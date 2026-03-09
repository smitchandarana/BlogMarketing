"""Distribution Queue data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

STATUS_QUEUED = "queued"
STATUS_SCHEDULED = "scheduled"
STATUS_PUBLISHED = "published"
STATUS_FAILED = "failed"

CHANNEL_WEBSITE = "website"
CHANNEL_LINKEDIN = "linkedin"


@dataclass
class DistributionQueue:
    content_id: int
    channel: str
    status: str = STATUS_QUEUED
    scheduled_time: str | None = None
    published_at: str | None = None
    error_message: str | None = None
    external_url: str | None = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    id: int = 0

    @classmethod
    def from_row(cls, row) -> "DistributionQueue":
        return cls(
            id=row["id"],
            content_id=row["content_id"],
            channel=row["channel"],
            status=row["status"],
            scheduled_time=row["scheduled_at"],   # DB column is scheduled_at
            published_at=row["published_at"],
            error_message=row["error_message"],
            external_url=row["external_url"],
            created_at=row["created_at"],
        )
