"""Shared test configuration and fixtures for CivicLens AI."""

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.fixture
def anyio_backend():
    """Configure anyio to use the asyncio backend for all tests."""
    return "asyncio"


@pytest.fixture
async def client():
    """Create an async HTTP test client bound to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
