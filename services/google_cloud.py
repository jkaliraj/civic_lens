"""Google Cloud platform service integrations for CivicLens AI.

Provides structured logging via Google Cloud Logging and Cloud Run
metadata utilities for production observability and monitoring.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def setup_cloud_logging(log_level: str = "INFO") -> None:
    """Initialize Google Cloud Logging for structured log output.

    Integrates with Python's built-in logging module to automatically
    send structured JSON logs to Google Cloud Logging when running on
    Google Cloud infrastructure (Cloud Run, GCE, GKE).

    Falls back to standard stderr logging for local development.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    try:
        import google.cloud.logging as cloud_logging

        client = cloud_logging.Client()
        client.setup_logging(log_level=numeric_level)
        logger.info(
            "Google Cloud Logging initialized",
            extra={"service": "civic-lens-ai", "component": "cloud-logging"},
        )
    except ImportError:
        logging.basicConfig(
            level=numeric_level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        logger.info("Standard logging active (google-cloud-logging not installed)")
    except Exception as exc:
        logging.basicConfig(
            level=numeric_level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        logger.warning("Cloud Logging setup failed, using standard logging: %s", exc)


def get_cloud_run_metadata() -> dict[str, str]:
    """Retrieve Google Cloud Run service metadata from environment.

    Cloud Run automatically injects K_SERVICE, K_REVISION, and
    K_CONFIGURATION environment variables into every container.

    Returns:
        Dictionary with service name, revision, configuration, project,
        and region. Values default to 'local' for local development.
    """
    return {
        "service": os.getenv("K_SERVICE", "local"),
        "revision": os.getenv("K_REVISION", "local"),
        "configuration": os.getenv("K_CONFIGURATION", "local"),
        "project_id": os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        "region": os.getenv("GOOGLE_CLOUD_LOCATION", ""),
    }


def log_structured(
    logger_instance: logging.Logger,
    level: int,
    message: str,
    **kwargs: Any,
) -> None:
    """Emit a structured log entry compatible with Cloud Logging.

    Args:
        logger_instance: Python logger to use.
        level: Logging level (e.g., logging.INFO).
        message: Log message string.
        **kwargs: Additional structured fields attached to the log entry.
    """
    logger_instance.log(
        level,
        message,
        extra={"json_fields": kwargs} if kwargs else {},
    )
