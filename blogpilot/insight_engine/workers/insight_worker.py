"""Insight Worker — orchestrates the full signal → insight pipeline.

Lifecycle:
  run_now()  → one synchronous cycle (used by API trigger + scheduler job)
  start()    → registers APScheduler interval job (default every 12 hours)
  stop()     → shuts down the scheduler
  is_running() → True if background scheduler active

Pipeline per run:
  1. Fetch unprocessed signals from DB
  2. Cluster them (signal_clusterer)
  3. Generate insights per cluster (insight_generator)
  4. Persist new insights to DB
  5. Rank and update confidence scores (insight_ranker)
  6. Mark contributing signals as 'processed'
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime

import blogpilot.db.repositories.signals as signal_repo
import blogpilot.db.repositories.insights as insight_repo

logger = logging.getLogger(__name__)

_scheduler = None
_lock = threading.Lock()
_MIN_SIGNALS_TO_RUN = 3   # Skip run if fewer unprocessed signals exist
_interval_hours: int = 12


def run_now(db_path: str | None = None) -> dict:
    """Execute one full insight generation cycle.

    Returns:
        Summary dict: signals_processed, insights_created, timestamp.
    """
    from blogpilot.insight_engine.services.signal_clusterer import cluster
    from blogpilot.insight_engine.services.insight_generator import generate
    from blogpilot.insight_engine.services.insight_ranker import rank

    logger.info("Insight worker: starting run.")

    # 1. Fetch unprocessed signals
    signals = signal_repo.get_all(status="processed", limit=200, db_path=db_path)
    # 'processed' signals have been scored but not yet converted to insights

    if len(signals) < _MIN_SIGNALS_TO_RUN:
        logger.info(
            "Insight worker: only %d scored signals available (min %d) — skipping.",
            len(signals), _MIN_SIGNALS_TO_RUN,
        )
        return {"signals_processed": 0, "insights_created": 0, "timestamp": _now()}

    # 2. Cluster
    clusters = cluster(signals)

    # 3. Generate insights
    new_insights = generate(clusters, db_path)

    # 4. Persist insights
    created_count = 0
    for insight in new_insights:
        try:
            insight.id = insight_repo.insert(insight, db_path)
            created_count += 1
        except Exception as exc:
            logger.error("Failed to insert insight '%s': %s", insight.title[:60], exc)

    # 5. Rank (updates confidence in DB)
    rank(new_insights, db_path=db_path, persist=True)

    # 6. Mark signals as used so they aren't reprocessed
    processed_ids = {sid for ins in new_insights for sid in ins.signal_ids}
    for sid in processed_ids:
        try:
            signal_repo.update_status(sid, "processed", db_path)
        except Exception as exc:
            logger.warning("Could not update signal %d status: %s", sid, exc)

    summary = {
        "signals_processed": len(signals),
        "insights_created": created_count,
        "timestamp": _now(),
    }
    logger.info("Insight worker run complete: %s", summary)
    return summary


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _job(db_path: str | None = None) -> None:
    try:
        run_now(db_path)
    except Exception as exc:
        logger.error("Insight worker job failed: %s", exc)


def get_interval() -> int:
    """Return current scheduler interval in hours."""
    return _interval_hours


def start(interval_hours: int = 12, db_path: str | None = None) -> None:
    """Start the background APScheduler job."""
    global _scheduler, _interval_hours
    _interval_hours = interval_hours
    with _lock:
        if _scheduler is not None and _scheduler.running:
            logger.info("Insight worker already running.")
            return
        try:
            from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import]
        except ImportError:
            logger.error("APScheduler not installed — insight worker cannot start.")
            return

        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.add_job(
            _job,
            trigger="interval",
            hours=interval_hours,
            kwargs={"db_path": db_path},
            id="insight_generate",
            replace_existing=True,
        )
        _scheduler.start()
        logger.info("Insight worker started — interval: every %d hour(s).", interval_hours)


def stop() -> None:
    global _scheduler
    with _lock:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
            _scheduler = None
            logger.info("Insight worker stopped.")


def is_running() -> bool:
    return _scheduler is not None and _scheduler.running
