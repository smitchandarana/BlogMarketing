"""Browser Session — shared Playwright session for LinkedIn engagement actions.

Manages a persistent browser context with stored cookies for authenticated
LinkedIn actions (like, comment). Reuses the same browser instance across
multiple actions within a single engagement cycle.

Usage:
    with BrowserSession(headless=True) as session:
        session.execute_like(post)
        session.execute_comment(post, "Great insight!")
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from pathlib import Path
from types import TracebackType

from blogpilot.engagement_engine.models.engagement_model import LinkedInPost

logger = logging.getLogger(__name__)

_FEED_URL = "https://www.linkedin.com/feed/"
_LOGIN_URL = "https://www.linkedin.com/login"
_COOKIES_PATH = os.environ.get("LINKEDIN_COOKIES_PATH", "linkedin_session.json")

# Daily limits (configurable via env)
_MAX_LIKES_PER_DAY = int(os.environ.get("ENGAGEMENT_MAX_LIKES", "50"))
_MAX_COMMENTS_PER_DAY = int(os.environ.get("ENGAGEMENT_MAX_COMMENTS", "20"))

# CSS selectors for LinkedIn UI elements
_SELECTORS = {
    "like_button": "button[aria-label*='Like']",
    "like_button_active": "button[aria-label*='Like'][aria-pressed='true']",
    "comment_button": "button[aria-label*='Comment']",
    "comment_box": "div.ql-editor[data-placeholder]",
    "comment_submit": "button.comments-comment-box__submit-button",
    "post_container": "div.feed-shared-update-v2",
}


class BrowserSessionError(Exception):
    """Raised when a browser action fails after retries."""


class SessionExpiredError(Exception):
    """Raised when the LinkedIn session cookie has expired."""


def _human_delay(min_s: float = 1.5, max_s: float = 4.0) -> None:
    """Sleep for a randomised duration to mimic human behaviour."""
    time.sleep(random.uniform(min_s, max_s))


def _typing_delay() -> None:
    """Short delay between keystrokes to simulate typing."""
    time.sleep(random.uniform(0.03, 0.12))


class BrowserSession:
    """Context-managed Playwright browser session for LinkedIn engagement.

    Args:
        headless: Run Chromium without a visible window.
        cookies_path: Path to stored LinkedIn session cookies JSON.
        max_retries: Number of retries per action on failure.
    """

    def __init__(
        self,
        *,
        headless: bool = True,
        cookies_path: str | None = None,
        max_retries: int = 2,
    ) -> None:
        self._headless = headless
        self._cookies_path = cookies_path or _COOKIES_PATH
        self._max_retries = max_retries
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._likes_today: int = 0
        self._comments_today: int = 0

    def __enter__(self) -> BrowserSession:
        self._start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._close()

    def _start(self) -> None:
        """Launch browser, load cookies, and verify authentication."""
        try:
            from playwright.sync_api import sync_playwright  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "playwright is required for engagement actions. "
                "Run: pip install playwright && playwright install chromium"
            ) from exc

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._headless)
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        # Load stored session cookies
        cookie_path = Path(self._cookies_path)
        if cookie_path.exists():
            with open(cookie_path, encoding="utf-8") as f:
                cookies = json.load(f)
            self._context.add_cookies(cookies)
            logger.debug("Loaded %d cookies from %s.", len(cookies), cookie_path)
        else:
            logger.warning("No LinkedIn session cookies at %s.", cookie_path)

        self._page = self._context.new_page()
        self._page.goto(_FEED_URL, timeout=30_000)
        _human_delay(2.0, 4.0)

        # Verify we're authenticated
        if _LOGIN_URL in self._page.url or "authwall" in self._page.url:
            self._close()
            raise SessionExpiredError(
                "LinkedIn session expired. Re-authenticate via Settings tab."
            )

        logger.info("Browser session started — authenticated on LinkedIn.")

    def _close(self) -> None:
        """Gracefully close the browser and Playwright."""
        try:
            if self._browser:
                self._browser.close()
        except Exception as exc:
            logger.debug("Browser close error: %s", exc)
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception as exc:
            logger.debug("Playwright stop error: %s", exc)
        self._browser = None
        self._context = None
        self._page = None
        self._playwright = None

    def _navigate_to_post(self, post: LinkedInPost) -> bool:
        """Scroll to the post identified by its URN on the current page.

        Returns True if the post element was found and scrolled into view.
        """
        if self._page is None:
            return False

        selector = f'div[data-urn="{post.post_urn}"]'
        try:
            el = self._page.query_selector(selector)
            if el:
                el.scroll_into_view_if_needed()
                _human_delay(0.8, 1.5)
                return True
        except Exception as exc:
            logger.debug("Could not scroll to post %s: %s", post.post_urn, exc)

        # Fallback: scroll down and search again
        for _ in range(5):
            self._page.keyboard.press("End")
            _human_delay(1.5, 3.0)
            try:
                el = self._page.query_selector(selector)
                if el:
                    el.scroll_into_view_if_needed()
                    _human_delay(0.8, 1.5)
                    return True
            except Exception:
                pass

        logger.warning("Post %s not found on page after scrolling.", post.post_urn)
        return False

    def execute_like(self, post: LinkedInPost) -> bool:
        """Click the Like button on a post.

        Args:
            post: The LinkedIn post to like.

        Returns:
            True if the like action succeeded.
        """
        if self._likes_today >= _MAX_LIKES_PER_DAY:
            logger.warning("Daily like limit (%d) reached — skipping.", _MAX_LIKES_PER_DAY)
            return False

        for attempt in range(1, self._max_retries + 1):
            try:
                return self._do_like(post)
            except Exception as exc:
                logger.warning(
                    "Like attempt %d/%d failed for %s: %s",
                    attempt, self._max_retries, post.post_urn, exc,
                )
                _human_delay(2.0, 5.0)

        logger.error("Like failed after %d retries for %s.", self._max_retries, post.post_urn)
        return False

    def _do_like(self, post: LinkedInPost) -> bool:
        """Internal: locate and click the Like button."""
        if self._page is None:
            raise BrowserSessionError("Browser session not started.")

        if not self._navigate_to_post(post):
            raise BrowserSessionError(f"Post {post.post_urn} not visible on page.")

        container = self._page.query_selector(f'div[data-urn="{post.post_urn}"]')
        if not container:
            raise BrowserSessionError(f"Post container not found: {post.post_urn}")

        # Check if already liked
        already_liked = container.query_selector(_SELECTORS["like_button_active"])
        if already_liked:
            logger.info("Post %s already liked — skipping.", post.post_urn)
            return True

        like_btn = container.query_selector(_SELECTORS["like_button"])
        if not like_btn:
            raise BrowserSessionError(f"Like button not found for {post.post_urn}")

        _human_delay(0.5, 1.5)
        like_btn.click()
        _human_delay(1.0, 2.0)

        self._likes_today += 1
        logger.info(
            "LIKED post %s by %s (%d/%d today).",
            post.post_urn, post.author_name, self._likes_today, _MAX_LIKES_PER_DAY,
        )
        return True

    def execute_comment(self, post: LinkedInPost, comment_text: str) -> bool:
        """Post a comment on a LinkedIn post.

        Args:
            post: The LinkedIn post to comment on.
            comment_text: The comment text to post.

        Returns:
            True if the comment was posted successfully.
        """
        if self._comments_today >= _MAX_COMMENTS_PER_DAY:
            logger.warning("Daily comment limit (%d) reached — skipping.", _MAX_COMMENTS_PER_DAY)
            return False

        if not comment_text or not comment_text.strip():
            logger.warning("Empty comment text — skipping comment on %s.", post.post_urn)
            return False

        for attempt in range(1, self._max_retries + 1):
            try:
                return self._do_comment(post, comment_text.strip())
            except Exception as exc:
                logger.warning(
                    "Comment attempt %d/%d failed for %s: %s",
                    attempt, self._max_retries, post.post_urn, exc,
                )
                _human_delay(3.0, 6.0)

        logger.error("Comment failed after %d retries for %s.", self._max_retries, post.post_urn)
        return False

    def _do_comment(self, post: LinkedInPost, comment_text: str) -> bool:
        """Internal: open comment box, type text, and submit."""
        if self._page is None:
            raise BrowserSessionError("Browser session not started.")

        if not self._navigate_to_post(post):
            raise BrowserSessionError(f"Post {post.post_urn} not visible on page.")

        container = self._page.query_selector(f'div[data-urn="{post.post_urn}"]')
        if not container:
            raise BrowserSessionError(f"Post container not found: {post.post_urn}")

        # Click the "Comment" button to open the comment box
        comment_btn = container.query_selector(_SELECTORS["comment_button"])
        if not comment_btn:
            raise BrowserSessionError(f"Comment button not found for {post.post_urn}")

        _human_delay(0.5, 1.2)
        comment_btn.click()
        _human_delay(1.5, 3.0)

        # Find the comment text editor
        comment_box = container.query_selector(_SELECTORS["comment_box"])
        if not comment_box:
            # Try page-level selector as fallback
            comment_box = self._page.query_selector(_SELECTORS["comment_box"])
        if not comment_box:
            raise BrowserSessionError(f"Comment box not found for {post.post_urn}")

        comment_box.click()
        _human_delay(0.3, 0.8)

        # Type the comment with human-like delays
        for char in comment_text:
            comment_box.type(char, delay=random.randint(30, 100))

        _human_delay(1.0, 2.0)

        # Click submit
        submit_btn = container.query_selector(_SELECTORS["comment_submit"])
        if not submit_btn:
            submit_btn = self._page.query_selector(_SELECTORS["comment_submit"])
        if not submit_btn:
            raise BrowserSessionError(f"Comment submit button not found for {post.post_urn}")

        submit_btn.click()
        _human_delay(2.0, 4.0)

        self._comments_today += 1
        logger.info(
            "COMMENTED on post %s by %s (%d/%d today): %.60s...",
            post.post_urn, post.author_name,
            self._comments_today, _MAX_COMMENTS_PER_DAY,
            comment_text,
        )
        return True

    @property
    def likes_today(self) -> int:
        """Number of likes executed in this session."""
        return self._likes_today

    @property
    def comments_today(self) -> int:
        """Number of comments posted in this session."""
        return self._comments_today
