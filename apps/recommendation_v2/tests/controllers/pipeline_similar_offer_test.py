import pytest

from controllers.pipeline_similar_offer import SIMILAR_OFFERS_LIST_MAXIMUM_SIZE
from controllers.pipeline_similar_offer import generate_similar_offers
from schemas.enriched_offer import EnrichedRecommendableOffer
from schemas.playlist_recommendation import RecommendationMetadata
from schemas.playlist_recommendation import RecommendationResponse
from schemas.similar_offer import SimilarOfferModelChoices
from schemas.similar_offer import SimilarOfferResponse

from tests.factories.models import EnrichedUserFactory
from tests.factories.models import NonRecommendableItemsFactory
from tests.factories.models import RecommendableOffersFactory
from tests.factories.schemas import RecommendableItemFactory
from tests.factories.schemas import VertexPredictionResultFactory


PARIS_LATITUDE = 48.8566
PARIS_LONGITUDE = 2.3522


def _make_enriched_offer(
    offer_id: str,
    search_group_name: str = "LIVRES",
    item_score: float = 1.0,
) -> EnrichedRecommendableOffer:
    return EnrichedRecommendableOffer(
        offer_id=offer_id,
        item_id=f"item-{offer_id}",
        offer_creation_date=None,
        stock_beginning_date=None,
        is_geolocated=False,
        venue_latitude=None,
        venue_longitude=None,
        offer_user_distance=None,
        item_score=item_score,
        item_rank=1,
        item_origin="default",
        semantic_emb_mean=None,
        stock_price=0.0,
        category="LIVRES_PAPIER",
        subcategory_id="LIVRE_PAPIER",
        search_group_name=search_group_name,
        booking_number=0,
        booking_number_last_7_days=0,
        booking_number_last_14_days=0,
        booking_number_last_28_days=0,
    )


@pytest.mark.asyncio
async def test_similar_offer_returns_successful_response(
    db_session,
    mock_vertex_retrieval,
    mock_vertex_ranking,
    mocker,
):
    """
    Verifies the nominal end-to-end behaviour for a similar offer request.

    20 digital items are returned by the Vertex retrieval mock.
    The pipeline must produce a non-empty, size-bounded result list.
    """
    reference_offer = await RecommendableOffersFactory.create_async(offer_id="offer-ref", item_id="item-ref")

    digital_items = [
        RecommendableItemFactory.build(
            item_id=f"item-{i}",
            example_offer_id=str(i),
            is_geolocated=False,
            total_offers=1,
        )
        for i in range(20)
    ]

    mock_vertex_retrieval[1].return_value = VertexPredictionResultFactory.build(predictions=digital_items)
    mock_vertex_ranking[1].side_effect = lambda offers, _ctx: offers
    mocker.patch("controllers.pipeline_similar_offer.log_past_offer_context_to_sink")

    response = await generate_similar_offers(
        db=db_session,
        offer_id=reference_offer.offer_id,
    )

    assert isinstance(response, SimilarOfferResponse)
    assert len(response.results) <= SIMILAR_OFFERS_LIST_MAXIMUM_SIZE
    assert len(response.results) > 0
    assert response.params.reco_origin == "similar_offer"


@pytest.mark.asyncio
async def test_similar_offer_handles_unknown_offer_id(
    db_session,
    mock_vertex_retrieval,
    mock_vertex_ranking,
    mocker,
):
    """
    Verifies the pipeline handles a reference offer that does not exist in the database.

    When the offer_id is not found the pipeline logs a warning but must still
    call Vertex and return a valid (possibly empty) response without raising.
    """
    digital_items = [RecommendableItemFactory.build(is_geolocated=False, total_offers=1) for _ in range(5)]

    mock_vertex_retrieval[1].return_value = VertexPredictionResultFactory.build(predictions=digital_items)
    mock_vertex_ranking[1].side_effect = lambda offers, _ctx: offers
    mocker.patch("controllers.pipeline_similar_offer.log_past_offer_context_to_sink")

    response = await generate_similar_offers(
        db=db_session,
        offer_id="non-existent-offer-id",
    )

    assert response.params.reco_origin == "similar_offer"
    assert isinstance(response, SimilarOfferResponse)


