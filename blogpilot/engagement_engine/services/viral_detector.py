"""Viral Detector — identifies posts with above-average engagement for their author.

Uses the author_metrics table (Migration 4) to compare a post's engagement
against the author's rolling averages. A post is viral when:
  likes > author_avg_likes * 3  OR  comments > author_avg_comments * 2

Also provides update_author_metrics() to maintain the rolling averages
after each engagement cycle.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from blogpilot.engagement_engine.models.engagement_model import (
    LinkedInPost,
    ViralResult,
)

logger = logging.getLogger(__name__)

_VIRAL_LIKES_MULTIPLIER = 3.0
_VIRAL_COMMENTS_MULTIPLIER = 2.0
_MIN_SAMPLES = 3  # Don't compute averages from fewer than this many posts


def detect(post: LinkedInPost, db_path: str | None = None) -> ViralResult:
    """Determine if a post is viral compared to the author's historical average.

    Args:
        post: The LinkedIn post to evaluate.
        db_path: Optional DB path override.

    Returns:
        ViralResult with is_viral flag, viral_score, and reason.
    """
    avg_likes, avg_comments, post_count = _get_author_averages(post.author_name, db_path)

    if avg_likes is None or post_count < _MIN_SAMPLES:
        # No historical data — use raw thresholds as fallback
        is_viral = post.likes >= 100 or post.comments >= 20
        score = min(1.0, (post.likes / 100 + post.comments / 20) / 2) if is_viral else 0.0
        reason = "No historical data; applied raw threshold (likes>=100 or comments>=20)."
        return ViralResult(is_viral=is_viral, viral_score=score, reason=reason)

    likes_ratio = post.likes / max(avg_likes, 1.0)
    comments_ratio = post.comments / max(avg_comments, 1.0)

    is_viral = (
        likes_ratio >= _VIRAL_LIKES_MULTIPLIER
        or comments_ratio >= _VIRAL_COMMENTS_MULTIPLIER
    )
    viral_score = min(1.0, max(likes_ratio / _VIRAL_LIKES_MULTIPLIER,
                               comments_ratio / _VIRAL_COMMENTS_MULTIPLIER))

    detail = (
        f"likes={post.likes} ({likes_ratio:.1f}x avg={avg_likes:.0f}), "
        f"comments={post.comments} ({comments_ratio:.1f}x avg={avg_comments:.0f})"
    )
    reason = f"{detail}." if is_viral else f"{detail} — below viral threshold."

    return ViralResult(is_viral=is_viral, viral_score=viral_score, reason=reason)


def _get_author_averages(
    author_name: str, db_path: str | None
) -> tuple[float | None, float | None, int]:
    """Query author_metrics for the author's rolling average engagement.

    Returns:
        (avg_likes, avg_comments, post_count) — all None/0 if no data.
    """
    if not author_name:
        return None, None, 0

    try:
        from blogpilot.db.connection import get_connection  # type: ignore[import]
        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT avg_likes, avg_comments, post_count FROM author_metrics WHERE author_name = ?",
                (author_name,),
            ).fetchone()
            if row:
                return row["avg_likes"], row["avg_comments"], row["post_count"]
            return None, None, 0
    except Exception as exc:
        logger.debug("Viral detector: author_metrics query failed: %s", exc)
        return None, None, 0


def update_author_metrics(post: LinkedInPost, db_path: str | None = None) -> None:
    """Update author_metrics with a new post observation using rolling average.

    Uses the incremental mean formula:
      new_avg = old_avg + (value - old_avg) / new_count

    Args:
        post: The LinkedIn post with engagement counts.
        db_path: Optional DB path override.
    """
    if not post.author_name:
        return

    try:
        from blogpilot.db.connection import get_connection  # type: ignore[import]
        now = datetime.now(timezone.utc).isoformat()

        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT avg_likes, avg_comments, avg_shares, post_count FROM author_metrics WHERE author_name = ?",
                (post.author_name,),
            ).fetchone()

            if row:
                old_count = row["post_count"]
                new_count = old_count + 1
                new_avg_likes = row["avg_likes"] + (post.likes - row["avg_likes"]) / new_count
                new_avg_comments = row["avg_comments"] + (post.comments - row["avg_comments"]) / new_count
                new_avg_shares = row["avg_shares"] + (post.shares - row["avg_shares"]) / new_count

                conn.execute(
                    """UPDATE author_metrics
                       SET avg_likes = ?, avg_comments = ?, avg_shares = ?,
                           post_count = ?, last_updated = ?
                       WHERE author_name = ?""",
                    (new_avg_likes, new_avg_comments, new_avg_shares,
                     new_count, now, post.author_name),
                )
            else:
                conn.execute(
                    """INSERT INTO author_metrics
                       (author_name, avg_likes, avg_comments, avg_shares, post_count, last_updated)
                       VALUES (?, ?, ?, ?, 1, ?)""",
                    (post.author_name, float(post.likes), float(post.comments),
                     float(post.shares), now),
                )
            conn.commit()
    except Exception as exc:
        logger.warning("Failed to update author_metrics for %s: %s", post.author_name, exc)
