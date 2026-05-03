"""CivicLens AI — REST API Routes"""
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from ai.gemini import (
    chat,
    explain_topic,
    generate_timeline,
    voter_readiness_check,
)

logger = logging.getLogger(__name__)
router = APIRouter()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ── Request Models ────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    country: Optional[str] = Field(None, max_length=100)

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        return v.strip()


class TimelineRequest(BaseModel):
    country: str = Field("United States", min_length=1, max_length=100)


class ReadinessRequest(BaseModel):
    registered: bool
    know_polling_location: bool
    have_id: bool
    know_election_date: bool
    understand_ballot: bool
    country: Optional[str] = Field(None, max_length=100)


class TopicRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500)

    @field_validator("topic")
    @classmethod
    def sanitize_topic(cls, v: str) -> str:
        return v.strip()


# ── Health ────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"status": "healthy", "service": "civic-lens-ai"}


# ── Chat ──────────────────────────────────────────────────────

@router.post("/chat")
async def chat_endpoint(data: ChatRequest):
    context = f"User's country of interest: {data.country}" if data.country else None
    reply = await chat(data.message, context)
    return {"reply": reply}


# ── Election Timeline ─────────────────────────────────────────

@router.post("/timeline")
async def timeline_endpoint(data: TimelineRequest):
    timeline = await generate_timeline(data.country)
    return {"country": data.country, "timeline": timeline}


# ── Voter Readiness Check ────────────────────────────────────

@router.post("/readiness")
async def readiness_endpoint(data: ReadinessRequest):
    answers = {
        "registered_to_vote": data.registered,
        "knows_polling_location": data.know_polling_location,
        "has_valid_id": data.have_id,
        "knows_election_date": data.know_election_date,
        "understands_ballot": data.understand_ballot,
    }
    if data.country:
        answers["country"] = data.country
    result = await voter_readiness_check(answers)
    return result


# ── Topic Explorer ────────────────────────────────────────────

@router.post("/topic")
async def topic_endpoint(data: TopicRequest):
    result = await explain_topic(data.topic)
    return result


# ── Election Glossary (static data) ──────────────────────────

@router.get("/glossary")
async def glossary_endpoint():
    glossary_path = DATA_DIR / "glossary.json"
    if not glossary_path.exists():
        raise HTTPException(status_code=404, detail="Glossary data not found")
    with open(glossary_path, encoding="utf-8") as f:
        return json.load(f)


# ── Election Process Steps (static data) ─────────────────────

@router.get("/process")
async def process_endpoint():
    process_path = DATA_DIR / "election_process.json"
    if not process_path.exists():
        raise HTTPException(status_code=404, detail="Election process data not found")
    with open(process_path, encoding="utf-8") as f:
        return json.load(f)
