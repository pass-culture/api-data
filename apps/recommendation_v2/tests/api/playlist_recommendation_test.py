from unittest.mock import patch

import pytest
from fastapi import Depends
from fastapi import FastAPI
from fastapi import status
from httpx import ASGITransport
from httpx import AsyncClient

from api.playlist_recommendation import router as playlist_router
from config import settings
from connectors.redis_api import RedisAPI
from main import verify_api_token
from services.db import get_database_session


VALID_USER_ID = "123"
VALID_TOKEN = "valid-test-token"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("token_query_param", "expected_status_code"),
    [
        pytest.param(None, status.HTTP_401_UNAUTHORIZED, id="no_token_returns_401"),
        pytest.param("wrong-token", status.HTTP_401_UNAUTHORIZED, id="invalid_token_returns_401"),
        pytest.param(VALID_TOKEN, status.HTTP_200_OK, id="valid_token_returns_200"),
    ],
)
async def test_playlist_recommendation_enforces_token_verification_when_not_local(
    db_session,
    token_query_param,
    expected_status_code,
):
    """
    Verifies that the playlist recommendation endpoint enforces API-token authentication
    regardless of the IS_LOCAL flag.

    A dedicated FastAPI application is built for each test run so that
    ``verify_api_token`` is always active — this mirrors the production
    (non-local) configuration exactly and avoids depending on environment variables.

    Parametrised cases
    ------------------
    - ``None``          → no token supplied           → 401 Unauthorized
    - ``"wrong-token"`` → token present but invalid   → 401 Unauthorized
    - ``VALID_TOKEN``   → token matches settings      → 200 OK
    """

    async def override_get_database_session():
        yield db_session

    test_app = FastAPI()
    test_app.include_router(
        playlist_router,
        dependencies=[Depends(verify_api_token)],
    )
    test_app.dependency_overrides[get_database_session] = override_get_database_session

    query_params = {"token": token_query_param} if token_query_param is not None else {}

    with patch.object(settings, "API_TOKEN", VALID_TOKEN):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                f"/playlist_recommendation/{VALID_USER_ID}",
                params=query_params,
                json={},
            )

    assert response.status_code == expected_status_code


@pytest.mark.asyncio
async def test_nearby_coordinates_in_same_h3_cell_share_cache_key(client: AsyncClient, redis_service, mocker):
    """Two coordinates inside the same H3 cell normalize to the same location_h3,
    so a user moving a few metres reuses the existing playlist cache entry.

    A real Redis container (via redis_service) backs the cache, so the second request is a
    genuine cache hit (from_cache=True). A spy on RedisAPI.fetch_cached_response captures the
    request_signature_data of each call without replacing the real implementation.
    """
    fetch_spy = mocker.spy(RedisAPI, "fetch_cached_response")

    first_response = await client.post(
        "/playlist_recommendation/user-nearby?latitude=48.8566&longitude=2.3522", json={}
    )
    second_response = await client.post(
        "/playlist_recommendation/user-nearby?latitude=48.8568&longitude=2.3524", json={}
    )

    # Cache-key logic (H3): the two calls share the same normalized location.
    assert fetch_spy.call_count == 2  # noqa: PLR2004
    first_sig = fetch_spy.call_args_list[0].kwargs["request_signature_data"]
    second_sig = fetch_spy.call_args_list[1].kwargs["request_signature_data"]
    assert first_sig["location_h3"] is not None
    assert first_sig["location_h3"] == second_sig["location_h3"]

    # Real cache behavior: first call misses, second call hits.
    assert first_response.status_code == status.HTTP_200_OK
    assert first_response.json()["from_cache"] is False
    assert second_response.status_code == status.HTTP_200_OK
    assert second_response.json()["from_cache"] is True


@pytest.mark.asyncio
async def test_distant_coordinates_produce_different_cache_keys(client: AsyncClient, redis_service, mocker):
    """Two coordinates in different H3 cells produce different location_h3 values,
    so a user moving a large distance generates a new playlist cache entry.

    Backed by a real Redis container, both requests miss the cache (from_cache=False)
    because their signatures — and therefore their cache keys — differ.
    """
    fetch_spy = mocker.spy(RedisAPI, "fetch_cached_response")

    first_response = await client.post(
        "/playlist_recommendation/user-distant?latitude=48.8566&longitude=2.3522", json={}
    )
    second_response = await client.post(
        "/playlist_recommendation/user-distant?latitude=48.8048&longitude=2.1203", json={}
    )

    # Cache-key logic (H3): the two calls normalize to different locations.
    assert fetch_spy.call_count == 2  # noqa: PLR2004
    first_sig = fetch_spy.call_args_list[0].kwargs["request_signature_data"]
    second_sig = fetch_spy.call_args_list[1].kwargs["request_signature_data"]
    assert first_sig["location_h3"] is not None
    assert first_sig["location_h3"] != second_sig["location_h3"]

    # Real cache behavior: different keys mean neither call is served from cache.
    assert first_response.status_code == status.HTTP_200_OK
    assert first_response.json()["from_cache"] is False
    assert second_response.status_code == status.HTTP_200_OK
    assert second_response.json()["from_cache"] is False
