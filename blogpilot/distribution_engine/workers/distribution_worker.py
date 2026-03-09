"""Distribution Worker — polls the queue and executes publishing jobs.

Lifecycle:
  run_now()    → one synchronous cycle: fetch due jobs → publish → update status
  start()      → APScheduler interval job (default every 30 min)
  stop()       → graceful shutdown
  is_running() → True if scheduler active
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime

import blogpilot.db.repositories.content as content_repo
import blogpilot.db.repositories.distribution as dist_repo
from blogpilot.distribution_engine.models.distribution_queue_model import (
    STATUS_PUBLISHED,
    STATUS_FAILED,
)

logger = logging.getLogger(__name__)

_scheduler = None
_lock = threading.Lock()
_interval_minutes: int = 30


def run_now(db_path: str | None = None) -> dict:
    """Execute one distribution cycle.

    Returns:
        Summary dict: jobs_processed, jobs_published, jobs_failed, timestamp.
    """
    logger.info("Distribution worker: starting run.")

    due_jobs = dist_repo.get_due(db_path)
    if not due_jobs:
        logger.info("Distribution worker: no jobs due.")
        return {"jobs_processed": 0, "jobs_published": 0, "jobs_failed": 0, "timestamp": _now()}

    published = 0
    failed = 0

    for job in due_jobs:
        content = content_repo.get_by_id(job.content_id, db_path)
        if content is None:
            logger.warning("Content %d not found for distribution job %d.", job.content_id, job.id)
            dist_repo.update_status(
                job.id, STATUS_FAILED,
                error_message=f"Content {job.content_id} not found.",
                db_path=db_path,
            )
            failed += 1
            continue

        try:
            url = _publish_job(job, content)
            dist_repo.update_status(
                job.id, STATUS_PUBLISHED,
                published_at=_now(),
                external_url=url,
                db_path=db_path,
            )
            content_repo.update_status(content.id, "published", db_path)
            logger.info("Job %d published (%s): %s", job.id, job.channel, url or "no URL")
            published += 1

        except Exception as exc:
            logger.error("Job %d failed (%s): %s", job.id, job.channel, exc)
            dist_repo.update_status(
                job.id, STATUS_FAILED,
                error_message=str(exc),
                db_path=db_path,
            )
            failed += 1

    summary = {
        "jobs_processed": len(due_jobs),
        "jobs_published": published,
        "jobs_failed": failed,
        "timestamp": _now(),
    }
    logger.info("Distribution worker run complete: %s", summary)
    return summary


def _publish_job(job, content) -> str | None:
    """Dispatch a single job to the correct publisher service."""
    if job.channel == "website":
        from blogpilot.distribution_engine.services.blog_publisher_service import publish

        blog_data = {
            "title": content.title,
            "slug": _slugify(content.title),
            "topic": content.topic,
            "keywords": content.hashtags.replace("#", "").split() if content.hashtags else [],
        }
        return publish(
            blog_data=blog_data,
            src_html_path=content.file_path,
            publish_date=content.created_at[:10],
        )

    elif job.channel == "linkedin":
        from blogpilot.distribution_engine.services.linkedin_publisher_service import publish

        text = f"{content.body}\n\n{content.hashtags}" if content.hashtags else content.body
        return publish(text=text)

    else:
        raise ValueError(f"Unknown channel: {job.channel}")


def _slugify(title: str) -> str:
    import re
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug[:80]


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _job(db_path: str | None = None) -> None:
    try:
        run_now(db_path)
    except Exception as exc:
        logger.error("Distribution worker job failed: %s", exc)


def get_interval() -> int:
    """Return current scheduler interval in minutes."""
    return _interval_minutes


def start(interval_minutes: int = 30, db_path: str | None = None) -> None:
    global _scheduler, _interval_minutes
    _interval_minutes = interval_minutes
    with _lock:
        if _scheduler is not None and _scheduler.running:
            logger.info("Distribution worker already running.")
            return
        try:
            from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import]
        except ImportError:
            logger.error("APScheduler not installed — distribution worker disabled.")
            return
        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.add_job(
            _job, trigger="interval", minutes=interval_minutes,
            kwargs={"db_path": db_path}, id="distribution_run", replace_existing=True,
        )
        _scheduler.start()
        logger.info("Distribution worker started — every %d minute(s).", interval_minutes)


def stop() -> None:
    global _scheduler
    with _lock:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
            _scheduler = None
            logger.info("Distribution worker stopped.")


def is_running() -> bool:
    return _scheduler is not None and _scheduler.running
