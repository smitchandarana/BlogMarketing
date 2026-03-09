"""Analytics Worker — daily metrics collection and performance analysis.

Lifecycle:
  run_now()    → one synchronous cycle: collect → analyze
  start()      → APScheduler interval job (default every 24h)
  stop()       → graceful shutdown
  is_running() → True if scheduler active
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime

from blogpilot.analytics_engine.services.metrics_collector import collect_all
from blogpilot.analytics_engine.services.performance_analyzer import analyze

logger = logging.getLogger(__name__)

_scheduler = None
_lock = threading.Lock()
_run_lock = threading.Lock()  # Prevents duplicate concurrent runs
_interval_hours: int = 24


def run_now(db_path: str | None = None) -> dict:
    """Execute one full analytics cycle.

    Returns:
        Summary dict: linkedin_collected, website_collected, content_scored, timestamp.
    """
    if not _run_lock.acquire(blocking=False):
        logger.warning("Analytics worker already running — skipping duplicate run.")
        return {"skipped": True, "timestamp": _now()}

    try:
        logger.info("Analytics worker: starting run.")

        collection = collect_all(db_path)
        analysis = analyze(db_path)

        summary = {
            "linkedin_collected": collection.get("linkedin_collected", 0),
            "website_collected": collection.get("website_collected", 0),
            "content_scored": analysis.get("content_scored", 0),
            "timestamp": _now(),
        }
        logger.info("Analytics worker run complete: %s", summary)
        return summary

    except Exception as exc:
        logger.error("Analytics worker run failed: %s", exc)
        return {"error": str(exc), "timestamp": _now()}

    finally:
        _run_lock.release()


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _job(db_path: str | None = None) -> None:
    try:
        run_now(db_path)
    except Exception as exc:
        logger.error("Analytics worker job failed: %s", exc)


def get_interval() -> int:
    """Return current scheduler interval in hours."""
    return _interval_hours


def start(interval_hours: int = 24, db_path: str | None = None) -> None:
    global _scheduler, _interval_hours
    _interval_hours = interval_hours
    with _lock:
        if _scheduler is not None and _scheduler.running:
            logger.info("Analytics worker already running.")
            return
        try:
            from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import]
        except ImportError:
            logger.error("APScheduler not installed — analytics worker disabled.")
            return
        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.add_job(
            _job, trigger="interval", hours=interval_hours,
            kwargs={"db_path": db_path}, id="analytics_run", replace_existing=True,
        )
        _scheduler.start()
        logger.info("Analytics worker started — every %d hour(s).", interval_hours)


def stop() -> None:
    global _scheduler
    with _lock:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
            _scheduler = None
            logger.info("Analytics worker stopped.")


def is_running() -> bool:
    return _scheduler is not None and _scheduler.running
