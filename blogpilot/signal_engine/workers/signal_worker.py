"""Signal Worker — scheduled collection + scoring job.

Lifecycle:
  start()  → registers an APScheduler interval job, returns immediately
  stop()   → shuts down the scheduler cleanly
  run_now() → runs one collect→score cycle synchronously (for API trigger)

The interval is configurable via scheduler_config.json 'signal_interval_hours' key.
Default: every 6 hours.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

_scheduler = None
_lock = threading.Lock()
_interval_hours: int = 6


def run_now(db_path: str | None = None) -> dict:
    """Execute one collect → score cycle and return a summary.

    Args:
        db_path: Optional DB path override.

    Returns:
        Dict with keys: collected (int), scored (int), timestamp (str).
    """
    from blogpilot.signal_engine.services.collector import collect
    from blogpilot.signal_engine.services.scorer import score

    logger.info("Signal worker: starting manual run.")
    new_signals = collect(db_path)
    scored = score(new_signals, db_path)

    summary = {
        "collected": len(new_signals),
        "scored": len(scored),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    logger.info("Signal worker run complete: %s", summary)
    return summary


def _job(db_path: str | None = None) -> None:
    """APScheduler job target — wraps run_now with error isolation."""
    try:
        run_now(db_path)
    except Exception as exc:
        logger.error("Signal worker job failed: %s", exc)


def get_interval() -> int:
    """Return current scheduler interval in hours."""
    return _interval_hours


def start(interval_hours: int = 6, db_path: str | None = None) -> None:
    """Start the background APScheduler interval job.

    Args:
        interval_hours: How often to collect signals. Default 6.
        db_path: Optional DB path override passed through to job.
    """
    global _scheduler, _interval_hours
    _interval_hours = interval_hours

    with _lock:
        if _scheduler is not None and _scheduler.running:
            logger.info("Signal worker already running.")
            return

        try:
            from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import]
        except ImportError:
            logger.error("APScheduler not installed — signal worker cannot start.")
            return

        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.add_job(
            _job,
            trigger="interval",
            hours=interval_hours,
            kwargs={"db_path": db_path},
            id="signal_collect",
            replace_existing=True,
        )
        _scheduler.start()
        logger.info("Signal worker started — interval: every %d hour(s).", interval_hours)


def stop() -> None:
    """Shut down the background scheduler gracefully."""
    global _scheduler
    with _lock:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
            _scheduler = None
            logger.info("Signal worker stopped.")


def is_running() -> bool:
    """Return True if the background scheduler is active."""
    return _scheduler is not None and _scheduler.running
