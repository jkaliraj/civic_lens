"""Gemini AI integration for CivicLens — election process education."""
import json
import logging
from typing import Optional

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_client = None

MODEL = "gemini-2.5-flash"

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


def _get_client():
    """Lazy-init Vertex AI Gemini client using ADC."""
    global _client
    if _client is None:
        project = _require_env("GOOGLE_CLOUD_PROJECT")
        location = _require_env("GOOGLE_CLOUD_LOCATION")
        _client = genai.Client(vertexai=True, project=project, location=location)
    return _client


def _require_env(key: str) -> str:
    """Return env var or raise with a clear message."""
    import os

    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val


def _clean_json(text: str):
    """Strip markdown fences and parse JSON from Gemini output."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


async def chat(message: str, context: Optional[str] = None) -> str:
    """Send a chat message to Gemini with election education context."""
    prompt_parts = [SYSTEM_INSTRUCTION]
    if context:
        prompt_parts.append(f"Additional context:\n{context}\n")
    prompt_parts.append(f"User: {message}")

    try:
        response = _get_client().models.generate_content(
            model=MODEL,
            contents=["\n".join(prompt_parts)],
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=2048,
            ),
        )
        return response.text
    except Exception as e:
        logger.exception("Gemini chat error")
        return f"I'm having trouble processing your request. Please try again. ({e})"


async def generate_timeline(country: str = "India") -> list:
    """Generate an election timeline for the specified country."""
    prompt = (
        f"{SYSTEM_INSTRUCTION}\n"
        f"Generate a typical election timeline for {country}. "
        "Return ONLY a JSON array of objects with these fields:\n"
        '[{"phase":"...","timeframe":"...","description":"...","key_actions":["..."]}]\n'
        "Include 6-8 phases from voter registration through post-election. "
        "ONLY valid JSON, no markdown."
    )
    try:
        response = _get_client().models.generate_content(
            model=MODEL,
            contents=[prompt],
            config=types.GenerateContentConfig(temperature=0.3),
        )
        return _clean_json(response.text)
    except json.JSONDecodeError:
        logger.exception("Timeline JSON parse error")
        return [{"phase": "Error", "timeframe": "N/A",
                 "description": "Could not generate timeline. Please try again.",
                 "key_actions": []}]
    except Exception as e:
        logger.exception("Timeline generation error")
        return [{"phase": "Error", "timeframe": "N/A",
                 "description": str(e), "key_actions": []}]


async def voter_readiness_check(answers: dict) -> dict:
    """Evaluate voter readiness based on quiz answers and return guidance."""
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
            model=MODEL,
            contents=[prompt],
            config=types.GenerateContentConfig(temperature=0.3),
        )
        return _clean_json(response.text)
    except json.JSONDecodeError:
        logger.exception("Readiness check JSON parse error")
        return {"score": 0, "status": "error",
                "summary": "Could not evaluate. Please try again.",
                "action_items": [], "tips": []}
    except Exception as e:
        logger.exception("Readiness check error")
        return {"score": 0, "status": "error",
                "summary": str(e), "action_items": [], "tips": []}


async def explain_topic(topic: str) -> dict:
    """Get a structured explanation of an election-related topic."""
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
            model=MODEL,
            contents=[prompt],
            config=types.GenerateContentConfig(temperature=0.5),
        )
        return _clean_json(response.text)
    except json.JSONDecodeError:
        logger.exception("Topic explain JSON parse error")
        return {"title": topic, "summary": "Could not generate explanation.",
                "key_points": [], "related_topics": [], "did_you_know": ""}
    except Exception as e:
        logger.exception("Topic explain error")
        return {"title": topic, "summary": str(e),
                "key_points": [], "related_topics": [], "did_you_know": ""}
