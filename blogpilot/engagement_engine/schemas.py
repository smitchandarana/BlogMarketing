"""Engagement Engine — Pydantic request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class EngagementRunResponse(BaseModel):
    posts_scanned: int
    posts_engaged: int
    comments_posted: int
    likes_given: int
    timestamp: str
    skipped: bool = False
    error: str | None = None


class WorkerStatusResponse(BaseModel):
    running: bool
    interval_hours: int


class InfluencerCreate(BaseModel):
    name: str
    linkedin_url: str
    category: str = ""
    priority: int = 3


class InfluencerResponse(BaseModel):
    id: int
    name: str
    linkedin_url: str
    category: str
    priority: int
    last_checked: str | None
    active: int


class EngagementLogEntry(BaseModel):
    id: int
    post_urn: str
    author_name: str | None
    post_text: str | None
    action: str
    comment_text: str | None
    relevance_score: float | None
    viral_score: float | None
    engaged_at: str
    status: str
    error: str | None


class EngagementStats(BaseModel):
    total_likes: int
    total_comments: int
    today_likes: int
    today_comments: int
    engagement_rate: float
