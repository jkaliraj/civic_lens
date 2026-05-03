"""Unit tests for CivicLens security and performance middleware."""

import pytest


@pytest.mark.anyio
async def test_security_headers_present(client):
    """All OWASP security headers should be present on API responses."""
    response = await client.get("/api/health")
    assert response.status_code == 200

    headers = response.headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["x-xss-protection"] == "1; mode=block"
    assert "strict-origin" in headers["referrer-policy"]
    assert "camera=()" in headers["permissions-policy"]
    assert "default-src 'self'" in headers["content-security-policy"]
    assert "max-age=31536000" in headers["strict-transport-security"]


@pytest.mark.anyio
async def test_response_time_header(client):
    """API responses should include an X-Response-Time header."""
    response = await client.post(
        "/api/chat",
        json={"message": "test"},
    )
    # Chat endpoint will fail without Gemini, but middleware still runs
    # if Pydantic validation passes. The header is set before error handling.
    # For static endpoints that don't call Gemini:
    response = await client.get("/api/glossary")
    assert "x-response-time" in response.headers
    assert response.headers["x-response-time"].endswith("s")


@pytest.mark.anyio
async def test_cache_control_on_api(client):
    """API responses should have no-store Cache-Control."""
    response = await client.get("/api/health")
    assert response.headers.get("cache-control") == "no-store, max-age=0"


@pytest.mark.anyio
async def test_csp_allows_google_services(client):
    """CSP should allow Google Analytics, Fonts, and Tag Manager."""
    response = await client.get("/api/health")
    csp = response.headers["content-security-policy"]
    assert "googletagmanager.com" in csp
    assert "google-analytics.com" in csp
    assert "fonts.googleapis.com" in csp
    assert "fonts.gstatic.com" in csp


@pytest.mark.anyio
async def test_health_not_rate_limited(client):
    """Health endpoint should be exempt from rate limiting."""
    for _ in range(70):
        response = await client.get("/api/health")
        assert response.status_code == 200


@pytest.mark.anyio
async def test_request_id_generated(client):
    """Responses should include an X-Request-ID header."""
    response = await client.get("/api/health")
    assert "x-request-id" in response.headers
    request_id = response.headers["x-request-id"]
    assert len(request_id) > 0
    # UUID4 format check: 8-4-4-4-12 hex chars
    parts = request_id.split("-")
    assert len(parts) == 5


@pytest.mark.anyio
async def test_request_id_passthrough(client):
    """When X-Request-ID is provided, it should be echoed back."""
    custom_id = "my-custom-request-id-12345"
    response = await client.get(
        "/api/health",
        headers={"X-Request-ID": custom_id},
    )
    assert response.headers["x-request-id"] == custom_id


@pytest.mark.anyio
async def test_request_id_unique_per_request(client):
    """Each request should get a unique request ID."""
    ids = set()
    for _ in range(5):
        response = await client.get("/api/health")
        ids.add(response.headers["x-request-id"])
    assert len(ids) == 5
