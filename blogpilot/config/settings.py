"""Centralized settings for the Phoenix Marketing Intelligence Engine.

Loads configuration from three layers (later wins):
  1. config/settings.yaml — default tunables
  2. Environment variables (.env) — secrets and overrides
  3. Runtime updates via POST /api/system/config

The YAML layer is optional — the system works with env vars alone.
"""

from __future__ import annotations

import os
import sys
import logging
from dataclasses import dataclass, field
from pathlib import Path

# Load .env before any os.getenv() calls so secrets are available at import time.
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
except ImportError:
    pass  # python-dotenv not installed — rely on process environment

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[2]
_YAML_PATH = _ROOT / "config" / "settings.yaml"

# Loaded YAML config dict (populated lazily)
_yaml_config: dict | None = None


def _load_yaml() -> dict:
    """Load settings.yaml if it exists, else return empty dict."""
    global _yaml_config
    if _yaml_config is not None:
        return _yaml_config

    if _YAML_PATH.exists():
        try:
            import yaml  # type: ignore[import]
            with open(_YAML_PATH, encoding="utf-8") as f:
                _yaml_config = yaml.safe_load(f) or {}
            logger.debug("Loaded settings from %s.", _YAML_PATH)
        except ImportError:
            logger.debug("PyYAML not installed — skipping settings.yaml.")
            _yaml_config = {}
        except Exception as exc:
            logger.warning("Failed to load settings.yaml: %s", exc)
            _yaml_config = {}
    else:
        _yaml_config = {}

    return _yaml_config


def get_yaml_value(*keys: str, default: object = None) -> object:
    """Get a nested value from settings.yaml.

    Args:
        *keys: Dot-path keys (e.g. 'engagement', 'daily_limits', 'max_likes').
        default: Fallback if key not found.

    Returns:
        The value from YAML or default.
    """
    cfg = _load_yaml()
    for key in keys:
        if isinstance(cfg, dict):
            cfg = cfg.get(key)
        else:
            return default
        if cfg is None:
            return default
    return cfg


def _app_dir() -> str:
    """Resolve writable app directory — delegates to existing paths.py if available."""
    try:
        # Re-use the frozen/dev aware resolver already in the project
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from paths import app_dir  # type: ignore[import]
        return app_dir()
    except ImportError:
        return os.path.dirname(os.path.abspath(__file__))


@dataclass
class Settings:
    """Application-wide settings resolved from environment variables."""

    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    groq_model: str = field(default_factory=lambda: os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
    groq_model_fast: str = field(default_factory=lambda: os.getenv("GROQ_MODEL_FAST", "llama-3.1-8b-instant"))

    unsplash_access_key: str = field(default_factory=lambda: os.getenv("UNSPLASH_ACCESS_KEY", ""))
    linkedin_access_token: str = field(default_factory=lambda: os.getenv("LINKEDIN_ACCESS_TOKEN", ""))
    linkedin_person_urn: str = field(default_factory=lambda: os.getenv("LINKEDIN_PERSON_URN", ""))
    linkedin_org_urn: str = field(default_factory=lambda: os.getenv("LINKEDIN_ORG_URN", ""))

    website_repo_path: str = field(
        default_factory=lambda: os.getenv("WEBSITE_REPO_PATH", r"C:\Projects\phoenixsolution")
    )

    db_path: str = field(default_factory=lambda: os.path.join(_app_dir(), "blog_marketing.db"))

    api_host: str = field(default_factory=lambda: os.getenv("API_HOST", "127.0.0.1"))
    api_port: int = field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))

    def is_groq_configured(self) -> bool:
        return bool(self.groq_api_key)

    def is_linkedin_configured(self) -> bool:
        return bool(self.linkedin_access_token)

    def is_unsplash_configured(self) -> bool:
        return bool(self.unsplash_access_key)


# Module-level singleton — created once at import time.
_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the shared Settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
        if not _settings.is_groq_configured():
            logger.warning("GROQ_API_KEY is not set — AI generation will fail.")
    return _settings


def get_groq_client():
    """Return the shared Groq client from the existing llm_client module."""
    try:
        from llm_client import get_client  # type: ignore[import]
        return get_client()
    except ImportError as exc:
        from blogpilot.common.exceptions import ConfigurationError
        raise ConfigurationError("llm_client module not found — ensure project root is in sys.path") from exc
