"""Engagement Strategy — decides the action to take for each post.

Decision table:
  Skip:              relevance_score < 0.6  OR  post already engaged
  Like only:         0.6 <= relevance_score < 0.75  AND  not viral
  Like + Comment:    relevance_score >= 0.75  OR  is_viral
  Priority comment:  influencer post (always Like + Comment if relevant)

Daily limits are enforced via the engagement_log table:
  max_likes_per_day    (default 50, configurable via env ENGAGEMENT_MAX_LIKES)
  max_comments_per_day (default 20, configurable via env ENGAGEMENT_MAX_COMMENTS)
"""

from __future__ import annotations

import logging
import os
from datetime import date

from blogpilot.engagement_engine.models.engagement_model import (
    ClassificationResult,
    EngagementDecision,
    LinkedInPost,
    ViralResult,
)

logger = logging.getLogger(__name__)

_MAX_LIKES = int(os.environ.get("ENGAGEMENT_MAX_LIKES", "50"))
_MAX_COMMENTS = int(os.environ.get("ENGAGEMENT_MAX_COMMENTS", "20"))
_COMMENT_THRESHOLD = 0.75
_RELEVANCE_THRESHOLD = 0.6


def decide(
    post: LinkedInPost,
    classification: ClassificationResult,
    viral: ViralResult,
    is_influencer: bool = False,
    db_path: str | None = None,
) -> EngagementDecision:
    """Determine the engagement action for a post.

    Args:
        post: The LinkedIn post.
        classification: Result from the relevance classifier.
        viral: Result from the viral detector.
        is_influencer: True if the post author is a tracked influencer.
        db_path: Optional DB path override.

    Returns:
        EngagementDecision with action ('like', 'comment', or 'skip').
    """
    # Skip irrelevant posts
    if not classification.relevant:
        return EngagementDecision(
            action="skip",
            relevance_score=classification.score,
            viral_score=viral.viral_score,
            post=post,
        )

    # Skip already-engaged posts
    if _already_engaged(post.post_urn, db_path):
        logger.debug("Strategy: post %s already engaged — skipping.", post.post_urn)
        return EngagementDecision(
            action="skip",
            relevance_score=classification.score,
            viral_score=viral.viral_score,
            post=post,
        )

    today_likes, today_comments = _get_today_counts(db_path)

    # Determine desired action
    wants_comment = (
        classification.score >= _COMMENT_THRESHOLD
        or viral.is_viral
        or is_influencer
    )

    if wants_comment:
        if today_likes < _MAX_LIKES and today_comments < _MAX_COMMENTS:
            action = "comment"
        elif today_likes < _MAX_LIKES:
            action = "like"  # Daily comment cap hit — fall back to like only
        else:
            action = "skip"
    else:
        # Like-only zone
        if today_likes < _MAX_LIKES:
            action = "like"
        else:
            action = "skip"

    if action == "skip":
        logger.info(
            "Strategy: daily limits reached (likes=%d, comments=%d) — skipping post %s.",
            today_likes, today_comments, post.post_urn,
        )

    return EngagementDecision(
        action=action,
        relevance_score=classification.score,
        viral_score=viral.viral_score,
        post=post,
    )


def _already_engaged(post_urn: str, db_path: str | None) -> bool:
    try:
        from blogpilot.db.connection import get_connection  # type: ignore[import]
        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM engagement_log WHERE post_urn = ? AND action != 'skip' LIMIT 1",
                (post_urn,),
            ).fetchone()
        return row is not None
    except Exception:
        return False


def _get_today_counts(db_path: str | None) -> tuple[int, int]:
    try:
        from blogpilot.db.connection import get_connection  # type: ignore[import]
        today = date.today().isoformat()
        with get_connection(db_path) as conn:
            likes = conn.execute(
                "SELECT COUNT(*) FROM engagement_log "
                "WHERE action IN ('like','comment') AND engaged_at LIKE ? AND status='done'",
                (f"{today}%",),
            ).fetchone()[0]
            comments = conn.execute(
                "SELECT COUNT(*) FROM engagement_log "
                "WHERE action = 'comment' AND engaged_at LIKE ? AND status='done'",
                (f"{today}%",),
            ).fetchone()[0]
        return likes, comments
    except Exception:
        return 0, 0
