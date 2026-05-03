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
    """Create an async HTTP test client bound to the FastAPI app.

    Clears rate-limiter state before each test so that tests don't
    interfere with one another.
    """
    # Walk the built middleware stack and clear rate-limit state
    _clear_rate_limit_state(app.middleware_stack)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _clear_rate_limit_state(obj) -> None:
    """Recursively walk the ASGI middleware stack and clear rate-limiter state."""
    if obj is None:
        return
    if hasattr(obj, "_requests"):
        obj._requests.clear()
    # Starlette wraps middleware; try both .app and .dispatch_func
    for attr in ("app", "dispatch_func"):
        child = getattr(obj, attr, None)
        if child is not None and child is not obj:
            _clear_rate_limit_state(child)
