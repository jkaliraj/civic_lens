"""Gemini AI integration for CivicLens — election process education.

Uses Google Vertex AI with Application Default Credentials (ADC) to
access Gemini 2.5 Flash for conversational AI, structured JSON generation,
and voter readiness assessment.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from google import genai
from google.genai import types

from config import get_settings
from services.cache import timeline_cache, topic_cache

__all__ = [
    "chat",
    "explain_topic",
    "generate_timeline",
    "voter_readiness_check",
    "SYSTEM_INSTRUCTION",
]

logger = logging.getLogger(__name__)

_client: Optional[genai.Client] = None

SYSTEM_INSTRUCTION = (
    "You are CivicLens AI, a non-partisan election education assistant. "
    "Your role is to help users understand election processes, timelines, "
    "voter registration, ballot types, and civic participation.\n\n"
    "Guidelines:\n"
    "- Always remain neutral and non-partisan\n"
    "- Provide factual, sourced information about election processes\n"
    "- Cover global election systems but can focus on specific countries when asked\n"
    "- Explain complex electoral concepts in simple, accessible language\n"
    "- Encourage civic participation without endorsing any party or candidate\n"
    "- If asked about specific candidates or party opinions, politely redirect "
    "to factual process information\n"
    "- Use structured formatting: bullet points, numbered steps, tables\n"
    "- When discussing timelines, be specific about dates and deadlines\n"
)


def _get_client() -> genai.Client:
    """Lazy-initialise the Vertex AI Gemini client using ADC.

    Creates a single client instance reused across all requests
    to optimise connection pooling and authentication overhead.

    Returns:
        genai.Client: Authenticated Vertex AI Gemini client.

    Raises:
        RuntimeError: If required Google Cloud env vars are missing.
    """
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.project_id:
            raise RuntimeError(
                "Missing required environment variable: GOOGLE_CLOUD_PROJECT"
            )
        _client = genai.Client(
            vertexai=True,
            project=settings.project_id,
            location=settings.location,
        )
        logger.info(
            "Vertex AI client initialised: project=%s, region=%s",
            settings.project_id,
            settings.location,
        )
    return _client


def _clean_json(text: str) -> Any:
    """Strip markdown fences and parse JSON from Gemini output.

    Handles common Gemini response patterns where JSON is wrapped
    in triple-backtick code fences with optional language tags.

    Args:
        text: Raw text response from Gemini.

    Returns:
        Parsed JSON as a Python dict or list.

    Raises:
        json.JSONDecodeError: If the cleaned text is not valid JSON.
    """
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


async def chat(message: str, context: Optional[str] = None) -> str:
    """Send a chat message to Gemini with election education context.

    Args:
        message: User's question or statement.
        context: Optional additional context (e.g. country of interest).

    Returns:
        Gemini's text response as a string.
    """
    settings = get_settings()
    prompt_parts = [SYSTEM_INSTRUCTION]
    if context:
        prompt_parts.append(f"Additional context:\n{context}\n")
    prompt_parts.append(f"User: {message}")

    try:
        response = _get_client().models.generate_content(
            model=settings.gemini_model,
            contents=["\n".join(prompt_parts)],
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=2048,
            ),
        )
        logger.info("Chat response generated: %d chars", len(response.text))
        return response.text
    except Exception as exc:
        logger.exception("Gemini chat error")
        return (
            "I'm having trouble processing your request. "
            f"Please try again. ({exc})"
        )


async def generate_timeline(country: str = "India") -> list[dict[str, Any]]:
    """Generate an election timeline for the specified country.

    Results are cached in-memory to reduce redundant Vertex AI calls
    for identical country queries within the TTL window.

    Args:
        country: Name of the country (default: India).

    Returns:
        List of timeline phase dictionaries.
    """
    # Check cache first
    cached = timeline_cache.get("timeline", country.lower())
    if cached is not None:
        logger.info("Timeline cache hit for country=%s", country)
        return cached

    settings = get_settings()
    prompt = (
        f"{SYSTEM_INSTRUCTION}\n"
        f"Generate a typical election timeline for {country}. "
        "Return ONLY a JSON array of objects with these fields:\n"
        '[{"phase":"...","timeframe":"...","description":"...",'
        '"key_actions":["..."]}]\n'
        "Include 6-8 phases from voter registration through post-election. "
        "ONLY valid JSON, no markdown."
    )
    try:
        response = _get_client().models.generate_content(
            model=settings.gemini_model,
            contents=[prompt],
            config=types.GenerateContentConfig(temperature=0.3),
        )
        result = _clean_json(response.text)
        timeline_cache.set(result, "timeline", country.lower())
        logger.info("Timeline generated for %s: %d phases", country, len(result))
        return result
    except json.JSONDecodeError:
        logger.exception("Timeline JSON parse error for %s", country)
        return [
            {
                "phase": "Error",
                "timeframe": "N/A",
                "description": "Could not generate timeline. Please try again.",
                "key_actions": [],
            }
        ]
    except Exception as exc:
        logger.exception("Timeline generation error for %s", country)
        return [
            {
                "phase": "Error",
                "timeframe": "N/A",
                "description": str(exc),
                "key_actions": [],
            }
        ]


async def voter_readiness_check(answers: dict[str, Any]) -> dict[str, Any]:
    """Evaluate voter readiness based on quiz answers and return guidance.

    Args:
        answers: Dictionary of readiness question responses.

    Returns:
        Dictionary with score, status, summary, action_items, and tips.
    """
    settings = get_settings()
    prompt = (
        f"{SYSTEM_INSTRUCTION}\n"
        "A user completed a voter readiness self-check with these answers:\n"
        f"{json.dumps(answers, indent=2)}\n\n"
        "Evaluate their readiness and return ONLY a JSON object:\n"
        '{"score":0-100,"status":"ready|needs_action|not_ready",'
        '"summary":"...","action_items":["..."],"tips":["..."]}\n'
        "Be encouraging and helpful. ONLY valid JSON, no markdown."
    )
    try:
        response = _get_client().models.generate_content(
            model=settings.gemini_model,
            contents=[prompt],
            config=types.GenerateContentConfig(temperature=0.3),
        )
        return _clean_json(response.text)
    except json.JSONDecodeError:
        logger.exception("Readiness check JSON parse error")
        return {
            "score": 0,
            "status": "error",
            "summary": "Could not evaluate. Please try again.",
            "action_items": [],
            "tips": [],
        }
    except Exception as exc:
        logger.exception("Readiness check error")
        return {
            "score": 0,
            "status": "error",
            "summary": str(exc),
            "action_items": [],
            "tips": [],
        }


async def explain_topic(topic: str) -> dict[str, Any]:
    """Get a structured explanation of an election-related topic.

    Results are cached in-memory to reduce Vertex AI calls for
    repeated topic queries.

    Args:
        topic: Election-related topic to explain.

    Returns:
        Dictionary with title, summary, key_points, related_topics,
        and did_you_know fields.
    """
    cached = topic_cache.get("topic", topic.lower())
    if cached is not None:
        logger.info("Topic cache hit for topic=%s", topic)
        return cached

    settings = get_settings()
    prompt = (
        f"{SYSTEM_INSTRUCTION}\n"
        f"Explain the election topic: '{topic}'\n"
        "Return ONLY a JSON object:\n"
        '{"title":"...","summary":"...","key_points":["..."],'
        '"related_topics":["..."],"did_you_know":"..."}\n'
        "Make it educational and engaging. ONLY valid JSON, no markdown."
    )
    try:
        response = _get_client().models.generate_content(
            model=settings.gemini_model,
            contents=[prompt],
            config=types.GenerateContentConfig(temperature=0.5),
        )
        result = _clean_json(response.text)
        topic_cache.set(result, "topic", topic.lower())
        logger.info("Topic explained: %s", topic)
        return result
    except json.JSONDecodeError:
        logger.exception("Topic explain JSON parse error for %s", topic)
        return {
            "title": topic,
            "summary": "Could not generate explanation.",
            "key_points": [],
            "related_topics": [],
            "did_you_know": "",
        }
    except Exception as exc:
        logger.exception("Topic explain error for %s", topic)
        return {
            "title": topic,
            "summary": str(exc),
            "key_points": [],
            "related_topics": [],
            "did_you_know": "",
        }
