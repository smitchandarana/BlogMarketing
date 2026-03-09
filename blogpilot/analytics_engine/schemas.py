"""Pydantic schemas for Analytics Engine API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MetricsResponse(BaseModel):
    id: int
    content_id: int
    channel: str
    impressions: int
    clicks: int
    likes: int
    comments: int
    engagements: int
    shares: int
    engagement_score: float
    recorded_at: str


class ContentMetricsResponse(BaseModel):
    content_id: int
    records: list[MetricsResponse]


class TopContentItem(BaseModel):
    id: int
    topic: str
    content_type: str
    performance_score: float
    status: str
    created_at: str


class TopContentResponse(BaseModel):
    items: list[TopContentItem]
    total: int


class TopicPerformance(BaseModel):
    topic: str
    avg_engagement: float
    content_count: int


class FormatPerformance(BaseModel):
    content_type: str
    avg_engagement: float
    content_count: int


class HourlyEngagement(BaseModel):
    hour: int
    avg_engagement: float
    sample_count: int


class DashboardResponse(BaseModel):
    avg_engagement_rate: float
    top_topics: list[TopicPerformance]
    top_formats: list[FormatPerformance]
    best_linkedin_hours: list[HourlyEngagement]
    best_website_hours: list[HourlyEngagement]


class CollectResponse(BaseModel):
    linkedin_collected: int
    website_collected: int
    content_scored: int
    timestamp: str


class WorkerStatusResponse(BaseModel):
    running: bool
