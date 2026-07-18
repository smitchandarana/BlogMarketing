"""Distribution Planner — decides where and when to publish each content item.

Rules:
  blog_post     → website (now)
  linkedin_post → linkedin (next optimal slot from smart_scheduler)
  default       → linkedin (now)
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


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
        # Publish to website immediately. We deliberately do NOT also queue a
        # "linkedin" promo job pointing at this same content_id: content_planner
        # already allocates at least one dedicated linkedin_post content row
        # per insight (see content_planner._PLAN_RULES — every category has
        # li_count >= 1), each with its own properly-generated caption and its
        # own linkedin distribution job via the branch below. A second
        # "linkedin" job here used to reuse this blog content_id, and
        # distribution_worker._publish_job() would then post content.body
        # verbatim to LinkedIn — but for a blog_post row that's just the raw
        # intro paragraph (no hook, no hashtags, no link to the article),
        # so every blog produced one real LinkedIn post plus one malformed
        # duplicate that burned the daily LinkedIn post budget.
        jobs.append({
            "content_id": content_id,
            "channel": "website",
            "scheduled_time": now.isoformat() + "Z",
        })
        logger.info("Planned blog_post %d: website now.", content_id)

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
