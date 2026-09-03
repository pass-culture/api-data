from unittest.mock import AsyncMock

import pytest
from fastapi import status
from httpx import AsyncClient

from connectors.redis_api import RedisAPI
from schemas.playlist_recommendation import RecommendationMetadata

from tests.conftest import patch_all_caches_enabled
from tests.factories.schemas import RecommendableItemFactory
from tests.factories.schemas import SimilarOfferResponseFactory
from tests.factories.schemas import VertexPredictionResultFactory


@pytest.mark.asyncio
async def test_category_order_does_not_affect_cache_key(
    client: AsyncClient, redis_service, mocker, mock_vertex_retrieval
):
    """
    Categories sent in a different query-param order must resolve to the same cache entry.

    Normalization (list sorting) is now centralized inside generate_cache_key._deep_normalize,
    so the endpoint no longer needs to sort lists manually. The request_signature_data may
    carry the lists in their raw insertion order, but the resulting Redis key is identical.

    Backed by a real Redis container, the reordered second request is a genuine cache
    hit (from_cache=True), proving the two requests resolve to the same cache entry.

    The Vertex retrieval mock is pinned to a single non-geolocated item (fast-track
    resolution, no DB lookup needed) so the pipeline deterministically returns a
    non-empty, non-fallback result — otherwise the default random mock data could
    occasionally miss resolution and trigger the (now uncached) playlist fallback,
    making the "second call is a cache hit" assertion flaky.
    """
    mock_vertex_retrieval[1].return_value = VertexPredictionResultFactory.build(
        status="success",
        predictions=[RecommendableItemFactory.build(is_geolocated=False, total_offers=1)],
    )
    fetch_spy = mocker.spy(RedisAPI, "fetch_cached_response")

    first_response = await client.get("/similar_offers/offer-categories?categories=CINEMA&categories=LIVRE")
    second_response = await client.get("/similar_offers/offer-categories?categories=LIVRE&categories=CINEMA")

    # Both calls must have been intercepted.
    assert fetch_spy.call_count == 2  # noqa: PLR2004

    # Real cache behavior: first call misses, reordered second call hits.
    assert first_response.status_code == status.HTTP_200_OK
    assert first_response.json()["from_cache"] is False
    assert second_response.status_code == status.HTTP_200_OK
    assert second_response.json()["from_cache"] is True


@pytest.mark.asyncio
async def test_user_id_query_param_affects_cache_key(client: AsyncClient, redis_service, mocker):
    """The optional user_id query param must be included in the signature so two users
    never share a similar-offer cache entry.

    Backed by a real Redis container, both requests miss the cache (from_cache=False)
    because the differing user_id yields a different cache key.
    """
    fetch_spy = mocker.spy(RedisAPI, "fetch_cached_response")

    first_response = await client.get("/similar_offers/offer-userid?user_id=user-A")
    second_response = await client.get("/similar_offers/offer-userid?user_id=user-B")

    # Cache-key logic: user_id is part of the signature.
    assert fetch_spy.call_count == 2  # noqa: PLR2004
    first_sig = fetch_spy.call_args_list[0].kwargs["request_signature_data"]
    second_sig = fetch_spy.call_args_list[1].kwargs["request_signature_data"]
    assert first_sig["user_id"] != second_sig["user_id"]

    # Real cache behavior: different users never share a cache entry.
    assert first_response.status_code == status.HTTP_200_OK
    assert first_response.json()["from_cache"] is False
    assert second_response.status_code == status.HTTP_200_OK
    assert second_response.json()["from_cache"] is False


@pytest.mark.asyncio
async def test_nearby_coordinates_in_same_h3_cell_share_cache_key(
    client: AsyncClient, redis_service, mocker, mock_vertex_retrieval
):
    """
    Two coordinates close enough to fall inside the same H3 cell must normalize to the
    same location_h3, and therefore the same cache key — this is the whole point of H3
    in caching: a user moving a few metres should hit the existing cache entry.

    Backed by a real Redis container, the second (nearby) request is a genuine cache hit
    (from_cache=True).

    The Vertex retrieval mock is pinned to a single non-geolocated item (fast-track
    resolution, no DB lookup needed) so the pipeline deterministically returns a
    non-empty, non-fallback result — otherwise the default random mock data could
    occasionally miss resolution and trigger the (now uncached) playlist fallback,
    making the "second call is a cache hit" assertion flaky.
    """
    mock_vertex_retrieval[1].return_value = VertexPredictionResultFactory.build(
        status="success",
        predictions=[RecommendableItemFactory.build(is_geolocated=False, total_offers=1)],
    )
    fetch_spy = mocker.spy(RedisAPI, "fetch_cached_response")

    # Both points sit ~50 m apart inside the same resolution-8 H3 cell.
    first_response = await client.get("/similar_offers/offer-nearby?latitude=48.8566&longitude=2.3522")
    second_response = await client.get("/similar_offers/offer-nearby?latitude=48.8568&longitude=2.3524")

    # Cache-key logic (H3): the two calls share the same normalized location.
    assert fetch_spy.call_count == 2  # noqa: PLR2004
    first_sig = fetch_spy.call_args_list[0].kwargs["request_signature_data"]
    second_sig = fetch_spy.call_args_list[1].kwargs["request_signature_data"]
    assert first_sig["location_h3"] is not None
    assert first_sig["location_h3"] == second_sig["location_h3"]

    # Real cache behavior: first call misses, nearby second call hits.
    assert first_response.status_code == status.HTTP_200_OK
    assert first_response.json()["from_cache"] is False
    assert second_response.status_code == status.HTTP_200_OK
    assert second_response.json()["from_cache"] is True


