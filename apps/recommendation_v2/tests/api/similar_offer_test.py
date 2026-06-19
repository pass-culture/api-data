import pytest
from fastapi import status
from httpx import AsyncClient

from connectors.redis_api import RedisAPI


@pytest.mark.asyncio
async def test_category_order_does_not_affect_cache_key(client: AsyncClient, redis_service, mocker):
    """
    The endpoint sorts categories before building the cache key, so request order
    must not produce a different cache entry — otherwise the same logical request
    could bypass the cache simply by reordering query params.

    Backed by a real Redis container, the reordered second request is a genuine cache
    hit (from_cache=True), proving the two requests resolve to the same cache entry.
    """
    fetch_spy = mocker.spy(RedisAPI, "fetch_cached_response")

    first_response = await client.get("/similar_offers/offer-categories?categories=CINEMA&categories=LIVRE")
    second_response = await client.get("/similar_offers/offer-categories?categories=LIVRE&categories=CINEMA")

    # Cache-key logic: categories are sorted, so order does not change the signature.
    assert fetch_spy.call_count == 2  # noqa: PLR2004
    first_sig = fetch_spy.call_args_list[0].kwargs["request_signature_data"]
    second_sig = fetch_spy.call_args_list[1].kwargs["request_signature_data"]
    assert first_sig["categories"] == second_sig["categories"]

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
async def test_nearby_coordinates_in_same_h3_cell_share_cache_key(client: AsyncClient, redis_service, mocker):
    """
    Two coordinates close enough to fall inside the same H3 cell must normalize to the
    same location_h3, and therefore the same cache key — this is the whole point of H3
    in caching: a user moving a few metres should hit the existing cache entry.

    Backed by a real Redis container, the second (nearby) request is a genuine cache hit
    (from_cache=True).
    """
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