@pytest.mark.asyncio
async def test_similar_offer_filters_out_already_booked_items(
    db_session,
    mock_vertex_retrieval,
    mock_vertex_ranking,
    mocker,
):
    """
    Verifies that already-booked items are excluded when an authenticated user_id is provided.

    Setup:
    - Vertex returns three items: item-A, item-B, item-C.
    - item-A is persisted in NonRecommendableItems for the authenticated user.

    Expected behaviour:
    - item-A must be absent from the candidates forwarded to resolve_closest_venues_from_items.
    - Only offer-B and offer-C appear in the final results.
    """
    user = await EnrichedUserFactory.create_warm()
    user_id = str(user.user_id)
    reference_offer = await RecommendableOffersFactory.create_async(offer_id="offer-ref", item_id="item-ref")

    item_a = RecommendableItemFactory.build(item_id="item-A", is_geolocated=False, total_offers=1)
    item_b = RecommendableItemFactory.build(item_id="item-B", is_geolocated=False, total_offers=1)
    item_c = RecommendableItemFactory.build(item_id="item-C", is_geolocated=False, total_offers=1)

    mock_vertex_retrieval[1].return_value = VertexPredictionResultFactory.build(predictions=[item_a, item_b, item_c])

    await NonRecommendableItemsFactory.create_async(user_id=user_id, item_id="item-A")

    offer_b = _make_enriched_offer("offer-B")
    offer_c = _make_enriched_offer("offer-C")

    mock_resolve = mocker.patch(
        "controllers.pipeline_similar_offer.resolve_closest_venues_from_items",
        new_callable=mocker.AsyncMock,
        return_value=[offer_b, offer_c],
    )
    mocker.patch("controllers.pipeline_similar_offer.log_past_offer_context_to_sink")

    response = await generate_similar_offers(
        db=db_session,
        offer_id=reference_offer.offer_id,
        user_id=user_id,
    )

    call_args = mock_resolve.call_args
    resolved_item_ids = [
        item.item_id
        for item in (call_args.kwargs.get("candidate_items") or call_args[1].get("candidate_items") or call_args[0][1])
    ]

    assert "item-A" not in resolved_item_ids
    assert "item-B" in resolved_item_ids
    assert "item-C" in resolved_item_ids

    assert "offer-B" in response.results
    assert "offer-C" in response.results
    assert response.params.reco_origin == "similar_offer"


@pytest.mark.asyncio
async def test_similar_offer_skips_booked_filter_for_unauthenticated_user(
    db_session,
    mock_vertex_retrieval,
    mock_vertex_ranking,
    mocker,
):
    """
    Verifies that the booked-item filter is skipped when no user_id is provided.

    filter_out_already_booked_items must NOT be called for unauthenticated requests
    since there is no user history to query.
    """
    reference_offer = await RecommendableOffersFactory.create_async(offer_id="offer-ref", item_id="item-ref")

    items = [RecommendableItemFactory.build(is_geolocated=False, total_offers=1) for _ in range(5)]
    mock_vertex_retrieval[1].return_value = VertexPredictionResultFactory.build(predictions=items)
    mock_vertex_ranking[1].side_effect = lambda offers, _ctx: offers

    mock_filter = mocker.patch(
        "controllers.pipeline_similar_offer.filter_out_already_booked_items",
        new_callable=mocker.AsyncMock,
    )
    mocker.patch("controllers.pipeline_similar_offer.log_past_offer_context_to_sink")

    await generate_similar_offers(
        db=db_session,
        offer_id=reference_offer.offer_id,
        user_id=None,
    )

    mock_filter.assert_not_called()


