"""Feed Scanner — scrapes posts from the LinkedIn feed using Playwright.

The scanner opens https://www.linkedin.com/feed/ in a Playwright browser
session, scrolls through the feed, and extracts post metadata.

Session cookies are loaded from LINKEDIN_COOKIES_PATH (env var) if set.
If the session is expired, a PlaywrightLoginRequired exception is raised
so the caller can prompt the user to re-authenticate.
"""

from __future__ import annotations

import logging
import os
import random
import time
from typing import TYPE_CHECKING

from blogpilot.engagement_engine.models.engagement_model import LinkedInPost

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_FEED_URL = "https://www.linkedin.com/feed/"
_LOGIN_URL = "https://www.linkedin.com/login"
_COOKIES_PATH = os.environ.get("LINKEDIN_COOKIES_PATH", "linkedin_session.json")


class PlaywrightLoginRequired(Exception):
    """Raised when the LinkedIn session has expired and re-login is needed."""


def _random_delay(min_s: float = 1.5, max_s: float = 4.0) -> None:
    """Sleep for a randomised duration to mimic human behaviour."""
    time.sleep(random.uniform(min_s, max_s))


def scan(
    scrolls: int = 3,
    headless: bool = True,
    cookies_path: str | None = None,
) -> list[LinkedInPost]:
    """Scroll the LinkedIn feed and return a list of extracted posts.

    Args:
        scrolls: Number of page scrolls (each yields ~10 posts).
        headless: Run Chromium in headless mode.
        cookies_path: Override path to stored session cookies JSON.

    Returns:
        List of LinkedInPost objects.

    Raises:
        PlaywrightLoginRequired: If the stored session is expired.
        ImportError: If playwright is not installed.
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "playwright is required for the engagement engine. "
            "Run: pip install playwright && playwright install chromium"
        ) from exc

    path = cookies_path or _COOKIES_PATH
    posts: list[LinkedInPost] = []

    # Fast-fail before launching a browser when there is no session at all.
    if not os.path.exists(path):
        raise PlaywrightLoginRequired(
            f"No LinkedIn session cookies found at '{path}'. "
            "Please re-authenticate via the Settings tab."
        )

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context()

        import json
        with open(path, encoding="utf-8") as f:
            cookies = json.load(f)
        context.add_cookies(cookies)

        page = context.new_page()
        page.goto(_FEED_URL, timeout=30_000)
        _random_delay(2, 4)

        # Detect redirect to login page — session expired
        if _LOGIN_URL in page.url or "authwall" in page.url:
            browser.close()
            raise PlaywrightLoginRequired(
                "LinkedIn session expired. Please re-authenticate via the Settings tab."
            )

        logger.info("Feed scanner: loaded feed, starting %d scroll(s).", scrolls)

        for i in range(scrolls):
            _extract_visible_posts(page, posts)
            page.keyboard.press("End")
            _random_delay(2.5, 5.0)
            logger.debug("Feed scanner: scroll %d/%d, %d posts so far.", i + 1, scrolls, len(posts))

        _extract_visible_posts(page, posts)
        browser.close()

    # Deduplicate by post_urn
    seen: set[str] = set()
    unique: list[LinkedInPost] = []
    for p in posts:
        if p.post_urn not in seen:
            seen.add(p.post_urn)
            unique.append(p)

    logger.info("Feed scanner: %d unique posts extracted.", len(unique))
    return unique


def _extract_visible_posts(page: object, posts: list[LinkedInPost]) -> None:  # type: ignore[type-arg]
    """Extract all visible post cards from the current page state."""
    try:
        cards = page.query_selector_all("div.feed-shared-update-v2")  # type: ignore[attr-defined]
        for card in cards:
            try:
                post = _parse_card(card)
                if post:
                    posts.append(post)
            except Exception as exc:
                logger.debug("Feed scanner: failed to parse card: %s", exc)
    except Exception as exc:
        logger.warning("Feed scanner: query_selector_all failed: %s", exc)


def _parse_card(card: object) -> LinkedInPost | None:  # type: ignore[type-arg]
    """Parse a single post card element into a LinkedInPost."""
    try:
        # Post URN from data attribute
        urn = card.get_attribute("data-urn") or ""  # type: ignore[attr-defined]
        if not urn:
            return None

        # Author
        author_el = card.query_selector("span.update-components-actor__name")  # type: ignore[attr-defined]
        author_name = author_el.inner_text().strip() if author_el else ""

        author_link_el = card.query_selector("a.update-components-actor__meta-link")  # type: ignore[attr-defined]
        author_url = author_link_el.get_attribute("href") or "" if author_link_el else ""

        # Post text
        text_el = card.query_selector("div.feed-shared-update-v2__description")  # type: ignore[attr-defined]
        text = text_el.inner_text().strip() if text_el else ""

        # Engagement counts (text like "1,234 reactions")
        likes = _parse_count(card, "button[aria-label*='reaction']")
        comments = _parse_count(card, "button[aria-label*='comment']")
        shares = _parse_count(card, "button[aria-label*='repost']")

        return LinkedInPost(
            post_urn=urn,
            author_name=author_name,
            author_url=author_url,
            text=text,
            likes=likes,
            comments=comments,
            shares=shares,
        )
    except Exception:
        return None


def _parse_count(card: object, selector: str) -> int:  # type: ignore[type-arg]
    """Extract an integer engagement count from a button aria-label."""
    try:
        el = card.query_selector(selector)  # type: ignore[attr-defined]
        if el is None:
            return 0
        label = el.get_attribute("aria-label") or ""
        # e.g. "1,234 reactions" or "56 comments"
        digits = label.split()[0].replace(",", "")
        return int(digits)
    except Exception:
        return 0
