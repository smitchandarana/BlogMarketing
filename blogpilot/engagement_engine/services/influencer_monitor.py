"""Influencer Monitor — visits target influencer profiles and collects recent posts.

Reads the influencer target list from the database and, for each active
influencer, visits their LinkedIn profile to check for new posts (last 24 hours).
New posts are returned with high priority for the engagement queue.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from blogpilot.engagement_engine.models.engagement_model import (
    InfluencerTarget,
    LinkedInPost,
)

logger = logging.getLogger(__name__)

_RECENCY_HOURS = 24


def get_influencers(db_path: str | None = None) -> list[InfluencerTarget]:
    """Return all active influencer targets from the database."""
    try:
        from blogpilot.db.connection import get_connection  # type: ignore[import]
        with get_connection(db_path) as conn:
            rows = conn.execute(
                "SELECT id, name, linkedin_url, category, priority, last_checked, active "
                "FROM influencer_targets WHERE active = 1 ORDER BY priority DESC"
            ).fetchall()
        return [
            InfluencerTarget(
                id=r[0], name=r[1], linkedin_url=r[2],
                category=r[3] or "", priority=r[4],
                last_checked=r[5] or "", active=r[6],
            )
            for r in rows
        ]
    except Exception as exc:
        logger.error("Influencer monitor: failed to load targets: %s", exc)
        return []


def add_influencer(
    name: str, linkedin_url: str, category: str = "", priority: int = 3,
    db_path: str | None = None,
) -> int:
    """Insert a new influencer target. Returns the new row id."""
    from blogpilot.db.connection import get_connection  # type: ignore[import]
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO influencer_targets (name, linkedin_url, category, priority, active) "
            "VALUES (?, ?, ?, ?, 1)",
            (name, linkedin_url, category, priority),
        )
        conn.commit()
        return cur.lastrowid or 0


def remove_influencer(influencer_id: int, db_path: str | None = None) -> None:
    """Soft-delete an influencer target (sets active = 0)."""
    from blogpilot.db.connection import get_connection  # type: ignore[import]
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE influencer_targets SET active = 0 WHERE id = ?",
            (influencer_id,),
        )
        conn.commit()


def check_influencer_posts(
    target: InfluencerTarget,
    headless: bool = True,
    db_path: str | None = None,
) -> list[LinkedInPost]:
    """Visit an influencer's profile and return posts published in the last 24 hours.

    Args:
        target: The influencer target to check.
        headless: Run Chromium in headless mode.
        db_path: Optional DB path override (for last_checked update).

    Returns:
        List of LinkedInPost objects from the last RECENCY_HOURS.
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "playwright is required. Run: pip install playwright && playwright install chromium"
        ) from exc

    import os
    import json
    import time
    import random

    cookies_path = os.environ.get("LINKEDIN_COOKIES_PATH", "linkedin_session.json")
    posts: list[LinkedInPost] = []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            context = browser.new_context()
            if os.path.exists(cookies_path):
                with open(cookies_path, encoding="utf-8") as f:
                    context.add_cookies(json.load(f))

            page = context.new_page()
            profile_url = target.linkedin_url.rstrip("/") + "/recent-activity/shares/"
            page.goto(profile_url, timeout=30_000)
            time.sleep(random.uniform(2, 4))

            cards = page.query_selector_all("div.feed-shared-update-v2")
            for card in cards:
                try:
                    urn = card.get_attribute("data-urn") or ""
                    if not urn:
                        continue
                    text_el = card.query_selector("div.feed-shared-update-v2__description")
                    text = text_el.inner_text().strip() if text_el else ""
                    posts.append(LinkedInPost(
                        post_urn=urn,
                        author_name=target.name,
                        author_url=target.linkedin_url,
                        text=text,
                    ))
                except Exception:
                    continue

            browser.close()
    except Exception as exc:
        logger.error("Influencer monitor: failed to check %s: %s", target.name, exc)
        return []

    # Update last_checked timestamp
    _update_last_checked(target.id, db_path)
    logger.info(
        "Influencer monitor: found %d posts for %s.", len(posts), target.name
    )
    return posts


def _update_last_checked(influencer_id: int, db_path: str | None) -> None:
    try:
        from blogpilot.db.connection import get_connection  # type: ignore[import]
        now = datetime.now(timezone.utc).isoformat()
        with get_connection(db_path) as conn:
            conn.execute(
                "UPDATE influencer_targets SET last_checked = ? WHERE id = ?",
                (now, influencer_id),
            )
            conn.commit()
    except Exception as exc:
        logger.debug("Influencer monitor: could not update last_checked: %s", exc)
