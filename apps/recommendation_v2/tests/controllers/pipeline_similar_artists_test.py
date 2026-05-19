import pytest

from controllers.pipeline_similar_artists import get_similar_artists_from_db

from tests.factories.models import SimilarArtistFactory


VALID_ARTIST_ID = "0c1a0fe4-f2bf-4e1d-b9ac-7c46e4a6e2d6"

SIMILAR_ARTISTS_JSON = [
    {"artist_id_match": "f3cbe55e-6341-47bf-ae0e-dc6eb6c33f5d", "rank": 1},
    {"artist_id_match": "cb11b170-50fd-492e-8569-d96a33330ff9", "rank": 2},
]


@pytest.mark.asyncio
async def test_similar_artists_returns_empty_list_when_artist_not_found(db_session):
    response = await get_similar_artists_from_db(db=db_session, artist_id="unknown-artist-id")

    assert response.similar_artists == []
    assert response.params.artist_id == "unknown-artist-id"


@pytest.mark.asyncio
async def test_similar_artists_returns_similar_artists_from_db(db_session):
    artist = await SimilarArtistFactory.create_async(
        artist_id=VALID_ARTIST_ID,
        similar_artists_json=SIMILAR_ARTISTS_JSON,
    )

    response = await get_similar_artists_from_db(db=db_session, artist_id=artist.artist_id)

    assert response.params.artist_id == VALID_ARTIST_ID
    assert len(response.similar_artists) == len(SIMILAR_ARTISTS_JSON)
    assert response.similar_artists[0].artist_id_match == SIMILAR_ARTISTS_JSON[0]["artist_id_match"]
    assert response.similar_artists[0].rank == SIMILAR_ARTISTS_JSON[0]["rank"]
