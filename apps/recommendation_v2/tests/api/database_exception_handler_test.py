"""
Tests for the ``database_exception_handler`` exception handler registered on the FastAPI app.

Scenarios covered
-----------------
1.  GET request  → HTTP 503, standard body, logger called with correct fields (method, body=None,
    route_template, error_type without ``orig``).
2.  POST request → HTTP 503, logger reads and logs the request body.
3.  Wrapped exception (``exc.orig``) → ``database_error_type`` reflects the underlying class name.
4.  No matched route → ``route_template`` falls back to ``request.url.path``.
"""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi import Request
from fastapi import status
from httpx import ASGITransport
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import SQLAlchemyError

from main import database_exception_handler


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_app(path: str, method: str, exc: Exception | None = None) -> FastAPI:
    """Build a minimal FastAPI app that raises *exc* (default: SQLAlchemyError) on *path*."""
    if exc is None:
        exc = SQLAlchemyError("db crash")

    async def always_raise(request: Request):
        raise exc

    app = FastAPI()
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    app.add_api_route(path, always_raise, methods=[method])
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_request_returns_503_with_correct_log():
    """
    A SQLAlchemyError on a GET endpoint must:
    - return HTTP 503 with the standard error body
    - call logger.error once with method=GET, body=None, the registered route_template,
      and the exception class name as database_error_type (no ``orig`` attribute).
    """
    app = _make_app("/test-get", "GET")

    with patch("main.logger") as mock_logger:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test-get")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"detail": "Service temporarily unavailable. Please try again later."}

    mock_logger.error.assert_called_once()
    extra = mock_logger.error.call_args.kwargs["extra"]
    assert extra["method"] == "GET"
    assert extra["body"] is None
    assert extra["route_template"] == "/test-get"
    assert extra["database_error_type"] == "SQLAlchemyError"


@pytest.mark.asyncio
async def test_post_request_returns_503_and_logs_body():
    """
    A SQLAlchemyError on a POST endpoint must return HTTP 503 and log the request body.
    """
    payload = {"user_id": 42}
    app = _make_app("/test-post", "POST")

    with patch("main.logger") as mock_logger:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/test-post", json=payload)

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    extra = mock_logger.error.call_args.kwargs["extra"]
    assert extra["method"] == "POST"
    assert extra["body"] == payload


@pytest.mark.asyncio
async def test_error_type_uses_orig_when_present():
    """
    When the SQLAlchemyError wraps a driver-level timeout via ``exc.orig``
    (e.g. asyncpg raises ``QueryCanceledError: canceling statement due to statement timeout``
    on a slow SELECT, which SQLAlchemy rewraps as OperationalError),
    ``database_error_type`` must reflect the underlying exception class, not the wrapper.
    """
    # Simulate a statement timeout from the asyncpg driver on a slow read query.
    driver_timeout = TimeoutError("canceling statement due to statement timeout")
    app = _make_app("/test-orig", "GET", exc=OperationalError("SELECT ...", {}, driver_timeout))

    with patch("main.logger") as mock_logger:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/test-orig")

    extra = mock_logger.error.call_args.kwargs["extra"]
    assert extra["database_error_type"] == "TimeoutError"
