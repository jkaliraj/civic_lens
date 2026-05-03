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
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai.gemini import (
    chat,
    explain_topic,
    generate_timeline,
    voter_readiness_check,
)
from services.cache import timeline_cache, topic_cache
from services.google_cloud import get_cloud_run_metadata

__all__ = ["router"]

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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"message": "How does voter registration work in India?"},
                {"message": "Explain the electoral college", "country": "USA"},
            ]
        }
    )

    message: str = Field(
        ..., min_length=1, max_length=2000, description="User question about elections"
    )
    country: Optional[str] = Field(
        None, max_length=100, description="Country context for localised answers"
    )

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

    reply: str = Field(..., description="AI-generated response about elections")


class TimelineRequest(BaseModel):
    """Request model for the election timeline endpoint.

    Attributes:
        country: Target country for timeline generation.
    """

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"country": "India"}, {"country": "USA"}]}
    )

    country: str = Field(
        "India", min_length=1, max_length=100, description="Country for timeline generation"
    )


class TimelineResponse(BaseModel):
    """Response model for the election timeline endpoint."""

    country: str = Field(..., description="Country the timeline was generated for")
    timeline: list[dict[str, Any]] = Field(
        ..., description="List of election phase objects"
    )


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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "registered": True,
                    "know_polling_location": True,
                    "have_id": True,
                    "know_election_date": False,
                    "understand_ballot": False,
                }
            ]
        }
    )

    registered: bool = Field(..., description="Whether the user is registered to vote")
    know_polling_location: bool = Field(
        ..., description="Whether they know their polling station"
    )
    have_id: bool = Field(..., description="Whether they have a valid voter ID")
    know_election_date: bool = Field(
        ..., description="Whether they know the election date"
    )
    understand_ballot: bool = Field(
        ..., description="Whether they understand the ballot format"
    )
    country: Optional[str] = Field(
        None, max_length=100, description="Optional country context"
    )


class ReadinessResponse(BaseModel):
    """Response model for the voter readiness check."""

    score: int = Field(..., ge=0, le=100, description="Readiness score 0-100")
    status: str = Field(..., description="Readiness status: ready, needs_action, not_ready")
    summary: str = Field(..., description="Human-readable readiness summary")
    action_items: list[str] = Field(default_factory=list, description="Steps to improve readiness")
    tips: list[str] = Field(default_factory=list, description="Helpful voting tips")


class TopicRequest(BaseModel):
    """Request model for the topic explainer endpoint.

    Attributes:
        topic: Election-related topic to explain (1-500 chars).
    """

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"topic": "Electoral College"}, {"topic": "Gerrymandering"}]}
    )

    topic: str = Field(
        ..., min_length=1, max_length=500, description="Election topic to explain"
    )

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

    title: str = Field(..., description="Topic title")
    summary: str = Field(..., description="Educational summary")
    key_points: list[str] = Field(default_factory=list, description="Key educational points")
    related_topics: list[str] = Field(default_factory=list, description="Related election topics")
    did_you_know: str = Field(default="", description="Fun fact about the topic")


class GlossaryTermModel(BaseModel):
    """A single glossary term and its definition."""

    term: str = Field(..., description="Electoral term")
    definition: str = Field(..., description="Plain-language definition")


class GlossaryResponse(BaseModel):
    """Response model for the glossary endpoint."""

    terms: list[GlossaryTermModel] = Field(..., description="List of glossary terms")


class ProcessStepModel(BaseModel):
    """A single step in the election process."""

    step: int = Field(..., description="Step number")
    title: str = Field(..., description="Step title")
    description: str = Field(..., description="Step description")
    icon: str = Field(..., description="Step icon emoji")
    details: list[str] = Field(default_factory=list, description="Detailed points")


class ProcessResponse(BaseModel):
    """Response model for the election process endpoint."""

    title: str = Field(..., description="Process guide title")
    steps: list[ProcessStepModel] = Field(..., description="Ordered list of election steps")


class HealthResponse(BaseModel):
    """Response model for the health check endpoint."""

    status: str = Field(..., description="Service health status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Application version")
    environment: str = Field(default="", description="Deployment environment")
    cache_stats: dict[str, dict[str, int]] = Field(
        default_factory=dict, description="Cache performance statistics"
    )


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


@router.get("/glossary", response_model=GlossaryResponse)
async def glossary_endpoint() -> GlossaryResponse:
    """Return the full election terminology glossary.

    Data is loaded from disk once and cached in memory for
    subsequent requests.
    """
    data = _load_glossary()
    return GlossaryResponse(**data)


# ── Election Process Steps (static data) ─────────────────────


@router.get("/process", response_model=ProcessResponse)
async def process_endpoint() -> ProcessResponse:
    """Return the step-by-step election process guide.

    Data is loaded from disk once and cached in memory for
    subsequent requests.
    """
    data = _load_process()
    return ProcessResponse(**data)
