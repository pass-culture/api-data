"""
Centralised token-authentication tests for all protected endpoints.

Each endpoint is tested against every token scenario — no token, invalid token,
valid token via query parameter, and valid token via HTTP header — producing a
full coverage matrix through stacked ``@pytest.mark.parametrize`` decorators.

Token sources
-------------
- Query parameter : ``?token=<value>``
- HTTP header     : ``X-API-Key: <value>``

Expected behaviour
------------------
- No token supplied            → 401 Unauthorized
- Invalid token (any source)   → 401 Unauthorized
- Valid token via query param  → 200 OK  (legacy support)
- Valid token via HTTP header  → 200 OK  (new preferred method)
"""

from unittest.mock import patch

import pytest
from fastapi import APIRouter
from fastapi import Depends
from fastapi import FastAPI
from fastapi import status
from httpx import ASGITransport
from httpx import AsyncClient

from api.playlist_recommendation import router as playlist_router
from api.similar_artists import router as similar_artists_router
from api.similar_offer import router as similar_offer_router
from config import settings
from main import verify_api_token
from services.db import get_database_session


VALID_TOKEN = "valid-test-token"

# ---------------------------------------------------------------------------
# Endpoint matrix
# Each entry: (router, http_method, url, json_body)
# ---------------------------------------------------------------------------
ENDPOINT_PARAMS = [
    pytest.param(
        similar_offer_router,
        "GET",
        "/similar_offers/offer-auth-test",
        None,
        id="similar_offers",
    ),
    pytest.param(
        playlist_router,
        "POST",
        "/playlist_recommendation/user-auth-test",
        {},
        id="playlist_recommendation",
    ),
    pytest.param(
        similar_artists_router,
        "GET",
        "/similar_artists/a3a7c9f7-26f1-4bd3-bfc2-40a7abd398cf",
        None,
        id="similar_artists",
    ),
]

# ---------------------------------------------------------------------------
# Token scenario matrix
# Each entry: (token_query, token_header, expected_status_code)
# ---------------------------------------------------------------------------
TOKEN_SCENARIO_PARAMS = [
    pytest.param(
        None,
        None,
        status.HTTP_401_UNAUTHORIZED,
        id="no_token->401",
    ),
    pytest.param(
        "wrong-token",
        None,
        status.HTTP_401_UNAUTHORIZED,
        id="invalid_query_token->401",
    ),
    pytest.param(
        None,
        "wrong-token",
        status.HTTP_401_UNAUTHORIZED,
        id="invalid_header_token->401",
    ),
    pytest.param(
        VALID_TOKEN,
        None,
        status.HTTP_200_OK,
        id="valid_query_token->200",
    ),
    pytest.param(
        None,
        VALID_TOKEN,
        status.HTTP_200_OK,
        id="valid_header_token->200",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("router", "method", "url", "body"), ENDPOINT_PARAMS)
@pytest.mark.parametrize(("token_query", "token_header", "expected_status"), TOKEN_SCENARIO_PARAMS)
async def test_token_authentication_on_all_endpoints(  # noqa: PLR0913
    db_session,
    router: APIRouter,
    method: str,
    url: str,
    body: dict | None,
    token_query: str | None,
    token_header: str | None,
    expected_status: int,
):
    """
    Verifies that every protected endpoint enforces API-token authentication
    and accepts the token from both a query parameter and an HTTP header.

    A dedicated FastAPI application is built for each parametrised combination
    so that ``verify_api_token`` is always active, mirroring the production
    (non-local) configuration and avoiding any dependency on the IS_LOCAL flag.
    """

    async def override_get_database_session():
        yield db_session

    test_app = FastAPI()
    test_app.include_router(router, dependencies=[Depends(verify_api_token)])
    test_app.dependency_overrides[get_database_session] = override_get_database_session

    query_params = {"token": token_query} if token_query is not None else {}
    headers = {"X-API-Key": token_header} if token_header is not None else {}

    with patch.object(settings, "API_TOKEN", VALID_TOKEN):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.request(
                method,
                url,
                params=query_params,
                headers=headers,
                json=body,
            )

    assert response.status_code == expected_status
