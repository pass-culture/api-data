from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from pydantic import BaseModel

from schemas.offer_page_playlists import OfferPlaylistItem
from schemas.offer_page_playlists import OfferPlaylistTitleEnum
from schemas.offer_page_playlists import OfferPlaylistTypeEnum
from schemas.playlist_recommendation import RecommendationMetadata

from tests.conftest import patch_all_caches_disabled
from tests.conftest import patch_all_caches_enabled
from tests.factories.schemas import OfferPagePlaylistsResponseFactory
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
_OFFER_PAGE_CACHED_METADATA = RecommendationMetadata(
    reco_origin="similar_offer",
    model_origin="default",
    call_id=ORIGINAL_CALL_ID,
)


# ---------------------------------------------------------------------------
# Response builders / accessors
# ---------------------------------------------------------------------------
# Most endpoints expose a flat response (top-level "params" + a single results
# field). offer_page_playlists aggregates several sub-playlists, each carrying
# its own "params"/"results". These builder/accessor callables abstract that
# difference away so a single parametrized test suite can cover every endpoint.


def _build_flat_response(factory, metadata: RecommendationMetadata, result_key: str, results: list[str]) -> BaseModel:
    return factory.build(params=metadata, **{result_key: results})


def _get_flat_call_id(payload: dict[str, Any], result_key: str) -> str:
    return payload["params"]["call_id"]


def _get_flat_results(payload: dict[str, Any], result_key: str) -> list[str]:
    return payload[result_key]


def _build_offer_page_playlists_response(
    factory, metadata: RecommendationMetadata, result_key: str, results: list[str]
) -> BaseModel:
    playlist = OfferPlaylistItem(
        title=OfferPlaylistTitleEnum.LES_FANS_AIMENT_AUSSI,
        playlist_type=OfferPlaylistTypeEnum.SAME_TYPE,
        results=results,
        params=metadata,
    )
    return factory.build(offer_id="offer-ref", playlists=[playlist])


def _get_offer_page_playlists_call_id(payload: dict[str, Any], result_key: str) -> str:
    return payload["playlists"][0]["params"]["call_id"]


def _get_offer_page_playlists_results(payload: dict[str, Any], result_key: str) -> list[str]:
    return payload["playlists"][0]["results"]


# ---------------------------------------------------------------------------
# Endpoint parameter table — add one row per new endpoint
# ---------------------------------------------------------------------------
# Columns: method, url, body, redis_module, pipeline_fn, factory, cached_metadata,
#          result_key (field(s) driving the built/asserted result list), namespace_prefix,
#          build_response, get_call_id, get_results

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
        _build_flat_response,
        _get_flat_call_id,
        _get_flat_results,
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
        _build_flat_response,
        _get_flat_call_id,
        _get_flat_results,
        id="similar_offer",
    ),
    pytest.param(
        "GET",
        "/offer_page_playlists/offer-ref?search_group_name=LIVRES",
        None,
        "api.offer_page_playlists.redis_api",
        "api.offer_page_playlists.generate_offer_page_playlists",
        OfferPagePlaylistsResponseFactory,
        _OFFER_PAGE_CACHED_METADATA,
        "results",
        "offer_page_playlists",
        _build_offer_page_playlists_response,
        _get_offer_page_playlists_call_id,
        _get_offer_page_playlists_results,
        id="offer_page_playlists",
    ),
]

_PARAMS = (
    "method,url,body,redis_module,pipeline,factory,cached_metadata,"
    "result_key,namespace,build_response,get_call_id,get_results"
)


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
    result_key,
    namespace,
    build_response,
    get_call_id,
    get_results,
):
    """Cache hit must set from_cache=True and skip the recommendation pipeline entirely."""
    patch_all_caches_enabled(mocker)
    mocker.patch(
        f"{redis_module}.fetch_cached_response",
        new_callable=AsyncMock,
        return_value=build_response(factory, cached_metadata, result_key, ["offer-A"]),
    )
    mock_pipeline = mocker.patch(pipeline, new_callable=AsyncMock)

    response = await _request(client, method, url, body)

    assert response.status_code == HTTPStatus.OK
    assert response.json()["from_cache"] is True
    mock_pipeline.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(_PARAMS, CACHE_ENDPOINTS)
