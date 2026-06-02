from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest
from fastapi import Depends
from fastapi import FastAPI
from fastapi import status
from httpx import ASGITransport
from httpx import AsyncClient

from api.similar_offer import router as similar_offer_router
from config import settings
from main import verify_api_token
from services.db import get_database_session


VALID_OFFER_ID = "108450770"
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
async def test_similar_offer_enforces_token_verification_when_not_local(
    db_session,
    token_query_param,
    expected_status_code,
):
    """
    Verifies that the similar offer endpoint enforces API-token authentication
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
        similar_offer_router,
        dependencies=[Depends(verify_api_token)],
    )
    test_app.dependency_overrides[get_database_session] = override_get_database_session

    query_params = {"token": token_query_param} if token_query_param is not None else {}

    with patch.object(settings, "API_TOKEN", VALID_TOKEN):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.get(
                f"/similar_offers/{VALID_OFFER_ID}",
                params=query_params,
            )

    assert response.status_code == expected_status_code


@pytest.mark.asyncio
async def test_category_order_does_not_affect_cache_key(client: AsyncClient, mocker):
    """
    The endpoint sorts categories before building the cache key, so request order
    must not produce a different cache entry — otherwise the same logical request
    could bypass the cache simply by reordering query params.
    """
    mocker.patch.object(settings, "REDIS_CACHE_ENABLED", new=True)
    fetch_mock = mocker.patch(
        "api.similar_offer.redis_api.fetch_cached_response", new_callable=AsyncMock, return_value=None
    )
    mocker.patch("api.similar_offer.redis_api.store_endpoint_response", new_callable=AsyncMock)

    await client.get("/similar_offers/offer-ref?categories=CINEMA&categories=LIVRE")
    await client.get("/similar_offers/offer-ref?categories=LIVRE&categories=CINEMA")

    assert fetch_mock.call_count == 2  # noqa: PLR2004
    first_sig = fetch_mock.call_args_list[0].kwargs["request_signature_data"]
    second_sig = fetch_mock.call_args_list[1].kwargs["request_signature_data"]
    assert first_sig["categories"] == second_sig["categories"]


@pytest.mark.asyncio
async def test_user_id_query_param_affects_cache_key(client: AsyncClient, mocker):
    """The optional user_id query param must be included in the signature so two users
    never share a similar-offer cache entry."""
    mocker.patch.object(settings, "REDIS_CACHE_ENABLED", new=True)
    fetch_mock = mocker.patch(
        "api.similar_offer.redis_api.fetch_cached_response", new_callable=AsyncMock, return_value=None
    )
    mocker.patch("api.similar_offer.redis_api.store_endpoint_response", new_callable=AsyncMock)

    await client.get("/similar_offers/offer-ref?user_id=user-A")
    await client.get("/similar_offers/offer-ref?user_id=user-B")

    assert fetch_mock.call_count == 2  # noqa: PLR2004
    first_sig = fetch_mock.call_args_list[0].kwargs["request_signature_data"]
    second_sig = fetch_mock.call_args_list[1].kwargs["request_signature_data"]
    assert first_sig["user_id"] != second_sig["user_id"]


@pytest.mark.asyncio
async def test_nearby_coordinates_in_same_h3_cell_share_cache_key(client: AsyncClient, mocker):
    """
    Two coordinates close enough to fall inside the same H3 cell must normalize to the
    same location_h3, and therefore the same cache key — this is the whole point of H3
    in caching: a user moving a few metres should hit the existing cache entry.
    """
    mocker.patch.object(settings, "REDIS_CACHE_ENABLED", new=True)
    fetch_mock = mocker.patch(
        "api.similar_offer.redis_api.fetch_cached_response", new_callable=AsyncMock, return_value=None
    )
    mocker.patch("api.similar_offer.redis_api.store_endpoint_response", new_callable=AsyncMock)

    # Both points sit ~50 m apart inside the same resolution-8 H3 cell.
    await client.get("/similar_offers/offer-ref?latitude=48.8566&longitude=2.3522")
    await client.get("/similar_offers/offer-ref?latitude=48.8568&longitude=2.3524")

    assert fetch_mock.call_count == 2  # noqa: PLR2004
    first_sig = fetch_mock.call_args_list[0].kwargs["request_signature_data"]
    second_sig = fetch_mock.call_args_list[1].kwargs["request_signature_data"]
    assert first_sig["location_h3"] is not None
    assert first_sig["location_h3"] == second_sig["location_h3"]


@pytest.mark.asyncio
async def test_distant_coordinates_produce_different_cache_key(client: AsyncClient, mocker):
    """Coordinates in different H3 cells must normalize to different location_h3 values
    so a far-away user never reuses an unrelated location's cache entry."""
    mocker.patch.object(settings, "REDIS_CACHE_ENABLED", new=True)
    fetch_mock = mocker.patch(
        "api.similar_offer.redis_api.fetch_cached_response", new_callable=AsyncMock, return_value=None
    )
    mocker.patch("api.similar_offer.redis_api.store_endpoint_response", new_callable=AsyncMock)

    # Paris vs Versailles (~17 km apart) fall in different resolution-8 H3 cells.
    await client.get("/similar_offers/offer-ref?latitude=48.8566&longitude=2.3522")
    await client.get("/similar_offers/offer-ref?latitude=48.8048&longitude=2.1203")

    assert fetch_mock.call_count == 2  # noqa: PLR2004
    first_sig = fetch_mock.call_args_list[0].kwargs["request_signature_data"]
    second_sig = fetch_mock.call_args_list[1].kwargs["request_signature_data"]
    assert first_sig["location_h3"] != second_sig["location_h3"]


@pytest.mark.asyncio
async def test_retrieval_model_query_param_affects_cache_key(client: AsyncClient, mocker):
    """The cache signature must vary by retrieval model to avoid cross-model cache reuse."""
    mocker.patch.object(settings, "REDIS_CACHE_ENABLED", new=True)
    fetch_mock = mocker.patch(
        "api.similar_offer.redis_api.fetch_cached_response", new_callable=AsyncMock, return_value=None
    )
    mocker.patch("api.similar_offer.redis_api.store_endpoint_response", new_callable=AsyncMock)

    await client.get("/similar_offers/offer-ref?retrieval_model=coreservation")
    await client.get("/similar_offers/offer-ref?retrieval_model=graph")

    assert fetch_mock.call_count == 2  # noqa: PLR2004
    first_sig = fetch_mock.call_args_list[0].kwargs["request_signature_data"]
    second_sig = fetch_mock.call_args_list[1].kwargs["request_signature_data"]
    assert first_sig["retrieval_model"] != second_sig["retrieval_model"]
