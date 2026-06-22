"""
Unit tests for GCPTraceMiddleware.

These tests mount the middleware on a minimal Starlette app and verify that
``cloud_trace_context`` and ``http_request_context`` are correctly populated
(and then reset) for each request.

``call_id_context`` is intentionally **not** tested here: it is the
responsibility of each pipeline controller to set it with a business-scoped UUID.
"""

import asyncio
from http import HTTPStatus

import pytest
import pytest_asyncio
from httpx import ASGITransport
from httpx import AsyncClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from middleware.gcp_trace import GCPTraceMiddleware
from services.logger import cloud_trace_context
from services.logger import http_request_context


# ---------------------------------------------------------------------------
# Minimal Starlette test application
# ---------------------------------------------------------------------------


async def _capture_endpoint(request: Request) -> JSONResponse:
    """Return the current contextvar values so assertions can inspect them."""
    return JSONResponse(
        {
            "cloud_trace": cloud_trace_context.get(),
            "http_request": http_request_context.get(None),
        }
    )


def _build_test_app() -> Starlette:
    app = Starlette(routes=[Route("/capture", _capture_endpoint)])
    app.add_middleware(GCPTraceMiddleware)  # ty: ignore[invalid-argument-type]
    return app


@pytest_asyncio.fixture()
async def test_client():
    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trace_header_is_stored_in_context(test_client):
    """Full X-Cloud-Trace-Context header is forwarded verbatim to cloud_trace_context."""
    trace_value = "abc123def456/789;o=1"

    response = await test_client.get("/capture", headers={"X-Cloud-Trace-Context": trace_value})

    assert response.status_code == HTTPStatus.OK
    assert response.json()["cloud_trace"] == trace_value


@pytest.mark.asyncio
async def test_cloud_trace_is_empty_when_no_trace_header(test_client):
    """cloud_trace_context is an empty string when the header is absent."""
    response = await test_client.get("/capture")

    assert response.json()["cloud_trace"] == ""


@pytest.mark.asyncio
async def test_http_request_metadata_is_populated(test_client):
    """http_request_context contains the essential Cloud Logging httpRequest fields."""
    response = await test_client.get("/capture")

    http_req = response.json()["http_request"]

    assert http_req["requestMethod"] == "GET"
    assert "/capture" in http_req["requestUrl"]


@pytest.mark.asyncio
async def test_context_is_reset_after_request():
    """
    Contextvars must be restored to their defaults after the middleware finishes,
    so that a reused coroutine/thread does not see stale values from a previous request.
    """
    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        await client.get("/capture", headers={"X-Cloud-Trace-Context": "stale_trace/0;o=1"})

    # After the request is fully processed the defaults should be restored
    assert cloud_trace_context.get() == ""
    assert http_request_context.get(None) is None


@pytest.mark.asyncio
async def test_concurrent_requests_have_isolated_contexts():
    """
    Two concurrent requests must not see each other's context values.
    Each response must carry only its own trace header.
    """
    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        results = await asyncio.gather(
            client.get("/capture", headers={"X-Cloud-Trace-Context": "trace_A/1;o=1"}),
            client.get("/capture", headers={"X-Cloud-Trace-Context": "trace_B/2;o=1"}),
        )

    traces = {r.json()["cloud_trace"] for r in results}
    assert traces == {"trace_A/1;o=1", "trace_B/2;o=1"}