@pytest.mark.asyncio
async def test_similar_offer_falls_back_to_offer_location_when_user_has_no_gps(
    db_session,
    mock_vertex_retrieval,
    mock_vertex_ranking,
    mocker,
):
    """
    Verifies that the pipeline uses the reference offer's venue coordinates when
    the user provides no GPS data but the offer has a known location.

    The user_context passed to resolve_closest_venues_from_items must carry the
    offer's venue coordinates as the effective user location.
    """
    reference_offer = await RecommendableOffersFactory.create_async(
        offer_id="offer-geo",
        item_id="item-geo",
        venue_latitude=48.8566,
        venue_longitude=2.3522,
    )

    items = [RecommendableItemFactory.build(is_geolocated=False, total_offers=1) for _ in range(5)]
    mock_vertex_retrieval[1].return_value = VertexPredictionResultFactory.build(predictions=items)
    mock_vertex_ranking[1].side_effect = lambda offers, _ctx: offers

    mock_resolve = mocker.patch(
        "controllers.pipeline_similar_offer.resolve_closest_venues_from_items",
        new_callable=mocker.AsyncMock,
        return_value=[],
    )
    mocker.patch("controllers.pipeline_similar_offer.log_past_offer_context_to_sink")

    await generate_similar_offers(
        db=db_session,
        offer_id=reference_offer.offer_id,
        latitude=None,
        longitude=None,
    )

    call_args = mock_resolve.call_args
    user_context = call_args.kwargs.get("user_context") or call_args[1].get("user_context") or call_args[0][2]

    assert user_context.latitude == PARIS_LATITUDE
    assert user_context.longitude == PARIS_LONGITUDE


@pytest.mark.asyncio
async def test_similar_offer_caps_results_at_maximum_size(
    db_session,
    mock_vertex_retrieval,
    mock_vertex_ranking,
    mocker,
):
    """
    Verifies that the pipeline never returns more than SIMILAR_OFFERS_LIST_MAXIMUM_SIZE results.
    """
    reference_offer = await RecommendableOffersFactory.create_async(offer_id="offer-ref", item_id="item-ref")

    many_offers = [_make_enriched_offer(f"offer-{i}") for i in range(50)]

    mock_vertex_retrieval[1].return_value = VertexPredictionResultFactory.build(predictions=[])
    mocker.patch(
        "controllers.pipeline_similar_offer.resolve_closest_venues_from_items",
        new_callable=mocker.AsyncMock,
        return_value=many_offers,
    )
    mock_vertex_ranking[1].side_effect = lambda offers, _ctx: offers
    mocker.patch("controllers.pipeline_similar_offer.log_past_offer_context_to_sink")

    response = await generate_similar_offers(
        db=db_session,
        offer_id=reference_offer.offer_id,
    )

    assert response.params.reco_origin == "similar_offer"
    assert len(response.results) <= SIMILAR_OFFERS_LIST_MAXIMUM_SIZE


