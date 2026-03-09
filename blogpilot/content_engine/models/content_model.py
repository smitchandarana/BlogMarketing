"""Content data model for the Content Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

# Valid content types
CONTENT_TYPES = ("blog_post", "linkedin_post", "linkedin_comment")

# Valid status values
STATUS_DRAFT = "draft"
STATUS_SCHEDULED = "scheduled"
STATUS_PUBLISHED = "published"


@dataclass
class Content:
    """Represents a generated marketing content draft.

    Attributes:
        content_type:  One of CONTENT_TYPES.
        topic:         Topic string passed to the generator.
        title:         Headline or post title.
        body:          Full generated text (HTML for blog, plain text for LinkedIn).
        insight_id:    FK to the insight that triggered this content (nullable).
        file_path:     Path to the saved HTML/TXT file on disk.
        hashtags:      Space-separated hashtags string.
        status:        draft → scheduled → published.
        created_at:    ISO-8601 UTC timestamp.
        id:            Set by DB after insert.
    """

    content_type: str
    topic: str
    title: str = ""
    body: str = ""
    insight_id: int | None = None
    file_path: str = ""
    hashtags: str = ""
    status: str = STATUS_DRAFT
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    id: int | None = None

    @classmethod
    def from_row(cls, row) -> "Content":
        return cls(
            id=row["id"],
            content_type=row["content_type"],
            topic=row["topic"],
            title=row["title"] or "",
            body=row["body"] or "",
            insight_id=row["insight_id"],
            file_path=row["file_path"] or "",
            hashtags=row["hashtags"] or "",
            status=row["status"],
            created_at=row["created_at"],
        )
