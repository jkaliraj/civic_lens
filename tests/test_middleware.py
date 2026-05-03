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


@pytest.mark.anyio
async def test_cross_origin_headers(client):
    """Responses should include Cross-Origin security headers."""
    response = await client.get("/api/health")
    assert response.headers.get("cross-origin-opener-policy") == "same-origin"
    assert response.headers.get("cross-origin-resource-policy") == "same-origin"


@pytest.mark.anyio
async def test_rate_limit_returns_429(client):
    """Exceeding rate limit should return HTTP 429 with Retry-After."""
    # Use a low-traffic endpoint; send > max_requests hits
    # Default max is 60/min; we skip health (exempt), so hit /api/glossary
    responses = []
    for _ in range(65):
        r = await client.get("/api/glossary")
        responses.append(r)
    # At least the last few should be 429
    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes
    # Verify Retry-After on a 429
    for r in responses:
        if r.status_code == 429:
            assert "retry-after" in r.headers
            break


@pytest.mark.anyio
async def test_hsts_includes_subdomains(client):
    """HSTS header should include includeSubDomains directive."""
    response = await client.get("/api/health")
    hsts = response.headers.get("strict-transport-security", "")
    assert "includeSubDomains" in hsts
    assert "max-age=31536000" in hsts


@pytest.mark.anyio
async def test_permissions_policy_complete(client):
    """Permissions-Policy should disable camera, microphone, geolocation, payment."""
    response = await client.get("/api/health")
    pp = response.headers.get("permissions-policy", "")
    assert "camera=()" in pp
    assert "microphone=()" in pp
    assert "geolocation=()" in pp
    assert "payment=()" in pp
