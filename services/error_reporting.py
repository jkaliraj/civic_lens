"""Google Cloud Error Reporting integration for CivicLens AI.

Captures and reports unhandled exceptions to Google Cloud Error
Reporting for production monitoring and alerting.
"""

from __future__ import annotations

import logging
import traceback
from typing import Any

logger = logging.getLogger(__name__)


def report_error(exc: Exception, context: dict[str, Any] | None = None) -> None:
    """Report an exception to Google Cloud Error Reporting.

    On Google Cloud infrastructure, uses the official client library
    to submit structured error reports. Falls back to logging locally.

    Args:
        exc: The exception instance to report.
        context: Optional dictionary with additional context (user action,
                 endpoint, request details).
    """
    error_details = {
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "traceback": traceback.format_exc(),
    }
    if context:
        error_details["context"] = context

    try:
        from google.cloud import error_reporting

        client = error_reporting.Client()
        client.report_exception()
        logger.error(
            "Error reported to Cloud Error Reporting: %s — %s",
            type(exc).__name__,
            str(exc),
        )
    except ImportError:
        logger.error(
            "Error (Cloud Error Reporting not available): %s — %s\n%s",
            type(exc).__name__,
            str(exc),
            traceback.format_exc(),
        )
    except Exception as report_exc:
        logger.error(
            "Failed to report error to Cloud Error Reporting: %s. "
            "Original error: %s — %s",
            str(report_exc),
            type(exc).__name__,
            str(exc),
        )
