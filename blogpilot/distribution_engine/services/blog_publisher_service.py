"""Blog publisher service — wraps website_publisher.py from BlogMarketing root."""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))


def _ensure_root() -> None:
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)


def publish(
    blog_data: dict,
    src_html_path: str,
    publish_date: str,
    image_local: str | None = None,
    *,
    git_push: bool = True,
) -> str | None:
    """Publish a blog post to the Phoenix website.

    Args:
        blog_data:     Blog metadata dict with keys: title, slug, keywords, etc.
        src_html_path: Absolute path to the generated HTML file.
        publish_date:  ISO date string (YYYY-MM-DD).
        image_local:   Optional path to local image file.
        git_push:      Whether to git-push the website repo after publishing.

    Returns:
        Live blog URL if successful, else None.
    """
    _ensure_root()
    try:
        from website_publisher import publish_to_website, git_push_website  # type: ignore[import]

        publish_to_website(
            blog_data=blog_data,
            src_html_path=src_html_path,
            publish_date=publish_date,
            image_local=image_local,
        )
        logger.info("Blog '%s' published to website.", blog_data.get("title", "?"))

        if git_push:
            slug = blog_data.get("slug", "")
            git_push_website(slug, blog_data.get("title", ""))
            logger.info("Website git push complete for slug '%s'.", slug)

        base_url = os.getenv("WEBSITE_BASE_URL", "https://www.phoenixsolution.in")
        slug = blog_data.get("slug", "")
        return f"{base_url}/blog/{slug}" if slug else None

    except Exception as exc:
        logger.error("blog_publisher_service.publish failed: %s", exc)
        return None