@pytest.mark.asyncio
async def test_similar_offer_uses_graph_retrieval_when_model_is_graph(
    db_session,
    mock_vertex_ranking,
    mocker,
):
    """When retrieval_model=graph, the graph retrieval client must be used."""
    reference_offer = await RecommendableOffersFactory.create_async(offer_id="offer-ref", item_id="item-ref")

    graph_items = [RecommendableItemFactory.build(is_geolocated=False, total_offers=1) for _ in range(5)]
    mock_graph_fetch = mocker.patch(
        "controllers.pipeline_similar_offer.fetch_graph_predictions_from_vertex",
        new_callable=mocker.AsyncMock,
        return_value=VertexPredictionResultFactory.build(predictions=graph_items),
    )
    mock_standard_fetch = mocker.patch(
        "controllers.pipeline_similar_offer.fetch_retrieval_predictions_from_vertex",
        new_callable=mocker.AsyncMock,
    )
    mock_vertex_ranking[1].side_effect = lambda offers, _ctx: offers
    mocker.patch("controllers.pipeline_similar_offer.log_past_offer_context_to_sink")

    response = await generate_similar_offers(
        db=db_session,
        offer_id=reference_offer.offer_id,
        retrieval_model=SimilarOfferModelChoices.graph,
    )

    assert response.params.reco_origin == "graph"
    mock_graph_fetch.assert_called_once()
    mock_standard_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_similar_offer_falls_back_to_playlist_recommendation_pipeline_when_coreservation_returns_no_results(
    db_session,
    mock_vertex_retrieval,
    mock_vertex_ranking,
    mocker,
):
    """
    Verifies the coreservation fallback: when the full similar-offer pipeline produces
    zero results, generate_playlist_recommendations is called and its output is returned
    with reco_origin='recommendation_fallback' and the model_origin from the fallback response.

    Setup:
    - Vertex retrieval returns no predictions → the pipeline naturally produces zero results.
    - generate_playlist_recommendations is mocked to return a predictable RecommendationResponse.

    Expected behaviour:
    - generate_playlist_recommendations is called exactly once.
    - The response results match the fallback offer IDs.
    - reco_origin is overridden to 'recommendation_fallback'.
    - model_origin reflects the playlist recommendation model (not the similar-offer model).
    """
    reference_offer = await RecommendableOffersFactory.create_async(offer_id="offer-ref", item_id="item-ref")

    # Force the similar-offer pipeline to produce zero results
    mock_vertex_retrieval[1].return_value = VertexPredictionResultFactory.build(predictions=[])

    # Prepare a predictable fallback response
    fallback_offer_ids = ["fallback-offer-1", "fallback-offer-2", "fallback-offer-3"]
    fallback_model_origin = "playlist-recommendation-model"
    mock_generate_playlist = mocker.patch(
        "controllers.pipeline_similar_offer.generate_playlist_recommendations",
        new_callable=mocker.AsyncMock,
        return_value=RecommendationResponse(
            playlist_recommended_offers=fallback_offer_ids,
            params=RecommendationMetadata(
                reco_origin="algo",
                model_origin=fallback_model_origin,
                call_id="fallback-call-id",
            ),
        ),
    )

    response = await generate_similar_offers(
        db=db_session,
        offer_id=reference_offer.offer_id,
    )

    mock_generate_playlist.assert_called_once()
    assert response.params.reco_origin == "recommendation_fallback"
    assert response.params.model_origin == fallback_model_origin
    assert response.results == fallback_offer_ids


@pytest.mark.asyncio
async def test_similar_offer_does_not_fall_back_when_retrieval_model_is_graph(
    db_session,
    mock_vertex_ranking,
    mocker,
):
    """
    Verifies that the fallback is NOT triggered for the graph retrieval model,
    even when offer resolution produces zero results.

    The fallback is a coreservation-only safety net (mirroring v1 behaviour).
    A graph request where resolution returns no offers must return an empty list
    without delegating to generate_playlist_recommendations.

    Setup:
    - The graph retrieval returns candidate items.
    - resolve_closest_venues_from_items returns an empty list (zero resolved offers).

    Expected behaviour:
    - generate_playlist_recommendations is never called.
    - reco_origin remains 'graph'.
    - results is an empty list.
    """
    reference_offer = await RecommendableOffersFactory.create_async(offer_id="offer-ref", item_id="item-ref")

    graph_items = [RecommendableItemFactory.build(is_geolocated=False, total_offers=1) for _ in range(5)]
    mocker.patch(
        "controllers.pipeline_similar_offer.fetch_graph_predictions_from_vertex",
        new_callable=mocker.AsyncMock,
        return_value=VertexPredictionResultFactory.build(predictions=graph_items),
    )
    # Resolution returns nothing → final_similar_offers will be empty
    mocker.patch(
        "controllers.pipeline_similar_offer.resolve_closest_venues_from_items",
        new_callable=mocker.AsyncMock,
        return_value=[],
    )
    mock_vertex_ranking[1].side_effect = lambda offers, _ctx: offers
    mock_generate_playlist = mocker.patch(
        "controllers.pipeline_similar_offer.generate_playlist_recommendations",
        new_callable=mocker.AsyncMock,
    )
    mocker.patch("controllers.pipeline_similar_offer.log_past_offer_context_to_sink")

    response = await generate_similar_offers(
        db=db_session,
        offer_id=reference_offer.offer_id,
        retrieval_model=SimilarOfferModelChoices.graph,
    )

    mock_generate_playlist.assert_not_called()
    assert response.params.reco_origin == "graph"
    assert response.results == []
