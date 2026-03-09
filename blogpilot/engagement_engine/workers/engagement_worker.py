"""Engagement Worker — scheduled LinkedIn engagement automation.

Lifecycle:
  run_now()    -> one synchronous cycle: scan -> classify -> engage
  start()      -> APScheduler interval job (default every 2 hours)
  stop()       -> graceful shutdown
  is_running() -> True if scheduler is active
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from blogpilot.engagement_engine.models.engagement_model import (
    EngagementDecision,
    EngagementLog,
    LinkedInPost,
)

logger = logging.getLogger(__name__)

_scheduler = None
_lock = threading.Lock()
_run_lock = threading.Lock()
_interval_hours: int = 2


def run_now(db_path: str | None = None, headless: bool = True) -> dict:
    """Execute one full engagement cycle.

    Flow:
      1. Scan LinkedIn feed for posts
      2. Check influencer profiles for new posts (high priority)
      3. Classify each post for relevance
      4. Detect viral posts
      5. Decide action per post
      6. Execute actions via Playwright
      7. Log results to DB

    Returns:
        Summary dict: posts_scanned, posts_engaged, comments_posted, likes_given, timestamp.
    """
    if not _run_lock.acquire(blocking=False):
        logger.warning("Engagement worker already running — skipping duplicate run.")
        return {"skipped": True, "timestamp": _now()}

    try:
        logger.info("Engagement worker: starting run.")

        from blogpilot.engagement_engine.services.feed_scanner import (
            PlaywrightLoginRequired,
            scan,
        )
        from blogpilot.engagement_engine.services.relevance_classifier import classify
        from blogpilot.engagement_engine.services.viral_detector import detect, update_author_metrics
        from blogpilot.engagement_engine.services.engagement_strategy import decide
        from blogpilot.engagement_engine.services.comment_generator import generate
        from blogpilot.engagement_engine.services.influencer_monitor import (
            check_influencer_posts,
            get_influencers,
        )

        from blogpilot.engagement_engine.services.browser_session import (
            BrowserSession,
            BrowserSessionError,
            SessionExpiredError,
        )

        # 1. Scan feed
        try:
            feed_posts = scan(scrolls=3, headless=headless)
        except PlaywrightLoginRequired as exc:
            logger.error("Engagement worker: %s", exc)
            return {"error": str(exc), "timestamp": _now()}

        # 2. Influencer posts (high priority)
        influencers = get_influencers(db_path)
        influencer_posts: list[LinkedInPost] = []
        for inf in influencers:
            try:
                influencer_posts.extend(check_influencer_posts(inf, headless=headless, db_path=db_path))
            except Exception as exc:
                logger.warning("Influencer check failed for %s: %s", inf.name, exc)

        # Merge — influencer posts first, then feed (deduplicated by urn)
        seen_urns: set[str] = set()
        all_posts: list[tuple[LinkedInPost, bool]] = []  # (post, is_influencer)
        for p in influencer_posts:
            if p.post_urn not in seen_urns:
                seen_urns.add(p.post_urn)
                all_posts.append((p, True))
        for p in feed_posts:
            if p.post_urn not in seen_urns:
                seen_urns.add(p.post_urn)
                all_posts.append((p, False))

        posts_scanned = len(all_posts)
        posts_engaged = 0
        comments_posted = 0
        likes_given = 0

        # 3. Open browser session for engagement actions
        try:
            session = BrowserSession(headless=headless)
            session.__enter__()
        except SessionExpiredError as exc:
            logger.error("Engagement worker: %s", exc)
            return {"error": str(exc), "timestamp": _now()}
        except (ImportError, BrowserSessionError) as exc:
            logger.error("Engagement worker: browser session failed: %s", exc)
            return {"error": str(exc), "timestamp": _now()}

        try:
            for post, is_inf in all_posts:
                try:
                    clf = classify(post)
                    viral = detect(post, db_path=db_path)
                    decision = decide(post, clf, viral, is_influencer=is_inf, db_path=db_path)

                    if decision.action == "skip":
                        _log_action(decision, db_path)
                        continue

                    if decision.action in ("like", "comment"):
                        if session.execute_like(post):
                            likes_given += 1

                    if decision.action == "comment":
                        comment_text = generate(post)
                        if comment_text and session.execute_comment(post, comment_text):
                            decision.comment_text = comment_text
                            comments_posted += 1

                    _log_action(decision, db_path)
                    posts_engaged += 1

                    # Update author rolling averages for viral detection
                    update_author_metrics(post, db_path)

                except Exception as exc:
                    logger.error("Engagement worker: error processing post %s: %s", post.post_urn, exc)
        finally:
            session.__exit__(None, None, None)

        summary = {
            "posts_scanned": posts_scanned,
            "posts_engaged": posts_engaged,
            "comments_posted": comments_posted,
            "likes_given": likes_given,
            "timestamp": _now(),
        }
        logger.info("Engagement worker run complete: %s", summary)
        return summary

    except Exception as exc:
        logger.error("Engagement worker run failed: %s", exc)
        return {"error": str(exc), "timestamp": _now()}

    finally:
        _run_lock.release()



def _log_action(decision: EngagementDecision, db_path: str | None) -> None:
    """Write an engagement action to the engagement_log table."""
    if decision.post is None:
        return
    entry = EngagementLog(
        post_urn=decision.post.post_urn,
        author_name=decision.post.author_name,
        post_text=decision.post.text[:500],
        action=decision.action,
        comment_text=decision.comment_text,
        relevance_score=decision.relevance_score,
        viral_score=decision.viral_score,
        engaged_at=_now(),
        status="done",
    )
    try:
        from blogpilot.db.connection import get_connection  # type: ignore[import]
        with get_connection(db_path) as conn:
            conn.execute(
                """INSERT INTO engagement_log
                   (post_urn, author_name, post_text, action, comment_text,
                    relevance_score, viral_score, engaged_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.post_urn, entry.author_name, entry.post_text,
                    entry.action, entry.comment_text,
                    entry.relevance_score, entry.viral_score,
                    entry.engaged_at, entry.status,
                ),
            )
            conn.commit()
    except Exception as exc:
        logger.error("Engagement worker: failed to log action: %s", exc)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job(db_path: str | None = None) -> None:
    try:
        run_now(db_path)
    except Exception as exc:
        logger.error("Engagement worker job failed: %s", exc)


def get_interval() -> int:
    """Return current scheduler interval in hours."""
    return _interval_hours


def start(interval_hours: int = 2, db_path: str | None = None) -> None:
    global _scheduler, _interval_hours
    _interval_hours = interval_hours
    with _lock:
        if _scheduler is not None and _scheduler.running:
            logger.info("Engagement worker already running.")
            return
        try:
            from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import]
        except ImportError:
            logger.error("APScheduler not installed — engagement worker disabled.")
            return
        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.add_job(
            _job, trigger="interval", hours=interval_hours,
            kwargs={"db_path": db_path}, id="engagement_run", replace_existing=True,
        )
        _scheduler.start()
        logger.info("Engagement worker started — every %d hour(s).", interval_hours)


def stop() -> None:
    global _scheduler
    with _lock:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
            _scheduler = None
            logger.info("Engagement worker stopped.")


def is_running() -> bool:
    return _scheduler is not None and _scheduler.running
