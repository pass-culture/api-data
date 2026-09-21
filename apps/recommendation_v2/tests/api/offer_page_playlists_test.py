"""
Integration tests for the /offer_page_playlists/{offer_id} endpoint.

These tests verify:
- Basic response structure and HTTP contract.
- 404 response when the offer is not in the database.
- Database-driven playlist composition rules.
- Redis cache hit/miss behaviour.
- Cache-key isolation between different offer_ids and user_ids.
"""

import pytest
from fastapi import status
from httpx import AsyncClient

from config import settings
from connectors.redis_api import RedisAPI
from schemas.categories import SearchGroupNameEnum

from tests.factories.models import OfferMetadataFactory


# ---------------------------------------------------------------------------
# Response structure & 404 handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_offer_page_playlists_returns_200_with_correct_structure(client: AsyncClient, db_session):
    """
    A well-formed request for an existing offer returns HTTP 200 and a valid OfferPagePlaylistsResponse payload.
    """
    await OfferMetadataFactory.create_async(
        offer_id="test-offer-id",
        search_group_name=SearchGroupNameEnum.CINEMA.value,
    )

    response = await client.get("/offer_page_playlists/test-offer-id")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()

    assert body["offer_id"] == "test-offer-id"
    assert "playlists" in body
    assert isinstance(body["playlists"], list)
    assert body["from_cache"] is False


@pytest.mark.asyncio
async def test_offer_page_playlists_each_playlist_has_required_fields(client: AsyncClient, db_session):
    """Each playlist item must carry title, analytics_playlist_type, results and params (call_id, ab_test)."""
    await OfferMetadataFactory.create_async(
        offer_id="test-offer-id",
        search_group_name=SearchGroupNameEnum.CINEMA.value,
    )

    response = await client.get("/offer_page_playlists/test-offer-id")
    assert response.status_code == status.HTTP_200_OK

    for playlist in response.json()["playlists"]:
        assert "title" in playlist
        assert "analytics_playlist_type" in playlist
        assert "results" in playlist
        assert "params" in playlist
        assert "call_id" in playlist["params"]
        assert "ab_test" in playlist["params"]
        assert playlist["params"]["ab_test"] == settings.AB_TEST_VARIANT_LABEL


@pytest.mark.asyncio
async def test_offer_page_playlists_non_existent_offer_returns_404(client: AsyncClient):
    """When an offer is not found in offer_metadata_mv, the endpoint returns HTTP 404 Not Found."""
    response = await client.get("/offer_page_playlists/unknown-offer-404")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "unknown-offer-404" in response.json()["detail"]


@pytest.mark.asyncio
async def test_offer_page_playlists_db_search_group_name_drives_playlist_composition(client: AsyncClient, db_session):
    """LIVRES in offer_metadata_mv must yield the dual same-type playlists (coreservation + graph)."""
    await OfferMetadataFactory.create_async(
        offer_id="livres-offer",
        search_group_name=SearchGroupNameEnum.LIVRES.value,
    )

    response = await client.get("/offer_page_playlists/livres-offer")

    assert response.status_code == status.HTTP_200_OK
    analytics_playlist_types = [p["analytics_playlist_type"] for p in response.json()["playlists"]]
    assert analytics_playlist_types == ["sameCategorySimilarOffersTwoTower", "sameCategorySimilarOffersGraph"]


# ---------------------------------------------------------------------------
# Redis cache behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_offer_page_playlists_cache_hit_sets_from_cache(client: AsyncClient, db_session, redis_service, mocker):
    """
    Second identical request hits the Redis cache and returns from_cache=True.
    """
    await OfferMetadataFactory.create_async(
        offer_id="cache-offer",
        search_group_name=SearchGroupNameEnum.CINEMA.value,
    )

    first = await client.get("/offer_page_playlists/cache-offer")
    second = await client.get("/offer_page_playlists/cache-offer")

    assert first.status_code == status.HTTP_200_OK
    assert first.json()["from_cache"] is False

    assert second.status_code == status.HTTP_200_OK
    assert second.json()["from_cache"] is True
    for playlist in second.json()["playlists"]:
        assert playlist["params"]["ab_test"] == settings.AB_TEST_VARIANT_LABEL


@pytest.mark.asyncio
async def test_offer_page_playlists_different_offer_ids_have_different_cache_keys(
    client: AsyncClient, db_session, redis_service, mocker
):
    """
    Requests for different offer_ids must not share a cache entry.
    """
    await OfferMetadataFactory.create_async(
        offer_id="offer-A",
        search_group_name=SearchGroupNameEnum.CINEMA.value,
    )
    await OfferMetadataFactory.create_async(
        offer_id="offer-B",
        search_group_name=SearchGroupNameEnum.CINEMA.value,
    )

    fetch_spy = mocker.spy(RedisAPI, "fetch_cached_response")

    await client.get("/offer_page_playlists/offer-A")
    await client.get("/offer_page_playlists/offer-B")

    assert fetch_spy.call_count == 2

    first_sig = fetch_spy.call_args_list[0].kwargs["request_signature_data"]
    second_sig = fetch_spy.call_args_list[1].kwargs["request_signature_data"]
    assert first_sig["offer_id"] != second_sig["offer_id"]


@pytest.mark.asyncio
async def test_offer_page_playlists_user_id_affects_cache_key(client: AsyncClient, db_session, redis_service, mocker):
    """Two different user_ids must never share a cache entry."""
    await OfferMetadataFactory.create_async(
        offer_id="user-offer",
        search_group_name=SearchGroupNameEnum.CINEMA.value,
    )

    fetch_spy = mocker.spy(RedisAPI, "fetch_cached_response")

    first = await client.get("/offer_page_playlists/user-offer", params={"user_id": "user-A"})
    second = await client.get("/offer_page_playlists/user-offer", params={"user_id": "user-B"})

    assert fetch_spy.call_count == 2

    first_sig = fetch_spy.call_args_list[0].kwargs["request_signature_data"]
    second_sig = fetch_spy.call_args_list[1].kwargs["request_signature_data"]
    assert first_sig["user_id"] != second_sig["user_id"]

    assert first.json()["from_cache"] is False
    assert second.json()["from_cache"] is False
