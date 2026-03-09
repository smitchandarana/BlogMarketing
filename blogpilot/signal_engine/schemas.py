"""Pydantic schemas for Signal Engine API request/response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SignalResponse(BaseModel):
    """API response for a single signal."""

    id: int
    source: str
    source_url: str
    title: str
    summary: str
    category: str
    relevance_score: float
    status: str
    created_at: str


class SignalListResponse(BaseModel):
    """Paginated list of signals."""

    signals: list[SignalResponse]
    total: int


class CollectRequest(BaseModel):
    """Optional body for POST /signals/collect."""

    run_scorer: bool = Field(
        default=True,
        description="Whether to score collected signals immediately.",
    )


class CollectResponse(BaseModel):
    """Summary returned after a collect run."""

    collected: int
    scored: int
    timestamp: str


class WorkerStatusResponse(BaseModel):
    """Status of the background signal worker."""

    running: bool
