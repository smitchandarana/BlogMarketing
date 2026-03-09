"""LinkedIn Service — wraps BlogMarketing's linkedin_generator.

Supports both modes:
  - blog_linked: 80-150 word teaser with article link (blog_data provided)
  - standalone:  300-500 word self-contained post (blog_data=None)
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

from blogpilot.content_engine.models.content_model import Content

logger = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))


def _ensure_root() -> None:
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)


def generate(
    topic: str,
    blog_data: dict | None = None,
    blog_url: str = "",
    insight_id: int | None = None,
) -> Content | None:
    """Generate a LinkedIn post and save it to disk.

    Args:
        topic:      Post topic.
        blog_data:  If provided, generates a blog-teaser post (80-150 words).
                    If None, generates a standalone post (300-500 words).
        blog_url:   Published blog URL (used in blog-linked mode).
        insight_id: FK to originating insight.

    Returns:
        Content object with file_path set, or None on failure.
    """
    _ensure_root()
    try:
        from linkedin_generator import generate_linkedin_post, save_linkedin_post  # type: ignore[import]
    except ImportError as exc:
        logger.error("Cannot import linkedin_generator: %s", exc)
        return None

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        li_data = generate_linkedin_post(topic=topic, blog_data=blog_data)
    except Exception as exc:
        logger.error("generate_linkedin_post failed for '%s': %s", topic, exc)
        return None

    try:
        file_path = save_linkedin_post(
            li_data=li_data,
            topic=topic,
            publish_date=date_str,
            blog_url=blog_url or li_data.get("blog_url", ""),
        )
    except Exception as exc:
        logger.error("save_linkedin_post failed: %s", exc)
        file_path = ""

    hashtags = li_data.get("hashtags", "")
    body = li_data.get("full_post") or li_data.get("caption", "")

    content = Content(
        content_type="linkedin_post",
        topic=topic,
        title=topic,
        body=body,
        insight_id=insight_id,
        file_path=file_path or "",
        hashtags=hashtags if isinstance(hashtags, str) else " ".join(hashtags),
    )
    logger.info(
        "LinkedIn post generated (%s mode): '%s'",
        "blog-linked" if blog_data else "standalone",
        topic[:60],
    )
    return content
