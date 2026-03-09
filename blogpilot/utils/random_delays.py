"""Random Delay utilities — human-like timing for automation actions.

Centralises all delay logic so engagement and scanning modules use
consistent, configurable timing patterns.
"""

from __future__ import annotations

import random
import time


def human_delay(min_s: float = 1.5, max_s: float = 4.0) -> float:
    """Sleep for a random duration within the given range.

    Args:
        min_s: Minimum delay in seconds.
        max_s: Maximum delay in seconds.

    Returns:
        The actual delay duration.
    """
    delay = random.uniform(min_s, max_s)
    time.sleep(delay)
    return delay


def typing_delay(min_ms: int = 30, max_ms: int = 120) -> float:
    """Sleep for a short random duration simulating keystroke timing.

    Args:
        min_ms: Minimum delay in milliseconds.
        max_ms: Maximum delay in milliseconds.

    Returns:
        The actual delay in seconds.
    """
    delay_s = random.randint(min_ms, max_ms) / 1000.0
    time.sleep(delay_s)
    return delay_s


def action_pause(action_type: str = "default") -> float:
    """Sleep with a delay appropriate for the type of action.

    Args:
        action_type: One of 'click', 'scroll', 'navigate', 'between_actions', 'default'.

    Returns:
        The actual delay in seconds.
    """
    ranges = {
        "click": (0.5, 1.5),
        "scroll": (2.0, 4.5),
        "navigate": (3.0, 6.0),
        "between_actions": (5.0, 12.0),
        "between_profiles": (8.0, 15.0),
        "default": (1.5, 4.0),
    }
    min_s, max_s = ranges.get(action_type, ranges["default"])
    return human_delay(min_s, max_s)


def jittered_interval(base_seconds: float, jitter_pct: float = 0.2) -> float:
    """Return a jittered version of a base interval.

    Useful for scheduler intervals to avoid synchronised bursts.

    Args:
        base_seconds: The base interval.
        jitter_pct: Maximum jitter as a fraction (0.2 = +/- 20%).

    Returns:
        Jittered interval in seconds.
    """
    jitter = base_seconds * jitter_pct
    return base_seconds + random.uniform(-jitter, jitter)
