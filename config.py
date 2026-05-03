"""CivicLens AI — Centralized Application Configuration.

Loads all settings from environment variables with sensible defaults.
Uses Google Cloud-aware defaults for seamless Cloud Run deployment.
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from functools import lru_cache

__all__ = ["Settings", "get_settings"]

logger = logging.getLogger(__name__)

_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


@dataclass(frozen=True)
class Settings:
    """Immutable application settings loaded from environment variables.

    Attributes:
        project_id: Google Cloud project ID for Vertex AI.
        location: Google Cloud region (default: us-central1).
        gemini_model: Gemini model identifier for AI generation.
        allowed_origins: Comma-separated CORS origins.
        port: HTTP server port (default: 8080 for Cloud Run).
        environment: Deployment environment (development/production).
        log_level: Python logging level.
        ga_measurement_id: Google Analytics 4 measurement ID.
        enable_cloud_logging: Enable Google Cloud Logging integration.
        cache_ttl_seconds: TTL for in-memory response caching.
        rate_limit_per_minute: Max API requests per IP per minute.
    """

    project_id: str = field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT", "")
    )
    location: str = field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    )
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    )
    allowed_origins: str = field(
        default_factory=lambda: os.getenv("ALLOWED_ORIGINS", "")
    )
    port: int = field(
        default_factory=lambda: int(os.getenv("PORT", "8080"))
    )
    environment: str = field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "production")
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper()
    )

    def __post_init__(self) -> None:
        """Validate configuration values after initialization."""
        if self.log_level not in _VALID_LOG_LEVELS:
            object.__setattr__(self, "log_level", "INFO")
        if not 1 <= self.port <= 65535:
            object.__setattr__(self, "port", 8080)
        if self.cache_ttl_seconds < 0:
            object.__setattr__(self, "cache_ttl_seconds", 3600)
        if self.rate_limit_per_minute < 1:
            object.__setattr__(self, "rate_limit_per_minute", 60)
    ga_measurement_id: str = field(
        default_factory=lambda: os.getenv("GA_MEASUREMENT_ID", "")
    )
    enable_cloud_logging: bool = field(
        default_factory=lambda: os.getenv(
            "ENABLE_CLOUD_LOGGING", "true"
        ).lower() == "true"
    )
    cache_ttl_seconds: int = field(
        default_factory=lambda: int(os.getenv("CACHE_TTL", "3600"))
    )
    rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT", "60"))
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton.

    Returns:
        Settings: Frozen dataclass with all application configuration.
    """
    settings = Settings()
    logger.info(
        "Settings loaded: project=%s, region=%s, model=%s, env=%s",
        settings.project_id,
        settings.location,
        settings.gemini_model,
        settings.environment,
    )
    return settings
