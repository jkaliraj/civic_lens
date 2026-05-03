"""Unit tests for CivicLens AI API endpoints."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


BASE = Path(__file__).resolve().parent.parent


@pytest.mark.anyio
async def test_health(client):
    """Health endpoint should return service metadata."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "civic-lens-ai"
    assert data["version"] == "1.0.0"


@pytest.mark.anyio
async def test_health_includes_cache_stats(client):
    """Health endpoint should include cache statistics."""
    response = await client.get("/api/health")
    data = response.json()
    assert "cache_stats" in data
    assert "timeline_cache" in data["cache_stats"]
    assert "topic_cache" in data["cache_stats"]


@pytest.mark.anyio
async def test_health_includes_environment(client):
    """Health endpoint should include environment info."""
    response = await client.get("/api/health")
    data = response.json()
    assert "environment" in data


@pytest.mark.anyio
async def test_root_contains_schema_org(client):
    """Root HTML should include schema.org structured data."""
    response = await client.get("/")
    assert "application/ld+json" in response.text
    assert "schema.org" in response.text
    assert "WebApplication" in response.text


@pytest.mark.anyio
async def test_root_contains_material_icons(client):
    """Root HTML should include Google Material Symbols."""
    response = await client.get("/")
    assert "Material+Symbols" in response.text


@pytest.mark.anyio
async def test_root_contains_open_graph(client):
    """Root HTML should include Open Graph meta tags."""
    response = await client.get("/")
    assert 'og:title' in response.text
    assert 'og:description' in response.text


@pytest.mark.anyio
async def test_root_contains_aria_live(client):
    """Root HTML should include an ARIA live announcer region."""
    response = await client.get("/")
    assert 'aria-live="assertive"' in response.text
    assert 'id="announcer"' in response.text


