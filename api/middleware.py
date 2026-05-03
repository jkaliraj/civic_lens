"""CivicLens AI — Security and performance middleware.

Provides HTTP security headers (OWASP best practices), sliding-window
rate limiting per client IP, request ID tracing, and global error handling.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from services.error_reporting import report_error

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request for traceability.

    Uses the incoming X-Request-ID header if present (e.g. from a load
    balancer), otherwise generates a UUID4. The ID is propagated in the
    response headers and available in the request state for logging.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Inject request ID into request state and response headers."""
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Global error handler that catches unhandled exceptions.

    Returns a structured JSON error response and reports the exception
    to Google Cloud Error Reporting for production monitoring.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Catch unhandled exceptions and return a safe JSON response."""
        try:
            return await call_next(request)
        except Exception as exc:
            request_id = getattr(request.state, "request_id", "unknown")
            logger.exception(
                "Unhandled error on %s %s [request_id=%s]",
                request.method,
                request.url.path,
                request_id,
            )
            report_error(exc, context={
                "method": request.method,
                "path": str(request.url.path),
                "request_id": request_id,
            })
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "An internal error occurred. Please try again.",
                    "request_id": request_id,
                },
            )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add OWASP-recommended security headers to every HTTP response.

    Headers applied:
        - X-Content-Type-Options: Prevent MIME sniffing.
        - X-Frame-Options: Block clickjacking.
        - X-XSS-Protection: Enable browser XSS filter.
        - Referrer-Policy: Limit referrer leakage.
        - Permissions-Policy: Disable sensitive browser features.
        - Content-Security-Policy: Restrict resource loading origins.
        - Strict-Transport-Security: Enforce HTTPS.
        - Cache-Control: Prevent sensitive data caching.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and attach security headers to response."""
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://www.googletagmanager.com "
            "https://www.google-analytics.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self' https://www.google-analytics.com "
            "https://analytics.google.com"
        )
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

        # Cache-Control for API responses (not static files)
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store, max-age=0"

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter per client IP address.

    Rejects requests exceeding the configured threshold with HTTP 429
    and a Retry-After header.

    Args:
        app: The ASGI application.
        max_requests: Maximum requests allowed per window.
        window_seconds: Duration of the sliding window in seconds.
    """

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next) -> Response:
        """Check rate limit, then forward or reject the request."""
        # Skip rate limiting for health checks and static files
        if request.url.path in ("/api/health", "/") or request.url.path.startswith(
            "/static"
        ):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # Prune timestamps outside the current window
        self._requests[client_ip] = [
            t
            for t in self._requests[client_ip]
            if now - t < self.window_seconds
        ]

        if len(self._requests[client_ip]) >= self.max_requests:
            logger.warning(
                "Rate limit exceeded: ip=%s, count=%d",
                client_ip,
                len(self._requests[client_ip]),
            )
            return Response(
                content='{"detail":"Rate limit exceeded. Please try again later."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(self.window_seconds)},
            )

        self._requests[client_ip].append(now)

        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        logger.info(
            "%s %s — %d (%0.3fs)",
            request.method,
            request.url.path,
            response.status_code,
            duration,
        )
        return response
