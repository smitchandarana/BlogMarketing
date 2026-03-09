"""Pydantic schemas for Distribution Engine API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueueItemResponse(BaseModel):
    id: int
    content_id: int
    channel: str
    status: str
    scheduled_time: str | None
    published_at: str | None
    external_url: str | None
    error_message: str | None
    created_at: str


class QueueListResponse(BaseModel):
    items: list[QueueItemResponse]
    total: int


class DistributeRequest(BaseModel):
    content_id: int = Field(description="Content record ID to distribute.")
    content_type: str = Field(
        default="linkedin_post",
        description="blog_post or linkedin_post — determines channel routing.",
    )


class DistributeResponse(BaseModel):
    jobs_created: int
    queue_ids: list[int]
    timestamp: str


class ScheduleRequest(BaseModel):
    queue_id: int = Field(description="Queue item ID to reschedule.")
    scheduled_time: str = Field(description="ISO datetime string for new publish time.")


class ScheduleResponse(BaseModel):
    queue_id: int
    scheduled_time: str


class WorkerRunResponse(BaseModel):
    jobs_processed: int
    jobs_published: int
    jobs_failed: int
    timestamp: str


class WorkerStatusResponse(BaseModel):
    running: bool
