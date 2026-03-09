"""Distribution Planner — decides where and when to publish each content item.

Rules:
  blog_post     → website (now) + linkedin promotion (+2h)
  linkedin_post → linkedin (next optimal slot from smart_scheduler)
  default       → linkedin (now)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Delay between blog publish and LinkedIn promotion post (minutes)
_LINKEDIN_PROMO_DELAY_MINUTES = 120


def plan(content_type: str, content_id: int) -> list[dict]:
    """Return a list of distribution jobs to create for this content item.

    Each job dict has keys: content_id, channel, scheduled_time (ISO str or None).

    Args:
        content_type: "blog_post" or "linkedin_post".
        content_id:   ID in the content table.

    Returns:
        List of job dicts ready for insertion into distribution_queue.
    """
    now = datetime.utcnow()
    jobs: list[dict] = []

    if content_type == "blog_post":
        # 1. Publish to website immediately
        jobs.append({
            "content_id": content_id,
            "channel": "website",
            "scheduled_time": now.isoformat() + "Z",
        })
        # 2. LinkedIn promotion after delay
        promo_time = now + timedelta(minutes=_LINKEDIN_PROMO_DELAY_MINUTES)
        jobs.append({
            "content_id": content_id,
            "channel": "linkedin",
            "scheduled_time": promo_time.isoformat() + "Z",
        })
        logger.info(
            "Planned blog_post %d: website now + linkedin at %s",
            content_id, promo_time.strftime("%H:%M"),
        )

    elif content_type == "linkedin_post":
        optimal_time = _get_optimal_linkedin_time(now)
        jobs.append({
            "content_id": content_id,
            "channel": "linkedin",
            "scheduled_time": optimal_time,
        })
        logger.info("Planned linkedin_post %d: linkedin at %s", content_id, optimal_time)

    else:
        # Default: publish to LinkedIn now
        jobs.append({
            "content_id": content_id,
            "channel": "linkedin",
            "scheduled_time": now.isoformat() + "Z",
        })

    return jobs


def _get_optimal_linkedin_time(fallback: datetime) -> str:
    """Use smart_scheduler to get the next optimal LinkedIn posting time.

    Falls back to the provided datetime if smart_scheduler is unavailable.
    """
    try:
        from blogpilot.distribution_engine.services.linkedin_publisher_service import (
            get_next_optimal_time,
        )
        optimal = get_next_optimal_time()
        if optimal:
            return optimal
    except Exception as exc:
        logger.debug("Could not get optimal time from smart_scheduler: %s", exc)
    return fallback.isoformat() + "Z"
