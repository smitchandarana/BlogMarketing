"""Analytics Engine — Metrics data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Metrics:
    content_id: int
    channel: str
    impressions: int = 0
    clicks: int = 0
    likes: int = 0
    comments: int = 0
    engagements: int = 0
    shares: int = 0
    engagement_score: float = 0.0
    raw_payload: str | None = None
    recorded_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    id: int = 0

    @classmethod
    def from_row(cls, row) -> "Metrics":
        return cls(
            id=row["id"],
            content_id=row["content_id"],
            channel=row["channel"],
            impressions=row["impressions"],
            clicks=row["clicks"],
            likes=row.get("likes", 0) or 0,
            comments=row.get("comments", 0) or 0,
            engagements=row["engagements"],
            shares=row["shares"],
            engagement_score=row.get("engagement_score", 0.0) or 0.0,
            raw_payload=row.get("raw_payload"),
            recorded_at=row["measured_at"],
        )

    @staticmethod
    def compute_engagement_score(
        likes: int,
        comments: int,
        shares: int,
        impressions: int,
    ) -> float:
        """Weighted engagement score normalised by impressions."""
        weighted = likes + comments * 2 + shares * 3
        return round(weighted / max(impressions, 1), 6)
