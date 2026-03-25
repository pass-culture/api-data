KNOWN_ARTIST_ID = "018c03db-4800-40a1-aede-be3716c59e0a"
UNKNOWN_ARTIST_ID = "00000000-0000-0000-0000-000000000000"


async def test_similar_artists_with_known_id(async_client):
    response = await async_client.get(f"/similar_artists/{KNOWN_ARTIST_ID}")
    assert response.status_code == 200
    body = response.json()

    # Main fields check
    assert "params" in body
    assert body["params"]["artist_id"] == KNOWN_ARTIST_ID
    assert "call_id" in body["params"]
    assert body["params"]["call_id"]

    # Response check
    assert "similar_artists" in body
    assert len(body["similar_artists"]) > 0

    # Check that the similar artists have the expected fields
    for artist in body["similar_artists"]:
        assert "artist_id_match" in artist
        assert "rank" in artist
        assert isinstance(artist["rank"], int)


async def test_similar_artists_with_unknown_id(async_client):
    response = await async_client.get(f"/similar_artists/{UNKNOWN_ARTIST_ID}")
    assert response.status_code == 200
    body = response.json()

    # Main fields check
    assert "params" in body
    assert body["params"]["artist_id"] == UNKNOWN_ARTIST_ID
    assert "call_id" in body["params"]
    assert body["params"]["call_id"]

    # Response check
    assert "similar_artists" in body
    assert len(body["similar_artists"]) == 0
