import pytest
from fastapi import status
from httpx import AsyncClient

from connectors.redis_api import RedisAPI


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
