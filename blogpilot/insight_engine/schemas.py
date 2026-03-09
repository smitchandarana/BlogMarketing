"""Pydantic schemas for Insight Engine API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class InsightResponse(BaseModel):
    id: int
    title: str
    summary: str
    category: str
    signal_ids: list[int]
    confidence: float
    action_items: list[str]
    status: str
    created_at: str


class InsightListResponse(BaseModel):
    insights: list[InsightResponse]
    total: int


class GenerateRequest(BaseModel):
    min_signals: int = Field(default=3, ge=1, description="Minimum signals required to run.")


class GenerateResponse(BaseModel):
    signals_processed: int
    insights_created: int
    timestamp: str


class WorkerStatusResponse(BaseModel):
    running: bool
