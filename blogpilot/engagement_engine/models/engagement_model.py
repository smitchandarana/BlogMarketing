"""Engagement Engine domain models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LinkedInPost:
    """A post scraped from the LinkedIn feed."""

    post_urn: str
    author_name: str
    author_url: str
    text: str
    likes: int = 0
    comments: int = 0
    shares: int = 0
    timestamp: str = ""


@dataclass
class ClassificationResult:
    """Result of relevance classification for a post."""

    relevant: bool
    score: float
    reason: str


@dataclass
class ViralResult:
    """Result of viral detection for a post."""

    is_viral: bool
    viral_score: float
    reason: str


@dataclass
class EngagementDecision:
    """The engagement action decided for a post."""

    action: str          # 'like' | 'comment' | 'skip'
    comment_text: str = ""
    relevance_score: float = 0.0
    viral_score: float = 0.0
    post: LinkedInPost | None = None


@dataclass
class EngagementLog:
    """A row in the engagement_log table."""

    post_urn: str
    author_name: str
    post_text: str
    action: str
    comment_text: str = ""
    relevance_score: float = 0.0
    viral_score: float = 0.0
    engaged_at: str = ""
    status: str = "done"
    error: str = ""
    id: int = 0


@dataclass
class InfluencerTarget:
    """A row in the influencer_targets table."""

    name: str
    linkedin_url: str
    category: str = ""
    priority: int = 3
    last_checked: str = ""
    active: int = 1
    id: int = 0
