"""Content Worker — auto-generates draft content from high-confidence insights.

Pipeline per run:
  1. Fetch approved insights with confidence >= threshold
  2. For each insight: run content_planner.plan()
  3. Generate each planned item (blog or LinkedIn)
  4. Persist to content table
  5. Mark insight status as 'used'

Lifecycle:
  run_now()    → one synchronous cycle
  start()      → APScheduler interval job (default every 24h)
  stop()       → graceful shutdown
  is_running() → True if scheduler active
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime

import blogpilot.db.repositories.insights as insight_repo
import blogpilot.db.repositories.content as content_repo

logger = logging.getLogger(__name__)

_scheduler = None
_lock = threading.Lock()
_MIN_CONFIDENCE = 0.5   # Only generate content for insights above this threshold
_interval_hours: int = 24


def run_now(db_path: str | None = None) -> dict:
    """Execute one content generation cycle.

    Returns:
        Summary: insights_processed, content_created, timestamp.
    """
    from blogpilot.content_engine.services.content_planner import plan
    from blogpilot.content_engine.services.blog_service import generate as gen_blog
    from blogpilot.content_engine.services.linkedin_service import generate as gen_li

    logger.info("Content worker: starting run.")

    # Fetch draft insights above confidence threshold
    insights = [
        i for i in insight_repo.get_all(status="draft", limit=20, db_path=db_path)
        if i.confidence >= _MIN_CONFIDENCE
    ]

    if not insights:
        logger.info("Content worker: no eligible insights (confidence >= %.2f).", _MIN_CONFIDENCE)
        return {"insights_processed": 0, "content_created": 0, "timestamp": _now()}

    created = 0
    for insight in insights:
        plan_items = plan(insight)
        blog_content = None  # Track blog for LinkedIn blog-linked mode

        for item in plan_items:
            try:
                if item["content_type"] == "blog_post":
                    c = gen_blog(
                        topic=item["topic"],
                        angle=item["angle"],
                        insight_id=insight.id,
                        db_path=db_path,
                    )
                    if c:
                        c.id = content_repo.insert(c, db_path)
                        blog_content = c
                        created += 1

                elif item["content_type"] == "linkedin_post":
                    # If a blog was generated for this insight, link to it
                    blog_data = None
                    if blog_content and blog_content.file_path:
                        blog_data = {"title": blog_content.title}
                    c = gen_li(
                        topic=item["topic"],
                        blog_data=blog_data,
                        insight_id=insight.id,
                    )
                    if c:
                        c.id = content_repo.insert(c, db_path)
                        created += 1

            except Exception as exc:
                logger.error("Content generation failed for '%s': %s", item["topic"][:60], exc)

        # Mark insight as used so it isn't reprocessed
        try:
            insight_repo.update_status(insight.id, "used", db_path)
        except Exception as exc:
            logger.warning("Could not mark insight %s as used: %s", insight.id, exc)

    summary = {"insights_processed": len(insights), "content_created": created, "timestamp": _now()}
    logger.info("Content worker run complete: %s", summary)
    return summary


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _job(db_path: str | None = None) -> None:
    try:
        run_now(db_path)
    except Exception as exc:
        logger.error("Content worker job failed: %s", exc)


def get_interval() -> int:
    """Return current scheduler interval in hours."""
    return _interval_hours


def start(interval_hours: int = 24, db_path: str | None = None) -> None:
    global _scheduler, _interval_hours
    _interval_hours = interval_hours
    with _lock:
        if _scheduler is not None and _scheduler.running:
            logger.info("Content worker already running.")
            return
        try:
            from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import]
        except ImportError:
            logger.error("APScheduler not installed.")
            return
        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.add_job(
            _job, trigger="interval", hours=interval_hours,
            kwargs={"db_path": db_path}, id="content_generate", replace_existing=True,
        )
        _scheduler.start()
        logger.info("Content worker started — interval: every %d hour(s).", interval_hours)


def stop() -> None:
    global _scheduler
    with _lock:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
            _scheduler = None
            logger.info("Content worker stopped.")


def is_running() -> bool:
    return _scheduler is not None and _scheduler.running
