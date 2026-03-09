"""Shared logger factory for all blogpilot modules.

Does NOT reconfigure the root logger — the existing main.py logging setup
(StreamHandler + FileHandler to blog_marketing.log) is preserved.
"""

from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a named logger under the blogpilot namespace.

    Args:
        name: Module name, typically passed as __name__.

    Returns:
        A Logger instance prefixed with 'blogpilot.' if not already.
    """
    if not name.startswith("blogpilot"):
        name = f"blogpilot.{name}"
    return logging.getLogger(name)
