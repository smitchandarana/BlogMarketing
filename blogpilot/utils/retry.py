"""Retry utility — exponential backoff with jitter for transient failures.

Usage:
    from blogpilot.utils.retry import retry

    @retry(max_attempts=3, base_delay=1.0)
    def call_external_api():
        ...

    # Or as a function wrapper:
    result = retry(max_attempts=3)(lambda: requests.get(url))()
"""

from __future__ import annotations

import functools
import logging
import random
import time
from typing import TypeVar, Callable, ParamSpec

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def retry(
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator that retries a function with exponential backoff.

    Args:
        max_attempts: Total number of attempts (including first try).
        base_delay: Initial delay in seconds before first retry.
        max_delay: Maximum delay between retries.
        backoff_factor: Multiplier for delay after each attempt.
        jitter: Add random jitter to prevent thundering herd.
        retryable_exceptions: Tuple of exception types to retry on.

    Returns:
        Decorator function.
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            delay = base_delay
            last_exc: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        logger.error(
                            "%s failed after %d attempts: %s",
                            func.__name__, max_attempts, exc,
                        )
                        raise

                    actual_delay = delay
                    if jitter:
                        actual_delay = delay * (0.5 + random.random())
                    actual_delay = min(actual_delay, max_delay)

                    logger.warning(
                        "%s attempt %d/%d failed (%s), retrying in %.1fs...",
                        func.__name__, attempt, max_attempts, exc, actual_delay,
                    )
                    time.sleep(actual_delay)
                    delay *= backoff_factor

            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator
