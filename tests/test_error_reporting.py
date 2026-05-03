"""Unit tests for the error reporting service."""

from unittest.mock import patch

from services.error_reporting import report_error


def test_report_error_logs_fallback():
    """report_error should not raise even without the Cloud client."""
    # It should gracefully log a warning when Cloud Error Reporting
    # is unavailable (which it will be in tests).
    try:
        report_error(
            ValueError("test error"),
            context={"path": "/api/test", "method": "POST"},
        )
    except Exception:
        raise AssertionError("report_error raised an exception")


def test_report_error_with_none_context():
    """report_error should handle None context."""
    try:
        report_error(RuntimeError("another test"), context=None)
    except Exception:
        raise AssertionError("report_error raised with None context")


def test_report_error_with_empty_context():
    """report_error should handle empty context dict."""
    try:
        report_error(RuntimeError("empty ctx"), context={})
    except Exception:
        raise AssertionError("report_error raised with empty context")
