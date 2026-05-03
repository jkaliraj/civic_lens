"""Unit tests for CivicLens configuration module."""

import os
from unittest.mock import patch

import pytest

from config import Settings, get_settings


class TestSettings:
    """Test suite for the Settings dataclass."""

    def test_default_values(self):
        """Settings should have sensible defaults when env vars are unset."""
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert s.location == "us-central1"
            assert s.gemini_model == "gemini-2.5-flash"
            assert s.port == 8080
            assert s.environment == "production"
            assert s.log_level == "INFO"
            assert s.enable_cloud_logging is True
            assert s.cache_ttl_seconds == 3600
            assert s.rate_limit_per_minute == 60

    def test_env_override(self):
        """Settings should read from environment variables."""
        env = {
            "GOOGLE_CLOUD_PROJECT": "test-project",
            "GOOGLE_CLOUD_LOCATION": "europe-west1",
            "GEMINI_MODEL": "gemini-2.0-flash",
            "PORT": "9090",
            "ENVIRONMENT": "development",
            "LOG_LEVEL": "DEBUG",
            "RATE_LIMIT": "100",
            "CACHE_TTL": "600",
        }
        with patch.dict(os.environ, env, clear=True):
            s = Settings()
            assert s.project_id == "test-project"
            assert s.location == "europe-west1"
            assert s.gemini_model == "gemini-2.0-flash"
            assert s.port == 9090
            assert s.environment == "development"
            assert s.log_level == "DEBUG"
            assert s.rate_limit_per_minute == 100
            assert s.cache_ttl_seconds == 600

    def test_settings_are_frozen(self):
        """Settings should be immutable once created."""
        s = Settings()
        with pytest.raises(AttributeError):
            s.port = 9999  # type: ignore[misc]

    def test_cloud_logging_flag(self):
        """Cloud logging flag should parse boolean-like strings."""
        with patch.dict(os.environ, {"ENABLE_CLOUD_LOGGING": "false"}, clear=True):
            s = Settings()
            assert s.enable_cloud_logging is False

        with patch.dict(os.environ, {"ENABLE_CLOUD_LOGGING": "TRUE"}, clear=True):
            s = Settings()
            assert s.enable_cloud_logging is True


class TestGetSettings:
    """Test suite for the cached get_settings function."""

    def test_returns_settings_instance(self):
        """get_settings should return a Settings object."""
        get_settings.cache_clear()
        s = get_settings()
        assert isinstance(s, Settings)

    def test_caching(self):
        """Subsequent calls should return the same cached instance."""
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
