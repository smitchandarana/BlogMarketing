"""Human Behaviour simulation for browser automation.

Provides patterns that make automated browser interactions look natural:
- Random scroll patterns (not just End key)
- Mouse movement simulation hints
- Session activity windows (avoid 3am posting)
- Rate limiting with natural pauses
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Active hours (UTC) — avoid engagement outside these windows
_ACTIVE_HOURS_START = 6   # 6 AM UTC
_ACTIVE_HOURS_END = 22    # 10 PM UTC


def is_active_hours(*, start: int = _ACTIVE_HOURS_START, end: int = _ACTIVE_HOURS_END) -> bool:
    """Check if the current UTC hour falls within active engagement hours.

    Args:
        start: Start of active window (hour, 0-23).
        end: End of active window (hour, 0-23).

    Returns:
        True if current time is within the active window.
    """
    hour = datetime.now(timezone.utc).hour
    if start <= end:
        return start <= hour < end
    # Wraps midnight (e.g. 22 to 6)
    return hour >= start or hour < end


def random_scroll_pattern(page: object, scrolls: int = 3) -> None:
    """Simulate human-like scrolling on a page.

    Mixes different scroll techniques instead of just pressing End.

    Args:
        page: Playwright Page object.
        scrolls: Number of scroll actions.
    """
    from blogpilot.utils.random_delays import human_delay

    techniques = ["end_key", "wheel", "page_down"]

    for i in range(scrolls):
        technique = random.choice(techniques)
        try:
            if technique == "end_key":
                page.keyboard.press("End")  # type: ignore[attr-defined]
            elif technique == "wheel":
                distance = random.randint(300, 800)
                page.mouse.wheel(0, distance)  # type: ignore[attr-defined]
            elif technique == "page_down":
                page.keyboard.press("PageDown")  # type: ignore[attr-defined]
        except Exception as exc:
            logger.debug("Scroll technique '%s' failed: %s", technique, exc)

        # Variable pause between scrolls
        human_delay(1.5 + random.random(), 4.0 + random.random() * 2)

        # Occasionally pause longer (reading behaviour)
        if random.random() < 0.3:
            human_delay(3.0, 8.0)


class RateLimiter:
    """Simple in-memory rate limiter for engagement actions.

    Tracks action counts within a rolling window and enforces daily limits.

    Args:
        max_per_window: Maximum actions allowed in the window.
        window_label: Label for logging (e.g. 'likes', 'comments').
    """

    def __init__(self, max_per_window: int, window_label: str = "actions") -> None:
        self._max = max_per_window
        self._label = window_label
        self._count = 0
        self._date = datetime.now(timezone.utc).date()

    def _reset_if_new_day(self) -> None:
        today = datetime.now(timezone.utc).date()
        if today != self._date:
            logger.debug("RateLimiter[%s]: new day — resetting count.", self._label)
            self._count = 0
            self._date = today

    def can_proceed(self) -> bool:
        """Check if another action is allowed within the limit."""
        self._reset_if_new_day()
        return self._count < self._max

    def record(self) -> None:
        """Record that an action was taken."""
        self._reset_if_new_day()
        self._count += 1
        logger.debug(
            "RateLimiter[%s]: %d/%d used.",
            self._label, self._count, self._max,
        )

    @property
    def remaining(self) -> int:
        """Number of actions remaining in the current window."""
        self._reset_if_new_day()
        return max(0, self._max - self._count)

    @property
    def count(self) -> int:
        """Number of actions taken in the current window."""
        self._reset_if_new_day()
        return self._count
