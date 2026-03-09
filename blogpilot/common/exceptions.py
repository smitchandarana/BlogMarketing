"""Exception hierarchy for the Phoenix Marketing Intelligence Engine."""

from __future__ import annotations


class ApplicationError(Exception):
    """Base exception for all domain-specific errors."""


class NotFoundError(ApplicationError):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str, identifier: str | int) -> None:
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} with identifier '{identifier}' was not found.")


class ConfigurationError(ApplicationError):
    """Raised when required configuration or environment variables are missing."""


class EngineError(ApplicationError):
    """Base exception for errors originating inside any engine."""


class SignalError(EngineError):
    """Raised when signal collection or scoring fails."""


class InsightError(EngineError):
    """Raised when insight generation or ranking fails."""


class ContentError(EngineError):
    """Raised when content generation fails."""


class DistributionError(EngineError):
    """Raised when publishing or scheduling content fails."""


class AnalyticsError(EngineError):
    """Raised when metrics collection or reporting fails."""


class DatabaseError(ApplicationError):
    """Raised when a database operation fails unexpectedly."""
