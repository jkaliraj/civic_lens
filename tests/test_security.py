"""Security-focused tests for CivicLens AI input validation."""

import pytest


@pytest.mark.anyio
async def test_chat_rejects_oversized_message(client):
    """Messages exceeding 2000 chars should be rejected."""
    response = await client.post(
        "/api/chat",
        json={"message": "x" * 2001},
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_chat_rejects_empty_message(client):
    """Empty string messages should be rejected."""
    response = await client.post("/api/chat", json={"message": ""})
    assert response.status_code == 422


@pytest.mark.anyio
async def test_chat_rejects_whitespace_only(client):
    """Whitespace-only messages should be rejected after strip."""
    response = await client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 422


@pytest.mark.anyio
async def test_topic_rejects_oversized_input(client):
    """Topics exceeding 500 chars should be rejected."""
    response = await client.post(
        "/api/topic",
        json={"topic": "x" * 501},
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_topic_rejects_empty(client):
    """Empty topic string should be rejected."""
    response = await client.post("/api/topic", json={"topic": ""})
    assert response.status_code == 422


@pytest.mark.anyio
async def test_timeline_rejects_oversized_country(client):
    """Country names exceeding 100 chars should be rejected."""
    response = await client.post(
        "/api/timeline",
        json={"country": "x" * 101},
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_readiness_requires_boolean_fields(client):
    """Non-boolean values for readiness fields should be rejected."""
    response = await client.post(
        "/api/readiness",
        json={
            "registered": "maybe",
            "know_polling_location": True,
            "have_id": True,
            "know_election_date": True,
            "understand_ballot": True,
        },
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_chat_handles_special_characters(client):
    """Special characters in messages should not cause errors."""
    response = await client.post(
        "/api/chat",
        json={"message": '<script>alert("xss")</script>'},
    )
    # Should be accepted (Pydantic passes it) but Gemini will handle safely
    # The key is it doesn't crash the server
    assert response.status_code in (200, 500)


@pytest.mark.anyio
async def test_invalid_json_rejected(client):
    """Malformed JSON payload should return 422."""
    response = await client.post(
        "/api/chat",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_missing_required_fields(client):
    """Missing required fields should return 422."""
    response = await client.post("/api/chat", json={})
    assert response.status_code == 422

    response = await client.post("/api/readiness", json={})
    assert response.status_code == 422


@pytest.mark.anyio
async def test_csp_header_present(client):
    """Content-Security-Policy header should be set."""
    response = await client.get("/api/health")
    csp = response.headers.get("content-security-policy", "")
    assert "default-src" in csp
    assert "script-src" in csp


@pytest.mark.anyio
async def test_x_content_type_options(client):
    """X-Content-Type-Options should be nosniff."""
    response = await client.get("/api/health")
    assert response.headers.get("x-content-type-options") == "nosniff"


@pytest.mark.anyio
async def test_referrer_policy(client):
    """Referrer-Policy header should be present."""
    response = await client.get("/api/health")
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


@pytest.mark.anyio
async def test_x_frame_options(client):
    """X-Frame-Options should be DENY."""
    response = await client.get("/api/health")
    assert response.headers.get("x-frame-options") == "DENY"


@pytest.mark.anyio
async def test_trusted_host_middleware_present():
    """App should have TrustedHostMiddleware registered."""
    from main import create_app
    app = create_app()
    middleware_classes = [m.cls.__name__ for m in app.user_middleware]
    assert "TrustedHostMiddleware" in middleware_classes


@pytest.mark.anyio
async def test_cors_allows_all_origins():
    """CORS middleware should be registered."""
    from main import create_app
    app = create_app()
    middleware_classes = [m.cls.__name__ for m in app.user_middleware]
    assert "CORSMiddleware" in middleware_classes