async def test_cache_hit_preserves_original_call_id(  # noqa: PLR0913
    client: AsyncClient,
    mocker,
    method,
    url,
    body,
    redis_module,
    pipeline,
    factory,
    cached_metadata,
    result_key,
    namespace,
    build_response,
    get_call_id,
    get_results,
):
    """
    A cache hit must preserve the original call_id.
    Cache hits are not tracked (no new BigQuery rows), but the client sends
    click/booking events referencing this call_id, which links them back to
    the original display rows.
    """
    patch_all_caches_enabled(mocker)
    mocker.patch(
        f"{redis_module}.fetch_cached_response",
        new_callable=AsyncMock,
        return_value=build_response(factory, cached_metadata, result_key, ["offer-A"]),
    )

    response = await _request(client, method, url, body)

    returned_call_id = get_call_id(response.json(), result_key)
    assert returned_call_id == ORIGINAL_CALL_ID


@pytest.mark.asyncio
@pytest.mark.parametrize(_PARAMS, CACHE_ENDPOINTS)
async def test_cache_hit_preserves_result_list(  # noqa: PLR0913
    client: AsyncClient,
    mocker,
    method,
    url,
    body,
    redis_module,
    pipeline,
    factory,
    cached_metadata,
    result_key,
    namespace,
    build_response,
    get_call_id,
    get_results,
):
    """The cached offer/result list must be returned unchanged."""
    expected = ["offer-A", "offer-B", "offer-C"]
    patch_all_caches_enabled(mocker)
    mocker.patch(
        f"{redis_module}.fetch_cached_response",
        new_callable=AsyncMock,
        return_value=build_response(factory, cached_metadata, result_key, expected),
    )

    response = await _request(client, method, url, body)

    assert get_results(response.json(), result_key) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(_PARAMS, CACHE_ENDPOINTS)
async def test_cache_miss_runs_pipeline_and_stores_result(  # noqa: PLR0913
    client: AsyncClient,
    mocker,
    method,
    url,
    body,
    redis_module,
    pipeline,
    factory,
    cached_metadata,
    result_key,
    namespace,
    build_response,
    get_call_id,
    get_results,
):
    """On a cache miss the pipeline must run and store the result under the correct namespace."""
    patch_all_caches_enabled(mocker)
    mocker.patch(f"{redis_module}.fetch_cached_response", new_callable=AsyncMock, return_value=None)
    mock_store = mocker.patch(f"{redis_module}.store_endpoint_response", new_callable=AsyncMock)
    non_empty_result = build_response(factory, cached_metadata, result_key, ["mocked-offer-1"])
    mocker.patch(pipeline, new_callable=AsyncMock, return_value=non_empty_result)

    response = await _request(client, method, url, body)

    assert response.status_code == HTTPStatus.OK
    assert response.json()["from_cache"] is False
    mock_store.assert_called_once()
    assert mock_store.call_args.kwargs["namespace_prefix"] == namespace


@pytest.mark.asyncio
@pytest.mark.parametrize(_PARAMS, CACHE_ENDPOINTS)
async def test_cache_miss_with_empty_result_does_not_store(  # noqa: PLR0913
    client: AsyncClient,
    mocker,
    method,
    url,
    body,
    redis_module,
    pipeline,
    factory,
    cached_metadata,
    result_key,
    namespace,
    build_response,
    get_call_id,
    get_results,
):
    """
    An empty result list must never be cached, even on a cache miss.

    A transient Vertex AI failure surfaces as a pipeline result with an empty
    offer/result list. Caching it would poison the cache with an empty response
    for the entire TTL, masking the failure and preventing any retry.
    """
    patch_all_caches_enabled(mocker)
    mocker.patch(f"{redis_module}.fetch_cached_response", new_callable=AsyncMock, return_value=None)
    mock_store = mocker.patch(f"{redis_module}.store_endpoint_response", new_callable=AsyncMock)
    empty_result = build_response(factory, cached_metadata, result_key, [])
    mocker.patch(pipeline, new_callable=AsyncMock, return_value=empty_result)

    response = await _request(client, method, url, body)

    assert response.status_code == HTTPStatus.OK
    assert get_results(response.json(), result_key) == []
    mock_store.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(_PARAMS, CACHE_ENDPOINTS)
async def test_no_cache_interaction_when_disabled(  # noqa: PLR0913
    client: AsyncClient,
    mocker,
    method,
    url,
    body,
    redis_module,
    pipeline,
    factory,
    cached_metadata,
    result_key,
    namespace,
    build_response,
    get_call_id,
    get_results,
):
    """With REDIS_CACHE_ENABLED=False neither fetch nor store must be called."""
    patch_all_caches_disabled(mocker)
    mock_fetch = mocker.patch(f"{redis_module}.fetch_cached_response", new_callable=AsyncMock)
    mock_store = mocker.patch(f"{redis_module}.store_endpoint_response", new_callable=AsyncMock)

    response = await _request(client, method, url, body)

    assert response.status_code == HTTPStatus.OK
    mock_fetch.assert_not_called()
    mock_store.assert_not_called()
