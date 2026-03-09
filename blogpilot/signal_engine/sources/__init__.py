"""Source adapter protocol.

Any new source must implement:
    class MySource:
        def fetch(self, config: dict) -> list[Signal]: ...

Drop the file in this directory and register it in collector.py.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from blogpilot.signal_engine.models.signal import Signal


@runtime_checkable
class SourceAdapter(Protocol):
    """Protocol every signal source adapter must satisfy."""

    def fetch(self, config: dict) -> list[Signal]:
        """Collect raw signals from the source.

        Args:
            config: Source-specific config dict from signal_sources.json.

        Returns:
            List of unscored Signal objects.
        """
        ...
