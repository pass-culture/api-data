import uuid
from http import HTTPStatus
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from config import settings
from schemas.playlist_recommendation import RecommendationMetadata

from tests.factories.schemas import RecommendationResponseFactory
from tests.factories.schemas import SimilarOfferResponseFactory


ORIGINAL_CALL_ID = "00000000-0000-0000-0000-000000000000"


_PLAYLIST_CACHED_METADATA = RecommendationMetadata(
    reco_origin="algo",
    model_origin="default",
    call_id=ORIGINAL_CALL_ID,
)
_SIMILAR_CACHED_METADATA = RecommendationMetadata(
    reco_origin="similar_offer",
    model_origin="default",
    call_id=ORIGINAL_CALL_ID,
)


# ---------------------------------------------------------------------------
# Endpoint parameter table — add one row per new endpoint
# ---------------------------------------------------------------------------
# Columns: method, url, body, redis_module, pipeline_fn, factory,
#          cached_metadata, result_key (top-level offers/results field), namespace_prefix

CACHE_ENDPOINTS = [
    pytest.param(
        "POST",
        "/playlist_recommendation/user-1",
        {},
        "api.playlist_recommendation.redis_api",
        "api.playlist_recommendation.generate_playlist_recommendations",
        RecommendationResponseFactory,
        _PLAYLIST_CACHED_METADATA,
        "playlist_recommended_offers",
        "playlist_recommendation",
        id="playlist",
    ),
    pytest.param(
        "GET",
        "/similar_offers/offer-ref",
        None,
        "api.similar_offer.redis_api",
        "api.similar_offer.generate_similar_offers",
        SimilarOfferResponseFactory,
        _SIMILAR_CACHED_METADATA,
        "results",
        "similar_offer",
        id="similar_offer",
    ),
]

_PARAMS = "method,url,body,redis_module,pipeline,factory,cached_metadata,result_key,namespace"


async def _request(client: AsyncClient, method: str, url: str, body):
    """Dispatch a GET or POST request based on the endpoint's HTTP method."""
    if method == "POST":
        return await client.post(url, json=body)
    return await client.get(url)


@pytest.mark.asyncio
@pytest.mark.parametrize(_PARAMS, CACHE_ENDPOINTS)
async def test_cache_hit_returns_from_cache_true(  # noqa: PLR0913
    client: AsyncClient,
    mocker,
    method,
    url,
    body,
    redis_module,
    pipeline,
    factory,
    cached_metadata,
):
    """Cache hit must set from_cache=True and skip the recommendation pipeline entirely."""
    mocker.patch.object(settings, "REDIS_CACHE_ENABLED", new=True)
    mocker.patch(
        f"{redis_module}.fetch_cached_response",
        new_callable=AsyncMock,
        return_value=factory.build(params=cached_metadata),
    )
    mock_pipeline = mocker.patch(pipeline, new_callable=AsyncMock)

    response = await _request(client, method, url, body)

    assert response.status_code == HTTPStatus.OK
    assert response.json()["from_cache"] is True
    mock_pipeline.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(_PARAMS, CACHE_ENDPOINTS)
async def test_cache_hit_injects_new_call_id(  # noqa: PLR0913
    client: AsyncClient,
    mocker,
    method,
    url,
    body,
    redis_module,
    factory,
    cached_metadata,
):
    """
    A cache hit must overwrite the original call_id with a newly generated UUID.
    Re-using the original call_id would link every cache-hit impression back to
    the same training event, which biases model retraining.
    """
    mocker.patch.object(settings, "REDIS_CACHE_ENABLED", new=True)
    mocker.patch(
        f"{redis_module}.fetch_cached_response",
        new_callable=AsyncMock,
        return_value=factory.build(params=cached_metadata),
    )

    response = await _request(client, method, url, body)

    returned_call_id = response.json()["params"]["call_id"]
    assert returned_call_id != ORIGINAL_CALL_ID
    uuid.UUID(returned_call_id)  # must be a valid UUID


@pytest.mark.asyncio
@pytest.mark.parametrize(_PARAMS, CACHE_ENDPOINTS)
async def test_cache_hit_preserves_result_list(  # noqa: PLR0913
    client: AsyncClient,
    mocker,
    method,
    url,
    body,
    redis_module,
    factory,
    cached_metadata,
    result_key,
):
    """The cached offer/result list must be returned unchanged."""
    expected = ["offer-A", "offer-B", "offer-C"]
    mocker.patch.object(settings, "REDIS_CACHE_ENABLED", new=True)
    mocker.patch(
        f"{redis_module}.fetch_cached_response",
        new_callable=AsyncMock,
        return_value=factory.build(params=cached_metadata, **{result_key: expected}),
    )

    response = await _request(client, method, url, body)

    assert response.json()[result_key] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(_PARAMS, CACHE_ENDPOINTS)
async def test_cache_miss_runs_pipeline_and_stores_result(  # noqa: PLR0913
    client: AsyncClient,
    mocker,
    method,
    url,
    body,
    redis_module,
    namespace,
):
    """On a cache miss the pipeline must run and store the result under the correct namespace."""
    mocker.patch.object(settings, "REDIS_CACHE_ENABLED", new=True)
    mocker.patch(f"{redis_module}.fetch_cached_response", new_callable=AsyncMock, return_value=None)
    mock_store = mocker.patch(f"{redis_module}.store_endpoint_response", new_callable=AsyncMock)

    response = await _request(client, method, url, body)

    assert response.status_code == HTTPStatus.OK
    assert response.json()["from_cache"] is False
    mock_store.assert_called_once()
    assert mock_store.call_args.kwargs["namespace_prefix"] == namespace


@pytest.mark.asyncio
@pytest.mark.parametrize(_PARAMS, CACHE_ENDPOINTS)
async def test_no_cache_interaction_when_disabled(
    client: AsyncClient,
    mocker,
    method,
    url,
    body,
    redis_module,
):
    """With REDIS_CACHE_ENABLED=False neither fetch nor store must be called."""
    mocker.patch.object(settings, "REDIS_CACHE_ENABLED", new=False)
    mock_fetch = mocker.patch(f"{redis_module}.fetch_cached_response", new_callable=AsyncMock)
    mock_store = mocker.patch(f"{redis_module}.store_endpoint_response", new_callable=AsyncMock)

    response = await _request(client, method, url, body)

    assert response.status_code == HTTPStatus.OK
    mock_fetch.assert_not_called()
    mock_store.assert_not_called()
