"""
Integration tests for the /offer_page_playlists/{offer_id} endpoint.

These tests verify:
- Basic response structure and HTTP contract.
- Redis cache hit/miss behaviour.
- Cache-key isolation between different offer_ids and user_ids.

Note: Playlist composition rules (CINEMA vs LIVRES vs MUSIQUE) are covered
by unit tests in tests/controllers/pipeline_offer_page_playlists_test.py.
"""

import pytest
from fastapi import status
from httpx import AsyncClient

from connectors.redis_api import RedisAPI
from schemas.categories import SearchGroupNameEnum


# ---------------------------------------------------------------------------
# Response structure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_offer_page_playlists_returns_200_with_correct_structure(client: AsyncClient):
    """
    A well-formed request returns HTTP 200 and a valid OfferPagePlaylistsResponse payload.
    """
    response = await client.get(
        "/offer_page_playlists/test-offer-id",
        params={"search_group_name": SearchGroupNameEnum.CINEMA.value},
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()

    assert body["offer_id"] == "test-offer-id"
    assert "playlists" in body
    assert isinstance(body["playlists"], list)
    assert body["from_cache"] is False


@pytest.mark.asyncio
async def test_offer_page_playlists_each_playlist_has_required_fields(client: AsyncClient):
    """Each playlist item must carry title, playlist_type, results and params.call_id."""
    response = await client.get(
        "/offer_page_playlists/test-offer-id",
        params={"search_group_name": SearchGroupNameEnum.CINEMA.value},
    )
    assert response.status_code == status.HTTP_200_OK

    for playlist in response.json()["playlists"]:
        assert "title" in playlist
        assert "playlist_type" in playlist
        assert "results" in playlist
        assert "params" in playlist
        assert "call_id" in playlist["params"]


# ---------------------------------------------------------------------------
# Redis cache behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_offer_page_playlists_cache_hit_sets_from_cache(client: AsyncClient, redis_service, mocker):
    """
    Second identical request hits the Redis cache and returns from_cache=True.
    """
    first = await client.get(
        "/offer_page_playlists/cache-offer",
        params={"search_group_name": SearchGroupNameEnum.CINEMA.value},
    )
    second = await client.get(
        "/offer_page_playlists/cache-offer",
        params={"search_group_name": SearchGroupNameEnum.CINEMA.value},
    )

    assert first.status_code == status.HTTP_200_OK
    assert first.json()["from_cache"] is False

    assert second.status_code == status.HTTP_200_OK
    assert second.json()["from_cache"] is True


@pytest.mark.asyncio
async def test_offer_page_playlists_different_offer_ids_have_different_cache_keys(
    client: AsyncClient, redis_service, mocker
):
    """
    Requests for different offer_ids must not share a cache entry.
    """
    fetch_spy = mocker.spy(RedisAPI, "fetch_cached_response")

    await client.get("/offer_page_playlists/offer-A", params={"search_group_name": SearchGroupNameEnum.CINEMA.value})
    await client.get("/offer_page_playlists/offer-B", params={"search_group_name": SearchGroupNameEnum.CINEMA.value})

    assert fetch_spy.call_count == 2  # noqa: PLR2004

    first_sig = fetch_spy.call_args_list[0].kwargs["request_signature_data"]
    second_sig = fetch_spy.call_args_list[1].kwargs["request_signature_data"]
    assert first_sig["offer_id"] != second_sig["offer_id"]


@pytest.mark.asyncio
async def test_offer_page_playlists_user_id_affects_cache_key(client: AsyncClient, redis_service, mocker):
    """Two different user_ids must never share a cache entry."""
    fetch_spy = mocker.spy(RedisAPI, "fetch_cached_response")

    first = await client.get(
        "/offer_page_playlists/user-offer",
        params={"user_id": "user-A", "search_group_name": SearchGroupNameEnum.CINEMA.value},
    )
    second = await client.get(
        "/offer_page_playlists/user-offer",
        params={"user_id": "user-B", "search_group_name": SearchGroupNameEnum.CINEMA.value},
    )

    assert fetch_spy.call_count == 2  # noqa: PLR2004

    first_sig = fetch_spy.call_args_list[0].kwargs["request_signature_data"]
    second_sig = fetch_spy.call_args_list[1].kwargs["request_signature_data"]
    assert first_sig["user_id"] != second_sig["user_id"]

    assert first.json()["from_cache"] is False
    assert second.json()["from_cache"] is False


@pytest.mark.asyncio
async def test_offer_page_playlists_search_group_name_affects_cache_key(client: AsyncClient, redis_service, mocker):
    """Two different search_group_names for the same offer_id must not share a cache entry."""
    fetch_spy = mocker.spy(RedisAPI, "fetch_cached_response")

    first = await client.get(
        "/offer_page_playlists/same-offer",
        params={"search_group_name": SearchGroupNameEnum.CINEMA.value},
    )
    second = await client.get(
        "/offer_page_playlists/same-offer",
        params={"search_group_name": SearchGroupNameEnum.LIVRES.value},
    )

    assert fetch_spy.call_count == 2  # noqa: PLR2004

    first_sig = fetch_spy.call_args_list[0].kwargs["request_signature_data"]
    second_sig = fetch_spy.call_args_list[1].kwargs["request_signature_data"]
    assert first_sig["search_group_name"] != second_sig["search_group_name"]

    assert first.json()["from_cache"] is False
    assert second.json()["from_cache"] is False


@pytest.mark.asyncio
async def test_offer_page_playlists_search_group_name_drives_playlist_composition(client: AsyncClient):
    """LIVRES must yield the dual same-type playlists (coreservation + graph)."""
    response = await client.get(
        "/offer_page_playlists/livres-offer",
        params={"search_group_name": SearchGroupNameEnum.LIVRES.value},
    )

    assert response.status_code == status.HTTP_200_OK
    playlist_types = [p["playlist_type"] for p in response.json()["playlists"]]
    assert playlist_types == ["same_type_coreservation", "same_type_graph"]


@pytest.mark.asyncio
async def test_offer_page_playlists_missing_search_group_name_returns_422(client: AsyncClient):
    """Without search_group_name (required parameter), the endpoint returns HTTP 422 Unprocessable Entity."""
    response = await client.get("/offer_page_playlists/unknown-offer")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