@pytest.mark.asyncio
async def test_distant_coordinates_produce_different_cache_key(client: AsyncClient, redis_service, mocker):
    """Coordinates in different H3 cells must normalize to different location_h3 values
    so a far-away user never reuses an unrelated location's cache entry.

    Backed by a real Redis container, both requests miss the cache (from_cache=False)
    because the differing location yields a different cache key.
    """
    fetch_spy = mocker.spy(RedisAPI, "fetch_cached_response")

    # Paris vs Versailles (~17 km apart) fall in different resolution-8 H3 cells.
    first_response = await client.get("/similar_offers/offer-distant?latitude=48.8566&longitude=2.3522")
    second_response = await client.get("/similar_offers/offer-distant?latitude=48.8048&longitude=2.1203")

    # Cache-key logic (H3): the two calls normalize to different locations.
    assert fetch_spy.call_count == 2  # noqa: PLR2004
    first_sig = fetch_spy.call_args_list[0].kwargs["request_signature_data"]
    second_sig = fetch_spy.call_args_list[1].kwargs["request_signature_data"]
    assert first_sig["location_h3"] != second_sig["location_h3"]

    # Real cache behavior: different keys mean neither call is served from cache.
    assert first_response.status_code == status.HTTP_200_OK
    assert first_response.json()["from_cache"] is False
    assert second_response.status_code == status.HTTP_200_OK
    assert second_response.json()["from_cache"] is False


@pytest.mark.asyncio
async def test_fallback_result_is_not_cached_under_similar_offer_namespace(client: AsyncClient, mocker):
    """
    A playlist-fallback result (reco_origin='recommendation_fallback') must never be
    cached under the 'similar_offer' namespace, even when it is non-empty.

    The fallback pipeline (generate_playlist_recommendations) is only meant to run
    when the similar-offer pipeline genuinely produced zero results. Caching its
    output under the similar_offer key would serve generic playlist recommendations,
    disguised as similar offers, on every subsequent request for the same offer.
    """
    patch_all_caches_enabled(mocker)
    mocker.patch("api.similar_offer.redis_api.fetch_cached_response", new_callable=AsyncMock, return_value=None)
    mock_store = mocker.patch("api.similar_offer.redis_api.store_endpoint_response", new_callable=AsyncMock)
    mocker.patch(
        "api.similar_offer.generate_similar_offers",
        new_callable=AsyncMock,
        return_value=SimilarOfferResponseFactory.build(
            results=["fallback-offer-1"],
            params=RecommendationMetadata(
                reco_origin="recommendation_fallback",
                model_origin="default",
                call_id="fallback-call-id",
            ),
        ),
    )

    response = await client.get("/similar_offers/offer-fallback")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["results"] == ["fallback-offer-1"]
    mock_store.assert_not_called()


@pytest.mark.asyncio
async def test_retrieval_model_query_param_affects_cache_key(client: AsyncClient, redis_service, mocker):
    """The cache signature must vary by retrieval model to avoid cross-model cache reuse.

    Backed by a real Redis container, both requests miss the cache (from_cache=False)
    because the differing retrieval_model yields a different cache key.
    """
    fetch_spy = mocker.spy(RedisAPI, "fetch_cached_response")

    first_response = await client.get("/similar_offers/offer-retrieval?retrieval_model=coreservation")
    second_response = await client.get("/similar_offers/offer-retrieval?retrieval_model=graph")

    # Cache-key logic: retrieval_model is part of the signature.
    assert fetch_spy.call_count == 2  # noqa: PLR2004
    first_sig = fetch_spy.call_args_list[0].kwargs["request_signature_data"]
    second_sig = fetch_spy.call_args_list[1].kwargs["request_signature_data"]
    assert first_sig["retrieval_model"] != second_sig["retrieval_model"]

    # Real cache behavior: different models never share a cache entry.
    assert first_response.status_code == status.HTTP_200_OK
    assert first_response.json()["from_cache"] is False
    assert second_response.status_code == status.HTTP_200_OK
    assert second_response.json()["from_cache"] is False
