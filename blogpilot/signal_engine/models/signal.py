"""Signal data model for the Signal Engine."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Signal:
    """Represents a single industry signal collected from an external source.

    Attributes:
        source:          Origin adapter — 'rss', 'reddit', 'news', 'manual'.
        source_url:      Canonical URL of the original item (used for dedup).
        title:           Headline or post title.
        summary:         Clean text summary (the user-facing content).
        category:        Topic category / signal type (e.g. 'ai', 'marketing').
        raw_data:        JSON-serialised original payload from the source.
        relevance_score: Groq-assigned score 0.0–1.0 vs Phoenix Solutions domain.
        status:          Workflow state: 'new' → 'processed' → 'dismissed'.
        created_at:      ISO-8601 UTC timestamp string.
        id:              Set by DB after insert; None before persistence.
    """

    source: str
    source_url: str
    title: str
    summary: str
    category: str = "general"
    raw_data: str = field(default_factory=lambda: "{}")
    relevance_score: float = 0.0
    status: str = "new"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    id: int | None = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def url_hash(self) -> str:
        """Return a short SHA-256 hex digest of source_url for dedup checks."""
        return hashlib.sha256(self.source_url.encode()).hexdigest()[:16]

    def set_raw(self, obj: dict) -> None:
        """Serialise a dict into raw_data."""
        self.raw_data = json.dumps(obj, ensure_ascii=False)

    def get_raw(self) -> dict:
        """Deserialise raw_data back to a dict."""
        try:
            return json.loads(self.raw_data)
        except (json.JSONDecodeError, TypeError):
            return {}

    @classmethod
    def from_row(cls, row) -> "Signal":
        """Construct a Signal from a sqlite3.Row."""
        return cls(
            id=row["id"],
            source=row["source"],
            source_url=row["source_url"] or "",
            title=row["title"],
            summary=row["summary"] or "",
            category=row["category"] or "general",
            raw_data=row["raw_data"] or "{}",
            relevance_score=row["relevance_score"] or 0.0,
            status=row["status"],
            created_at=row["created_at"],
        )
