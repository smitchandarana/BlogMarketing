"""Blog Service — wraps BlogMarketing's blog_generator and html_renderer.

Does NOT reimplement any logic. Calls the existing flat modules directly.
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
    angle: str = "",
    insight_id: int | None = None,
    db_path: str | None = None,
) -> Content | None:
    """Generate a blog post from a topic and content angle.

    Calls:
        blog_generator.generate_blog(topic, content_angle) → blog_data dict
        image_service.generate(keywords) → image_path (optional)
        html_renderer.save_blog(blog_data, date, image_url) → html file path

    Args:
        topic:      Blog topic string.
        angle:      Content angle / hook (maps to content_angle in blog_generator).
        insight_id: FK to the originating insight.
        db_path:    Unused — passed for interface consistency.

    Returns:
        Content object with file_path set, or None on failure.
    """
    _ensure_root()
    try:
        from blog_generator import generate_blog      # type: ignore[import]
        from html_renderer import save_blog           # type: ignore[import]
    except ImportError as exc:
        logger.error("Cannot import blog_generator or html_renderer: %s", exc)
        return None

    try:
        blog_data = generate_blog(topic=topic, content_angle=angle)
    except Exception as exc:
        logger.error("blog_generator.generate_blog failed for '%s': %s", topic, exc)
        return None

    # Optional image
    image_path: str | None = None
    try:
        from blogpilot.content_engine.services.image_service import generate as get_image
        keywords = blog_data.get("keywords", [topic])
        slug = blog_data.get("slug", "")
        image_path = get_image(keywords, slug)
    except Exception as exc:
        logger.debug("Image generation skipped: %s", exc)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        html_path = save_blog(blog_data, publish_date=date_str, image_url=image_path)
    except Exception as exc:
        logger.error("html_renderer.save_blog failed: %s", exc)
        return None

    content = Content(
        content_type="blog_post",
        topic=topic,
        title=blog_data.get("title", topic),
        body=blog_data.get("intro", ""),
        insight_id=insight_id,
        file_path=html_path or "",
        hashtags="",
    )
    logger.info("Blog generated: '%s' → %s", content.title[:60], html_path)
    return content
