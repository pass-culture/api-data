KNOWN_OFFER_ID = "offer-movie-2"
UNKNOWN_OFFER_ID = "offer-unknown"


async def test_similar_offers_with_known_id_default(async_client):
    response = await async_client.get(f"/similar_offers/{KNOWN_OFFER_ID}")
    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    assert "params" in body
    # Since it is a known offer, it should not fall back to recommendation fallback by default
    assert body["params"]["model_origin"] != "recommendation_fallback"


async def test_similar_offers_with_unknown_id_default(async_client):
    response = await async_client.get(f"/similar_offers/{UNKNOWN_OFFER_ID}")
    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    # Since it is not in the database, with default retrieval_model,
    # it uses recommendation fallback which might return some results
    assert body["params"]["model_origin"] == "default"


async def test_similar_offers_with_unknown_id_graph(async_client):
    response = await async_client.get(
        f"/similar_offers/{UNKNOWN_OFFER_ID}?retrieval_model=graph"
    )
    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    # With retrieval_model=graph and offer not in DB, it must return an empty list immediately.
    assert len(body["results"]) == 0
    assert body["params"]["model_origin"] == "graph"


async def test_similar_offers_with_known_id_graph(async_client):
    response = await async_client.get(
        f"/similar_offers/{KNOWN_OFFER_ID}?retrieval_model=graph"
    )
    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    assert body["params"]["model_origin"] == "graph"
