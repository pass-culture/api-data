"""
Integration tests for the ``GET /playlist_top_artists/{search_group_name}`` HTTP endpoint.
"""

import pytest
from fastapi import status
from httpx import AsyncClient

from config import settings
from schemas.categories import SearchGroupNameEnum

from tests.conftest import MOCK_CALL_ID
from tests.factories.models import ArtistFactory
from tests.factories.models import ArtistTopByCategoryFactory
from tests.factories.models import SimilarArtistFactory


DEFAULT_SCORE_NAME = settings.PLAYLIST_TOP_ARTISTS_DEFAULT_SCORE_NAME

TOP_ARTIST_1 = "11111111-1111-1111-1111-111111111111"
TOP_ARTIST_2 = "22222222-2222-2222-2222-222222222222"
TOP_ARTIST_3 = "33333333-3333-3333-3333-333333333333"
SHARED_CANDIDATE = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


async def _seed_top_artist(
    artist_id: str = TOP_ARTIST_1,
    category_rank: int = 1,
    search_group_name: str = "CINEMA",
) -> None:
    """
    Persist a single ``ArtistTopByCategory`` record in the test database.
    """
    await ArtistTopByCategoryFactory.create_async(
        artist_id=artist_id,
        search_group_name=search_group_name,
        score_name=DEFAULT_SCORE_NAME,
        category_rank=category_rank,
        score_value=9.0 - category_rank,
    )


@pytest.mark.asyncio
async def test_playlist_top_artists_returns_empty_when_no_data(client: AsyncClient):
    response = await client.get(f"/playlist_top_artists/{SearchGroupNameEnum.CINEMA.value}")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["playlist_artists"] == []
    assert body["params"]["search_group_name"] == "CINEMA"
    assert body["params"]["call_id"] == MOCK_CALL_ID


@pytest.mark.asyncio
async def test_playlist_top_artists_returns_tops_and_discovery(client: AsyncClient):
    for artist_id, rank in ((TOP_ARTIST_1, 1), (TOP_ARTIST_2, 2), (TOP_ARTIST_3, 3)):
        await _seed_top_artist(artist_id=artist_id, category_rank=rank)

    await SimilarArtistFactory.create_async(
        artist_id=TOP_ARTIST_1,
        similar_artists_json=[{"artist_id_match": SHARED_CANDIDATE, "rank": 1}],
    )
    await SimilarArtistFactory.create_async(
        artist_id=TOP_ARTIST_2,
        similar_artists_json=[{"artist_id_match": SHARED_CANDIDATE, "rank": 2}],
    )
    await ArtistFactory.create_async(
        artist_id=SHARED_CANDIDATE,
        main_search_group_name="CINEMA",
        main_search_group_name_has_bookable_offer=True,
    )

    response = await client.get(f"/playlist_top_artists/{SearchGroupNameEnum.CINEMA.value}")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["playlist_artists"] == [TOP_ARTIST_1, TOP_ARTIST_2, TOP_ARTIST_3, SHARED_CANDIDATE]
    assert set(body) == {"playlist_artists", "params"}


@pytest.mark.asyncio
async def test_playlist_top_artists_rejects_invalid_search_group_name(client: AsyncClient):
    response = await client.get("/playlist_top_artists/NOT_A_CATEGORY")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_playlist_top_artists_rejects_unsupported_search_group_name(client: AsyncClient):
    """`SPECTACLES` is a valid `SearchGroupNameEnum` value, but is not among the 3
    categories (CINEMA, LIVRES, MUSIQUE) supported by this endpoint."""
    response = await client.get(f"/playlist_top_artists/{SearchGroupNameEnum.SPECTACLES.value}")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_playlist_top_artists_respects_discovery_size_query_param(client: AsyncClient):
    await _seed_top_artist(artist_id=TOP_ARTIST_1, category_rank=1)
    for index in range(1, 11):
        await ArtistFactory.create_async(
            artist_id=f"candidate-{index}",
            main_search_group_name="CINEMA",
            main_search_group_name_has_bookable_offer=True,
        )
    await SimilarArtistFactory.create_async(
        artist_id=TOP_ARTIST_1,
        similar_artists_json=[{"artist_id_match": f"candidate-{index}", "rank": index} for index in range(1, 11)],
    )

    response = await client.get(f"/playlist_top_artists/{SearchGroupNameEnum.CINEMA.value}?discovery_size=2")

    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["playlist_artists"]) == 1 + 2


@pytest.mark.asyncio
async def test_playlist_top_artists_filter_has_bookable_offer_in_main_category_excludes_ineligible_candidate(
    client: AsyncClient,
):
    await _seed_top_artist(artist_id=TOP_ARTIST_1, category_rank=1)
    await SimilarArtistFactory.create_async(
        artist_id=TOP_ARTIST_1,
        similar_artists_json=[{"artist_id_match": SHARED_CANDIDATE, "rank": 1}],
    )
    await ArtistFactory.create_async(
        artist_id=SHARED_CANDIDATE,
        main_search_group_name="CINEMA",
        main_search_group_name_has_bookable_offer=False,
    )

    response = await client.get(f"/playlist_top_artists/{SearchGroupNameEnum.CINEMA.value}")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["playlist_artists"] == [TOP_ARTIST_1]


@pytest.mark.asyncio
async def test_playlist_top_artists_filter_main_category_matches_search_group_name_excludes_other_category_candidate(
    client: AsyncClient,
):
    await _seed_top_artist(artist_id=TOP_ARTIST_1, category_rank=1)
    await SimilarArtistFactory.create_async(
        artist_id=TOP_ARTIST_1,
        similar_artists_json=[{"artist_id_match": SHARED_CANDIDATE, "rank": 1}],
    )
    await ArtistFactory.create_async(
        artist_id=SHARED_CANDIDATE,
        main_search_group_name="MUSIQUE",
        main_search_group_name_has_bookable_offer=True,
    )

    response = await client.get(f"/playlist_top_artists/{SearchGroupNameEnum.CINEMA.value}")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["playlist_artists"] == [TOP_ARTIST_1]
