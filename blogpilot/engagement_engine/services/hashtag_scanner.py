"""Hashtag Scanner — discover LinkedIn posts by scanning hashtag feeds.

Loads hashtags from Prompts/Hashtags.txt and opens each hashtag's feed page
on LinkedIn (e.g. linkedin.com/feed/hashtag/AI) to discover relevant posts
that may not appear in the user's main feed.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from pathlib import Path

from blogpilot.engagement_engine.models.engagement_model import LinkedInPost

logger = logging.getLogger(__name__)

_HASHTAG_URL_TEMPLATE = "https://www.linkedin.com/feed/hashtag/{tag}/"
_LOGIN_URL = "https://www.linkedin.com/login"
_COOKIES_PATH = os.environ.get("LINKEDIN_COOKIES_PATH", "linkedin_session.json")

# Max hashtags to scan per cycle (avoid rate-limiting)
_MAX_HASHTAGS_PER_SCAN = int(os.environ.get("HASHTAG_SCAN_MAX", "5"))


def _human_delay(min_s: float = 1.5, max_s: float = 4.0) -> None:
    """Sleep for a randomised duration to mimic human behaviour."""
    time.sleep(random.uniform(min_s, max_s))


def load_hashtags(path: str | None = None) -> list[str]:
    """Load hashtags from Prompts/Hashtags.txt.

    Args:
        path: Override path to the hashtags file.

    Returns:
        List of hashtag strings without the '#' prefix.
    """
    if path is None:
        # Try common locations
        candidates = [
            Path("Prompts/Hashtags.txt"),
            Path(__file__).resolve().parents[3] / "Prompts" / "Hashtags.txt",
        ]
        for candidate in candidates:
            if candidate.exists():
                path = str(candidate)
                break
        else:
            logger.warning("Hashtags.txt not found — using empty list.")
            return []

    tags: list[str] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            tag = line.strip().lstrip("#")
            if tag:
                tags.append(tag)

    logger.debug("Loaded %d hashtags from %s.", len(tags), path)
    return tags


def scan_hashtags(
    *,
    hashtags: list[str] | None = None,
    max_hashtags: int | None = None,
    scrolls_per_tag: int = 2,
    headless: bool = True,
    cookies_path: str | None = None,
) -> list[LinkedInPost]:
    """Scan LinkedIn hashtag feeds and return discovered posts.

    Args:
        hashtags: List of hashtags to scan (without '#'). Loads from file if None.
        max_hashtags: Max number of hashtags to visit. Defaults to env HASHTAG_SCAN_MAX.
        scrolls_per_tag: Number of page scrolls per hashtag feed.
        headless: Run Chromium in headless mode.
        cookies_path: Override path to stored session cookies.

    Returns:
        Deduplicated list of LinkedInPost objects from hashtag feeds.

    Raises:
        ImportError: If playwright is not installed.
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "playwright is required for hashtag scanning. "
            "Run: pip install playwright && playwright install chromium"
        ) from exc

    if hashtags is None:
        hashtags = load_hashtags()
    if not hashtags:
        logger.info("No hashtags to scan.")
        return []

    limit = max_hashtags or _MAX_HASHTAGS_PER_SCAN
    # Randomly sample to vary which hashtags we check each cycle
    selected = random.sample(hashtags, min(limit, len(hashtags)))
    logger.info("Hashtag scanner: scanning %d hashtags: %s", len(selected), selected)

    cookie_path = cookies_path or _COOKIES_PATH
    all_posts: list[LinkedInPost] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        # Load cookies
        if os.path.exists(cookie_path):
            with open(cookie_path, encoding="utf-8") as f:
                cookies = json.load(f)
            context.add_cookies(cookies)

        page = context.new_page()

        for tag in selected:
            url = _HASHTAG_URL_TEMPLATE.format(tag=tag)
            try:
                page.goto(url, timeout=30_000)
                _human_delay(2.0, 4.0)

                # Check for login redirect
                if _LOGIN_URL in page.url or "authwall" in page.url:
                    logger.error("Session expired during hashtag scan for #%s.", tag)
                    break

                # Scroll and extract
                for scroll_i in range(scrolls_per_tag):
                    posts = _extract_posts(page, tag)
                    all_posts.extend(posts)
                    page.keyboard.press("End")
                    _human_delay(2.0, 4.5)

                # Final extraction after last scroll
                posts = _extract_posts(page, tag)
                all_posts.extend(posts)

                logger.debug("Hashtag #%s: extracted %d posts.", tag, len(posts))
                _human_delay(3.0, 6.0)  # Longer delay between hashtags

            except Exception as exc:
                logger.warning("Hashtag scanner: error scanning #%s: %s", tag, exc)

        browser.close()

    # Deduplicate by post_urn
    seen: set[str] = set()
    unique: list[LinkedInPost] = []
    for p in all_posts:
        if p.post_urn not in seen:
            seen.add(p.post_urn)
            unique.append(p)

    logger.info("Hashtag scanner: %d unique posts from %d hashtags.", len(unique), len(selected))
    return unique


def _extract_posts(page: object, hashtag: str) -> list[LinkedInPost]:
    """Extract visible post cards from the current page state."""
    posts: list[LinkedInPost] = []
    try:
        cards = page.query_selector_all("div.feed-shared-update-v2")  # type: ignore[attr-defined]
        for card in cards:
            try:
                post = _parse_card(card, hashtag)
                if post:
                    posts.append(post)
            except Exception as exc:
                logger.debug("Hashtag scanner: parse error: %s", exc)
    except Exception as exc:
        logger.warning("Hashtag scanner: query_selector_all failed: %s", exc)
    return posts


def _parse_card(card: object, hashtag: str) -> LinkedInPost | None:
    """Parse a single post card into a LinkedInPost."""
    try:
        urn = card.get_attribute("data-urn") or ""  # type: ignore[attr-defined]
        if not urn:
            return None

        author_el = card.query_selector("span.update-components-actor__name")  # type: ignore[attr-defined]
        author_name = author_el.inner_text().strip() if author_el else ""

        author_link_el = card.query_selector("a.update-components-actor__meta-link")  # type: ignore[attr-defined]
        author_url = author_link_el.get_attribute("href") or "" if author_link_el else ""

        text_el = card.query_selector("div.feed-shared-update-v2__description")  # type: ignore[attr-defined]
        text = text_el.inner_text().strip() if text_el else ""

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


def _parse_count(card: object, selector: str) -> int:
    """Extract an integer engagement count from a button aria-label."""
    try:
        el = card.query_selector(selector)  # type: ignore[attr-defined]
        if el is None:
            return 0
        label = el.get_attribute("aria-label") or ""
        digits = label.split()[0].replace(",", "")
        return int(digits)
    except Exception:
        return 0
