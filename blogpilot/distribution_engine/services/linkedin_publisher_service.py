"""LinkedIn publisher service — wraps linkedin_publisher.py from BlogMarketing root."""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
_LI_GROWTH_ROOT = os.path.normpath(os.path.join(_ROOT, "..", "LinkedINGrowth"))
if not os.path.exists(_LI_GROWTH_ROOT):
    _LI_GROWTH_ROOT = r"d:\Projects\LinkedINGrowth"


def _ensure_root() -> None:
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)


def publish(
    text: str,
    image_path: str | None = None,
    org_urn: str | None = None,
) -> str | None:
    """Publish a LinkedIn post.

    Args:
        text:       Post body text (caption + hashtags combined).
        image_path: Optional local image path for media upload.
        org_urn:    Company page URN; posts to personal profile if None.

    Returns:
        LinkedIn post URL on success, else None.
    """
    _ensure_root()
    try:
        from linkedin_publisher import publish_post  # type: ignore[import]

        result = publish_post(text=text, image_path=image_path, org_urn=org_urn)
        if result:
            post_id = result.get("id", "")
            url = f"https://www.linkedin.com/feed/update/{post_id}" if post_id else None
            logger.info("LinkedIn post published. URL: %s", url or "unavailable")
            return url
        return None

    except Exception as exc:
        logger.error("linkedin_publisher_service.publish failed: %s", exc)
        return None


def pick_best_post() -> dict | None:
    """Use smart_scheduler to pick the highest-scored pending post.

    Returns:
        tracker.csv row dict of the best candidate, or None.
    """
    _ensure_root()
    try:
        from smart_scheduler import pick_best  # type: ignore[import]
        return pick_best()
    except Exception as exc:
        logger.warning("pick_best_post failed: %s", exc)
        return None


def get_next_optimal_time() -> str | None:
    """Return the next optimal publish time as an ISO string using smart_scheduler logic.

    Returns:
        ISO datetime string or None.
    """
    _ensure_root()
    try:
        from smart_scheduler import load_config, get_next_fire  # type: ignore[import]
        cfg = load_config()
        dt = get_next_fire(cfg)
        return dt.isoformat() if dt else None
    except Exception as exc:
        logger.warning("get_next_optimal_time failed: %s", exc)
        return None
