"""CivicLens AI — REST API Routes.

Defines all HTTP endpoints for the CivicLens election education
platform, including AI chat, timeline generation, voter readiness
assessment, and static data retrieval.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from ai.gemini import (
    chat,
    explain_topic,
    generate_timeline,
    voter_readiness_check,
)
from services.cache import timeline_cache, topic_cache
from services.google_cloud import get_cloud_run_metadata

logger = logging.getLogger(__name__)
router = APIRouter()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ── Request / Response Models ─────────────────────────────────


class ChatRequest(BaseModel):
    """Request model for the AI chat endpoint.

    Attributes:
        message: User question about elections (1-2000 chars).
        country: Optional country context for localised answers.
    """

    message: str = Field(..., min_length=1, max_length=2000)
    country: Optional[str] = Field(None, max_length=100)

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        """Strip leading/trailing whitespace from user messages."""
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty or whitespace only")
        return v


class ChatResponse(BaseModel):
    """Response model for the AI chat endpoint."""

    reply: str


class TimelineRequest(BaseModel):
    """Request model for the election timeline endpoint.

    Attributes:
        country: Target country for timeline generation.
    """

    country: str = Field("India", min_length=1, max_length=100)


class TimelineResponse(BaseModel):
    """Response model for the election timeline endpoint."""

    country: str
    timeline: list[dict[str, Any]]


class ReadinessRequest(BaseModel):
    """Request model for the voter readiness check endpoint.

    Attributes:
        registered: Whether the user is registered to vote.
        know_polling_location: Whether they know their polling station.
        have_id: Whether they have a valid voter ID.
        know_election_date: Whether they know the election date.
        understand_ballot: Whether they understand the ballot format.
        country: Optional country context.
    """

    registered: bool
    know_polling_location: bool
    have_id: bool
    know_election_date: bool
    understand_ballot: bool
    country: Optional[str] = Field(None, max_length=100)


class ReadinessResponse(BaseModel):
    """Response model for the voter readiness check."""

    score: int
    status: str
    summary: str
    action_items: list[str] = []
    tips: list[str] = []


class TopicRequest(BaseModel):
    """Request model for the topic explainer endpoint.

    Attributes:
        topic: Election-related topic to explain (1-500 chars).
    """

    topic: str = Field(..., min_length=1, max_length=500)

    @field_validator("topic")
    @classmethod
    def sanitize_topic(cls, v: str) -> str:
        """Strip leading/trailing whitespace from topic input."""
        v = v.strip()
        if not v:
            raise ValueError("Topic cannot be empty or whitespace only")
        return v


class TopicResponse(BaseModel):
    """Response model for the topic explainer."""

    title: str
    summary: str
    key_points: list[str] = []
    related_topics: list[str] = []
    did_you_know: str = ""


class HealthResponse(BaseModel):
    """Response model for the health check endpoint."""

    status: str
    service: str
    version: str
    environment: str = ""
    cache_stats: dict[str, dict[str, int]] = {}


# ── Cached data loaders ──────────────────────────────────────


@lru_cache(maxsize=1)
def _load_glossary() -> dict[str, Any]:
    """Load and cache glossary data from disk.

    Returns:
        Parsed glossary JSON.

    Raises:
        HTTPException: If glossary file is not found.
    """
    glossary_path = DATA_DIR / "glossary.json"
    if not glossary_path.exists():
        raise HTTPException(status_code=404, detail="Glossary data not found")
    with open(glossary_path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_process() -> dict[str, Any]:
    """Load and cache election process data from disk.

    Returns:
        Parsed election process JSON.

    Raises:
        HTTPException: If process file is not found.
    """
    process_path = DATA_DIR / "election_process.json"
    if not process_path.exists():
        raise HTTPException(status_code=404, detail="Election process data not found")
    with open(process_path, encoding="utf-8") as f:
        return json.load(f)


# ── Health ────────────────────────────────────────────────────


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Service health check for Cloud Run and monitoring.

    Returns:
        HealthResponse with service status, name, version,
        environment metadata, and cache statistics.
    """
    metadata = get_cloud_run_metadata()
    return HealthResponse(
        status="healthy",
        service="civic-lens-ai",
        version="1.0.0",
        environment=metadata.get("service", "local"),
        cache_stats={
            "timeline_cache": timeline_cache.stats,
            "topic_cache": topic_cache.stats,
        },
    )


# ── Chat ──────────────────────────────────────────────────────


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(data: ChatRequest) -> ChatResponse:
    """AI-powered election education chat.

    Accepts a user message and returns a contextual response
    from Gemini 2.5 Flash via Vertex AI.
    """
    context = f"User's country of interest: {data.country}" if data.country else None
    logger.info("Chat request: %d chars", len(data.message))
    reply = await chat(data.message, context)
    return ChatResponse(reply=reply)


# ── Election Timeline ─────────────────────────────────────────


@router.post("/timeline", response_model=TimelineResponse)
async def timeline_endpoint(data: TimelineRequest) -> TimelineResponse:
    """Generate an AI-powered election timeline for a country.

    Uses Gemini to produce a structured timeline of election phases
    with caching to optimise repeated queries.
    """
    logger.info("Timeline request: country=%s", data.country)
    timeline = await generate_timeline(data.country)
    return TimelineResponse(country=data.country, timeline=timeline)


# ── Voter Readiness Check ────────────────────────────────────


@router.post("/readiness", response_model=ReadinessResponse)
async def readiness_endpoint(data: ReadinessRequest) -> ReadinessResponse:
    """AI-powered voter readiness self-assessment.

    Evaluates user responses and returns a readiness score with
    personalised action items and tips.
    """
    answers: dict[str, Any] = {
        "registered_to_vote": data.registered,
        "knows_polling_location": data.know_polling_location,
        "has_valid_id": data.have_id,
        "knows_election_date": data.know_election_date,
        "understands_ballot": data.understand_ballot,
    }
    if data.country:
        answers["country"] = data.country
    logger.info("Readiness check request")
    result = await voter_readiness_check(answers)
    return ReadinessResponse(**result)


# ── Topic Explorer ────────────────────────────────────────────


@router.post("/topic", response_model=TopicResponse)
async def topic_endpoint(data: TopicRequest) -> TopicResponse:
    """AI-powered election topic explainer.

    Returns a structured educational explanation with key points,
    related topics, and fun facts.
    """
    logger.info("Topic request: %s", data.topic)
    result = await explain_topic(data.topic)
    return TopicResponse(**result)


# ── Election Glossary (static data) ──────────────────────────


@router.get("/glossary")
async def glossary_endpoint() -> dict[str, Any]:
    """Return the full election terminology glossary.

    Data is loaded from disk once and cached in memory for
    subsequent requests.
    """
    return _load_glossary()


# ── Election Process Steps (static data) ─────────────────────


@router.get("/process")
async def process_endpoint() -> dict[str, Any]:
    """Return the step-by-step election process guide.

    Data is loaded from disk once and cached in memory for
    subsequent requests.
    """
    return _load_process()
