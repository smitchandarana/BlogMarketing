"""Comment Service — wraps LinkedINGrowth's AI comment generator.

Used by the Distribution Engine (Phase 5) when engaging with LinkedIn posts.
Not auto-run by the content worker — called on-demand.

LinkedINGrowth path: d:/Projects/LinkedINGrowth
"""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)

_LI_GROWTH_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "..", "LinkedINGrowth")
)
# Fallback to absolute path if relative resolution fails
if not os.path.exists(_LI_GROWTH_ROOT):
    _LI_GROWTH_ROOT = r"d:\Projects\LinkedINGrowth"


def _ensure_li_growth() -> bool:
    """Add LinkedINGrowth to sys.path. Returns True if available."""
    if not os.path.exists(_LI_GROWTH_ROOT):
        logger.warning("LinkedINGrowth not found at %s — comment generation unavailable.", _LI_GROWTH_ROOT)
        return False
    if _LI_GROWTH_ROOT not in sys.path:
        sys.path.insert(0, _LI_GROWTH_ROOT)
    return True


def generate_comment(post_text: str, author: str = "", topic: str = "") -> str | None:
    """Generate a relevant AI comment for a LinkedIn post.

    Delegates to LinkedINGrowth/ai/comment_generator.generate_comment().

    Args:
        post_text: The LinkedIn post body text.
        author:    Post author name (optional, improves relevance).
        topic:     Topic label (optional).

    Returns:
        Comment string, or None if LinkedINGrowth is unavailable.
    """
    if not _ensure_li_growth():
        return None
    try:
        from ai.comment_generator import generate_comment as _gen  # type: ignore[import]
        comment = _gen(post_text=post_text, author=author, topic=topic)
        logger.info("Comment generated (%d chars) for topic '%s'", len(comment), topic or "unknown")
        return comment
    except Exception as exc:
        logger.error("comment_generator failed: %s", exc)
        return None


def classify_relevance(post_text: str) -> bool:
    """Check if a post is relevant to Phoenix Solutions topics.

    Delegates to LinkedINGrowth/ai/relevance_classifier.is_relevant().

    Args:
        post_text: LinkedIn post body text.

    Returns:
        True if relevant, False otherwise (defaults to True on error).
    """
    if not _ensure_li_growth():
        return True  # Fail open — don't block on missing dep
    try:
        from ai.relevance_classifier import is_relevant  # type: ignore[import]
        result = is_relevant(post_text)
        logger.debug("Relevance check: %s", "RELEVANT" if result else "NOT_RELEVANT")
        return result
    except Exception as exc:
        logger.warning("relevance_classifier failed: %s — defaulting to True", exc)
        return True
