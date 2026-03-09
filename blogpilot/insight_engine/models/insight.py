"""Insight data model for the Insight Engine."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Insight:
    """Represents a structured decision intelligence insight derived from signals.

    Attributes:
        title:            Short headline describing the core problem.
        summary:          Full Groq-generated insight paragraph.
        category:         Topic domain (matches signal category).
        signal_ids:       IDs of the signals that contributed to this insight.
        confidence:       Priority score 0.0–1.0 assigned by insight_ranker.
        action_items:     List of recommended actions for Phoenix Solutions.
        status:           Workflow state: 'draft' → 'approved' → 'used'.
        created_at:       ISO-8601 UTC timestamp string.
        id:               Set by DB after insert; None before persistence.
    """

    title: str
    summary: str
    category: str
    signal_ids: list[int] = field(default_factory=list)
    confidence: float = 0.0
    action_items: list[str] = field(default_factory=list)
    status: str = "draft"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    id: int | None = None

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def signal_ids_json(self) -> str:
        return json.dumps(self.signal_ids)

    def action_items_json(self) -> str:
        return json.dumps(self.action_items)

    @classmethod
    def from_row(cls, row) -> "Insight":
        """Construct an Insight from a sqlite3.Row."""
        try:
            signal_ids = json.loads(row["signal_ids"] or "[]")
        except (json.JSONDecodeError, TypeError):
            signal_ids = []

        try:
            action_items = json.loads(row["action_items"] or "[]")
        except (json.JSONDecodeError, TypeError):
            action_items = []

        return cls(
            id=row["id"],
            title=row["title"],
            summary=row["summary"],
            category=row["category"] or "general",
            signal_ids=signal_ids,
            confidence=row["confidence"] or 0.0,
            action_items=action_items,
            status=row["status"],
            created_at=row["created_at"],
        )
