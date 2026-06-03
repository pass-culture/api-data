from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest
from fastapi import Depends
from fastapi import FastAPI
from fastapi import status
from httpx import ASGITransport
from httpx import AsyncClient

from api.playlist_recommendation import router as playlist_router
from config import settings
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
async def test_nearby_coordinates_in_same_h3_cell_share_cache_key(client: AsyncClient, mocker):
    """Two coordinates inside the same H3 cell normalize to the same location_h3,
    so a user moving a few metres reuses the existing playlist cache entry."""
    mocker.patch.object(settings, "REDIS_CACHE_ENABLED", new=True)
    fetch_mock = mocker.patch(
        "api.playlist_recommendation.redis_api.fetch_cached_response", new_callable=AsyncMock, return_value=None
    )
    mocker.patch("api.playlist_recommendation.redis_api.store_endpoint_response", new_callable=AsyncMock)

    await client.post("/playlist_recommendation/user-1?latitude=48.8566&longitude=2.3522", json={})
    await client.post("/playlist_recommendation/user-1?latitude=48.8568&longitude=2.3524", json={})

    assert fetch_mock.call_count == 2  # noqa: PLR2004
    first_sig = fetch_mock.call_args_list[0].kwargs["request_signature_data"]
    second_sig = fetch_mock.call_args_list[1].kwargs["request_signature_data"]
    assert first_sig["location_h3"] is not None
    assert first_sig["location_h3"] == second_sig["location_h3"]


@pytest.mark.asyncio
async def test_distant_coordinates_produce_different_cache_keys(client: AsyncClient, mocker):
    """Two coordinates in different H3 cells produce different location_h3 values,
    so a user moving a large distance generates a new playlist cache entry."""
    mocker.patch.object(settings, "REDIS_CACHE_ENABLED", new=True)
    fetch_mock = mocker.patch(
        "api.playlist_recommendation.redis_api.fetch_cached_response", new_callable=AsyncMock, return_value=None
    )
    mocker.patch("api.playlist_recommendation.redis_api.store_endpoint_response", new_callable=AsyncMock)

    await client.post("/playlist_recommendation/user-1?latitude=48.8566&longitude=2.3522", json={})
    await client.post("/playlist_recommendation/user-1?latitude=48.8048&longitude=2.1203", json={})

    assert fetch_mock.call_count == 2  # noqa: PLR2004
    first_sig = fetch_mock.call_args_list[0].kwargs["request_signature_data"]
    second_sig = fetch_mock.call_args_list[1].kwargs["request_signature_data"]
    assert first_sig["location_h3"] is not None
    assert first_sig["location_h3"] != second_sig["location_h3"]
