"""CivicLens AI — Election Process Education Assistant.

Production-grade FastAPI application deployed on Google Cloud Run,
powered by Google Gemini 2.5 Flash via Vertex AI with integrated
Google Cloud Logging, Google Analytics, and response caching.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.middleware import (
    ErrorHandlerMiddleware,
    RateLimitMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)
from api.routes import router
from config import get_settings
from services.google_cloud import setup_cloud_logging, get_cloud_run_metadata

__all__ = ["app", "create_app"]

logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle manager.

    Initialises Google Cloud Logging on startup and emits
    Cloud Run metadata for observability.
    """
    settings = get_settings()
    setup_cloud_logging(settings.log_level)

    metadata = get_cloud_run_metadata()
    logger.info(
        "CivicLens AI started — service=%s, revision=%s, project=%s, region=%s",
        metadata["service"],
        metadata["revision"],
        metadata["project_id"],
        metadata["region"],
    )
    yield
    logger.info("CivicLens AI shutting down")


def create_app() -> FastAPI:
    """Application factory for CivicLens AI.

    Configures middleware stack (GZip, CORS, security headers,
    rate limiting), mounts API routes, and serves the static SPA.

    Returns:
        FastAPI: Fully configured application instance.
    """
    settings = get_settings()

    application = FastAPI(
        title="CivicLens AI",
        description=(
            "Election Process Education Assistant powered by "
            "Google Gemini 2.5 Flash & Vertex AI"
        ),
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    # Middleware stack (last added = first executed)
    origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )
    application.add_middleware(GZipMiddleware, minimum_size=500)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(
        RateLimitMiddleware,
        max_requests=settings.rate_limit_per_minute,
        window_seconds=60,
    )
    application.add_middleware(RequestIdMiddleware)
    application.add_middleware(ErrorHandlerMiddleware)

    # API routes
    application.include_router(router, prefix="/api")

    # Static files with cache headers
    application.mount(
        "/static",
        StaticFiles(directory=BASE / "static"),
        name="static",
    )

    @application.get("/")
    async def root() -> FileResponse:
        """Serve the main single-page application."""
        return FileResponse(BASE / "static" / "index.html")

    return application


app = create_app()
