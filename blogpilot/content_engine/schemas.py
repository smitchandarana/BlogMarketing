"""Pydantic schemas for Content Engine API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContentResponse(BaseModel):
    id: int
    content_type: str
    topic: str
    title: str
    body: str
    insight_id: int | None
    file_path: str
    hashtags: str
    status: str
    created_at: str


class ContentListResponse(BaseModel):
    content: list[ContentResponse]
    total: int


class GenerateRequest(BaseModel):
    insight_id: int | None = Field(default=None, description="Generate from a specific insight ID.")
    topic: str | None = Field(default=None, description="Generate standalone content for a topic.")
    content_type: str = Field(default="linkedin_post", description="blog_post or linkedin_post")


class GenerateResponse(BaseModel):
    insights_processed: int
    content_created: int
    timestamp: str


class WorkerStatusResponse(BaseModel):
    running: bool