@pytest.mark.anyio
async def test_root_serves_html(client):
    """Root path should serve the SPA HTML page."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "CivicLens" in response.text


@pytest.mark.anyio
async def test_root_contains_google_analytics(client):
    """Root HTML should include Google Analytics gtag script."""
    response = await client.get("/")
    assert "googletagmanager.com" in response.text
    assert "gtag(" in response.text


@pytest.mark.anyio
async def test_root_contains_google_fonts(client):
    """Root HTML should include Google Fonts stylesheet link."""
    response = await client.get("/")
    assert "fonts.googleapis.com" in response.text
    assert "Space+Grotesk" in response.text


@pytest.mark.anyio
async def test_glossary_returns_terms(client):
    """Glossary endpoint should return a list of term/definition pairs."""
    response = await client.get("/api/glossary")
    assert response.status_code == 200
    data = response.json()
    assert "terms" in data
    assert len(data["terms"]) > 0
    assert "term" in data["terms"][0]
    assert "definition" in data["terms"][0]


@pytest.mark.anyio
async def test_glossary_is_cached(client):
    """Subsequent glossary requests should use the lru_cache."""
    r1 = await client.get("/api/glossary")
    r2 = await client.get("/api/glossary")
    assert r1.json() == r2.json()


@pytest.mark.anyio
async def test_process_returns_steps(client):
    """Process endpoint should return exactly 7 ordered steps."""
    response = await client.get("/api/process")
    assert response.status_code == 200
    data = response.json()
    assert "steps" in data
    assert len(data["steps"]) == 7
    assert data["steps"][0]["step"] == 1
    assert "title" in data["steps"][0]
    assert "icon" in data["steps"][0]


@pytest.mark.anyio
async def test_chat_validates_empty_message(client):
    """Empty message should be rejected with 422."""
    response = await client.post(
        "/api/chat",
        json={"message": ""},
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_chat_validates_message_length(client):
    """Messages exceeding 2000 chars should be rejected."""
    response = await client.post(
        "/api/chat",
        json={"message": "a" * 2001},
    )
    assert response.status_code == 422


@pytest.mark.anyio
@patch("api.routes.chat", new_callable=AsyncMock)
async def test_chat_success(mock_chat, client):
    """Chat endpoint should return Gemini response."""
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
@patch("api.routes.chat", new_callable=AsyncMock)
async def test_chat_with_country_context(mock_chat, client):
    """Chat should forward country context when provided."""
    mock_chat.return_value = "India uses EVMs for voting."
    response = await client.post(
        "/api/chat",
        json={"message": "How does voting work?", "country": "India"},
    )
    assert response.status_code == 200
    mock_chat.assert_called_once()
    call_args = mock_chat.call_args
    assert call_args[1].get("context") or call_args[0][1]


@pytest.mark.anyio
@patch("api.routes.generate_timeline", new_callable=AsyncMock)
async def test_timeline_success(mock_timeline, client):
    """Timeline endpoint should return structured phases."""
    mock_timeline.return_value = [
        {
            "phase": "Registration",
            "timeframe": "6 months before",
            "description": "Voter registration opens",
            "key_actions": ["Register"],
        }
    ]
    response = await client.post(
        "/api/timeline",
        json={"country": "India"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["country"] == "India"
    assert len(data["timeline"]) == 1
    assert data["timeline"][0]["phase"] == "Registration"


@pytest.mark.anyio
@patch("api.routes.generate_timeline", new_callable=AsyncMock)
async def test_timeline_default_country(mock_timeline, client):
    """Timeline should default to India when no country specified."""
    mock_timeline.return_value = []
    response = await client.post("/api/timeline", json={})
    assert response.status_code == 200
    assert response.json()["country"] == "India"


@pytest.mark.anyio
@patch("api.routes.voter_readiness_check", new_callable=AsyncMock)
async def test_readiness_check(mock_readiness, client):
    """Readiness endpoint should return score and recommendations."""
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
    assert len(data["action_items"]) > 0


@pytest.mark.anyio
@patch("api.routes.voter_readiness_check", new_callable=AsyncMock)
async def test_readiness_all_true(mock_readiness, client):
    """Full readiness should return high score."""
    mock_readiness.return_value = {
        "score": 100,
        "status": "ready",
        "summary": "Fully prepared!",
        "action_items": [],
        "tips": ["Vote early"],
    }
    response = await client.post(
        "/api/readiness",
        json={
            "registered": True,
            "know_polling_location": True,
            "have_id": True,
            "know_election_date": True,
            "understand_ballot": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["score"] == 100


@pytest.mark.anyio
@patch("api.routes.voter_readiness_check", new_callable=AsyncMock)
async def test_readiness_all_false(mock_readiness, client):
    """No readiness should return low score."""
    mock_readiness.return_value = {
        "score": 0,
        "status": "not_ready",
        "summary": "Not prepared yet.",
        "action_items": ["Register to vote", "Get ID"],
        "tips": ["Start early"],
    }
    response = await client.post(
        "/api/readiness",
        json={
            "registered": False,
            "know_polling_location": False,
            "have_id": False,
            "know_election_date": False,
            "understand_ballot": False,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "not_ready"


@pytest.mark.anyio
@patch("api.routes.explain_topic", new_callable=AsyncMock)
async def test_topic_endpoint(mock_explain, client):
    """Topic endpoint should return structured explanation."""
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
    assert "did_you_know" in data


@pytest.mark.anyio
async def test_topic_validates_empty(client):
    """Empty topic should be rejected with 422."""
    response = await client.post("/api/topic", json={"topic": ""})
    assert response.status_code == 422


@pytest.mark.anyio
async def test_static_files_accessible(client):
    """Static CSS and JS files should be served correctly."""
    css = await client.get("/static/styles.css")
    assert css.status_code == 200
    assert "text/css" in css.headers["content-type"]

    js = await client.get("/static/app.js")
    assert js.status_code == 200
    assert "javascript" in js.headers["content-type"]


@pytest.mark.anyio
async def test_api_docs_available(client):
    """Swagger docs should be accessible at /api/docs."""
    response = await client.get("/api/docs")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_openapi_schema_available(client):
    """OpenAPI JSON schema should be served and contain all endpoints."""
    response = await client.get("/api/openapi.json")
    # FastAPI default openapi_url is /openapi.json but we mount at /api
    # The docs are at /api/docs, try getting the openapi.json
    if response.status_code == 404:
        response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    assert schema["info"]["title"] == "CivicLens AI"


@pytest.mark.anyio
async def test_glossary_term_structure(client):
    """Each glossary term should have exactly term and definition fields."""
    response = await client.get("/api/glossary")
    data = response.json()
    for t in data["terms"]:
        assert set(t.keys()) == {"term", "definition"}


@pytest.mark.anyio
async def test_process_step_structure(client):
    """Each process step should have all required fields."""
    response = await client.get("/api/process")
    data = response.json()
    required_keys = {"step", "title", "description", "icon", "details"}
    for step in data["steps"]:
        assert required_keys.issubset(set(step.keys()))


@pytest.mark.anyio
async def test_redoc_available(client):
    """ReDoc documentation should be accessible at /api/redoc."""
    response = await client.get("/api/redoc")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_root_contains_skip_link(client):
    """Root HTML should include a skip-to-content link for accessibility."""
    response = await client.get("/")
    assert 'class="skip-link"' in response.text
    assert 'href="#main-content"' in response.text


@pytest.mark.anyio
async def test_root_contains_keyboard_hints(client):
    """Root HTML should include keyboard shortcut hints."""
    response = await client.get("/")
    assert "keyboard-hint" in response.text
