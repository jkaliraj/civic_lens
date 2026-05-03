"""Unit tests for CivicLens AI API endpoints."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app

BASE = Path(__file__).resolve().parent.parent


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.anyio
async def test_health(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "civic-lens-ai"


@pytest.mark.anyio
async def test_root_serves_html(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "CivicLens" in response.text


@pytest.mark.anyio
async def test_glossary_returns_terms(client):
    response = await client.get("/api/glossary")
    assert response.status_code == 200
    data = response.json()
    assert "terms" in data
    assert len(data["terms"]) > 0
    assert "term" in data["terms"][0]
    assert "definition" in data["terms"][0]


@pytest.mark.anyio
async def test_process_returns_steps(client):
    response = await client.get("/api/process")
    assert response.status_code == 200
    data = response.json()
    assert "steps" in data
    assert len(data["steps"]) == 7
    assert data["steps"][0]["step"] == 1
    assert "title" in data["steps"][0]


@pytest.mark.anyio
async def test_chat_validates_empty_message(client):
    response = await client.post(
        "/api/chat",
        json={"message": ""},
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_chat_validates_message_length(client):
    response = await client.post(
        "/api/chat",
        json={"message": "a" * 2001},
    )
    assert response.status_code == 422


@pytest.mark.anyio
@patch("api.routes.chat", new_callable=AsyncMock)
async def test_chat_success(mock_chat, client):
    mock_chat.return_value = "Elections are the foundation of democracy."
    response = await client.post(
        "/api/chat",
        json={"message": "What is an election?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "election" in data["reply"].lower()


@pytest.mark.anyio
@patch("api.routes.generate_timeline", new_callable=AsyncMock)
async def test_timeline_success(mock_timeline, client):
    mock_timeline.return_value = [
        {"phase": "Registration", "timeframe": "6 months before",
         "description": "Voter registration opens", "key_actions": ["Register"]}
    ]
    response = await client.post(
        "/api/timeline",
        json={"country": "India"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["country"] == "India"
    assert len(data["timeline"]) == 1


@pytest.mark.anyio
@patch("api.routes.voter_readiness_check", new_callable=AsyncMock)
async def test_readiness_check(mock_readiness, client):
    mock_readiness.return_value = {
        "score": 80,
        "status": "ready",
        "summary": "You are mostly ready to vote.",
        "action_items": ["Confirm polling location"],
        "tips": ["Bring water"],
    }
    response = await client.post(
        "/api/readiness",
        json={
            "registered": True,
            "know_polling_location": True,
            "have_id": True,
            "know_election_date": True,
            "understand_ballot": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 80
    assert data["status"] == "ready"


@pytest.mark.anyio
@patch("api.routes.explain_topic", new_callable=AsyncMock)
async def test_topic_endpoint(mock_explain, client):
    mock_explain.return_value = {
        "title": "Electoral College",
        "summary": "A body of electors...",
        "key_points": ["538 total electors"],
        "related_topics": ["Popular vote"],
        "did_you_know": "Fun fact",
    }
    response = await client.post(
        "/api/topic",
        json={"topic": "Electoral College"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Electoral College"
    assert len(data["key_points"]) > 0


@pytest.mark.anyio
async def test_topic_validates_empty(client):
    response = await client.post("/api/topic", json={"topic": ""})
    assert response.status_code == 422
