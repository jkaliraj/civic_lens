"""CivicLens AI — Gemini AI integration module.

Provides conversational AI, structured generation, and voter
readiness assessment powered by Google Vertex AI.
"""

from ai.gemini import (
    SYSTEM_INSTRUCTION,
    chat,
    explain_topic,
    generate_timeline,
    voter_readiness_check,
)

__all__ = [
    "SYSTEM_INSTRUCTION",
    "chat",
    "explain_topic",
    "generate_timeline",
    "voter_readiness_check",
]
