import h3
import pytest

from api.playlist_recommendation import PRESET_LOCATION_TO_GEOGRAPHIC_COORDINATES_MAPPING
from api.playlist_recommendation import PresetLocation
from config import settings
from controllers.pipeline_playlist_recommendation import PLAYLIST_RECOMMENDATION_MAXIMUM_SIZE
from controllers.pipeline_playlist_recommendation import generate_playlist_recommendations
from schemas.enriched_offer import EnrichedRecommendableOffer
from schemas.playlist_recommendation import PlaylistRequestParams
from schemas.playlist_recommendation import RecommendationResponse

from tests.factories.models import EnrichedUserFactory
from tests.factories.models import NonRecommendableItemsFactory
from tests.factories.models import RecommendableOffersFactory
from tests.factories.models import VenueFactory
from tests.factories.schemas import RecommendableItemFactory


def _make_enriched_offer(
    offer_id: str,
    search_group_name: str = "LIVRES",
    item_score: float = 1.0,
) -> EnrichedRecommendableOffer:
    """
    Creates a minimal EnrichedRecommendableOffer for use in unit tests.

    Only the fields required to exercise pipeline logic are populated;
    all geospatial and booking-count fields are set to neutral/null values.

    Args:
        offer_id: Unique identifier for the offer.
        search_group_name: Category group used for diversification checks.
        item_score: Relevance score assigned to the item.

    Returns:
        A fully-initialised EnrichedRecommendableOffer instance.
    """
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
async def test_pipeline_generates_successful_playlist_for_geolocated_user(
    db_session,
    mock_vertex_retrieval,
    mock_vertex_ranking,
    mocker,
):
    """
    Verifies the end-to-end nominal behaviour for a geolocated user.

    50 digital items (is_geolocated=False, total_offers=1) are returned by the
    Vertex retrieval mock, bypassing any geospatial DB query via the fast-track.
    The pipeline must produce a non-empty, size-bounded playlist and call tracking.
    """
    user = await EnrichedUserFactory.create_warm()

    digital_items = [
        RecommendableItemFactory.build(
            item_id=f"item-{i}",
            example_offer_id=str(i),
            is_geolocated=False,
            total_offers=1,
        )
        for i in range(50)
    ]

    mock_vertex_retrieval[0].return_value = digital_items
    mock_vertex_ranking[0].side_effect = lambda offers, _ctx: offers
    mock_tracking = mocker.patch("controllers.pipeline_playlist_recommendation.log_past_offer_context_to_sink")

    response = await generate_playlist_recommendations(
        db=db_session,
        user_id=str(user.user_id),
        latitude=48.8566,
        longitude=2.3522,
        params=PlaylistRequestParams(),
    )

    assert isinstance(response, RecommendationResponse)
    assert len(response.playlist_recommended_offers) <= PLAYLIST_RECOMMENDATION_MAXIMUM_SIZE
    assert len(response.playlist_recommended_offers) > 0
    mock_tracking.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_generates_successful_playlist_without_gps(
    db_session,
    mock_vertex_retrieval,
    mock_vertex_ranking,
    mocker,
):
    """
    Verifies that the pipeline works correctly when no GPS coordinates are provided.

    Digital items (is_geolocated=False) bypass geospatial DB queries via the fast-track
    and must appear in the final playlist even without a user location.

    A single geolocated item is deliberately injected in the Vertex response to assert
    that physical offers are silently excluded when the user's position is unknown —
    recommending them would be meaningless and potentially misleading.

    Expected behaviour:
    - The pipeline completes successfully.
    - The returned playlist is non-empty and contains only digital offers.
    - The geolocated offer ("offer-physical") is absent from the response.
    - from_cache is False.
    """
    user = await EnrichedUserFactory.create_warm()

    digital_items = [
        RecommendableItemFactory.build(
            item_id=f"item-digital-{i}",
            example_offer_id=f"offer-digital-{i}",
            is_geolocated=False,
            total_offers=1,
        )
        for i in range(10)
    ]
    geolocated_item = RecommendableItemFactory.build(
        item_id="item-physical",
        example_offer_id="offer-physical",
        is_geolocated=True,
        total_offers=1,
        example_venue_latitude=48.8566,
        example_venue_longitude=2.3522,
    )

    mock_vertex_retrieval[0].return_value = [*digital_items, geolocated_item]
    mock_vertex_ranking[0].side_effect = lambda offers, _ctx: offers
    mocker.patch("controllers.pipeline_playlist_recommendation.log_past_offer_context_to_sink")

    response = await generate_playlist_recommendations(
        db=db_session,
        user_id=str(user.user_id),
        latitude=None,
        longitude=None,
        params=PlaylistRequestParams(),
    )

    assert isinstance(response, RecommendationResponse)
    assert len(response.playlist_recommended_offers) > 0
    assert response.from_cache is False
    assert "offer-physical" not in response.playlist_recommended_offers, (
        "A geolocated offer must not appear in the playlist when the user has no GPS coordinates."
    )
    response.params.reco_origin = "algo"


@pytest.mark.asyncio
async def test_pipeline_filters_out_already_booked_items(
    db_session,
    mock_vertex_retrieval,
    mock_vertex_ranking,
    mocker,
):
    """
    Verifies that items the user has already booked are excluded from the final playlist.

    Setup:
    - Vertex returns three items: item-A, item-B, item-C.
    - item-A is persisted in NonRecommendableItems for this user (already booked).

    Expected behaviour:
    - item-A must be absent from the candidate list forwarded to resolve_closest_venues_from_items.
    - Only offer-B and offer-C must appear in the final playlist.
    """
    user = await EnrichedUserFactory.create_warm()
    user_id = str(user.user_id)

    item_a = RecommendableItemFactory.build(item_id="item-A", is_geolocated=False, total_offers=1)
    item_b = RecommendableItemFactory.build(item_id="item-B", is_geolocated=False, total_offers=1)
    item_c = RecommendableItemFactory.build(item_id="item-C", is_geolocated=False, total_offers=1)

    mock_vertex_retrieval[0].return_value = [item_a, item_b, item_c]

    await NonRecommendableItemsFactory.create_async(
        user_id=user_id,
        item_id="item-A",
    )

    offer_b = _make_enriched_offer("offer-B")
    offer_c = _make_enriched_offer("offer-C")

    mock_resolve = mocker.patch(
        "controllers.pipeline_playlist_recommendation.resolve_closest_venues_from_items",
        new_callable=mocker.AsyncMock,
        return_value=[offer_b, offer_c],
    )
    mocker.patch("controllers.pipeline_playlist_recommendation.log_past_offer_context_to_sink")

    response = await generate_playlist_recommendations(
        db=db_session,
        user_id=user_id,
        latitude=None,
        longitude=None,
        params=PlaylistRequestParams(),
    )

    call_args = mock_resolve.call_args
    resolved_item_ids = [
        item.item_id
        for item in (call_args.kwargs.get("candidate_items") or call_args[1].get("candidate_items") or call_args[0][1])
    ]

    assert "item-A" not in resolved_item_ids
    assert "item-B" in resolved_item_ids
    assert "item-C" in resolved_item_ids

    assert "offer-B" in response.playlist_recommended_offers
    assert "offer-C" in response.playlist_recommended_offers


@pytest.mark.asyncio
async def test_pipeline_handles_venues_out_of_range(
    db_session,
    mock_vertex_retrieval,
    mock_vertex_ranking,
    mocker,
):
    """
    Verifies geo-distance filtering for single-offer and multi-offer geolocated items.

    Scenario — user is located in Paris:

        item-close  (total_offers=1, Paris)      → fast-track: within 100 km → included
        item-far    (total_offers=1, Marseille)   → fast-track: > DEFAULT_MAX_DISTANCE  → excluded
        item-multi  (total_offers=3)              → DB resolution via H3 spatial filter:
            ├── offer-orly       (~15 km)  ← CLOSEST within 50 km radius → selected
            ├── offer-versailles (~20 km)  → in range but not closest       → excluded
            └── offer-marseille-multi (~765 km) → outside H3 radius        → excluded

    find_closest_offers_with_h3_index is exercised WITHOUT mocking to validate the
    end-to-end H3 spatial filter and closest-offer resolution logic.
    """
    user = await EnrichedUserFactory.create_warm()

    paris_lat, paris_lon = PRESET_LOCATION_TO_GEOGRAPHIC_COORDINATES_MAPPING[PresetLocation.HIGH_DENSITY_PARIS]
    marseille_lat, marseille_lon = PRESET_LOCATION_TO_GEOGRAPHIC_COORDINATES_MAPPING[
        PresetLocation.HIGH_DENSITY_MARSEILLE
    ]

    versailles_lat, versailles_lon = 48.8044, 2.1204  # ~20 km from Paris
    orly_lat, orly_lon = 48.7262, 2.3652  # ~15 km from Paris

    h3_resolution = settings.GEOSPATIAL_RETRIEVAL_H3_RESOLUTION

    def make_h3_index(lat: float, lon: float) -> str:
        return h3.latlng_to_cell(lat, lon, h3_resolution)

    venue_versailles = await VenueFactory.create_async(
        latitude=versailles_lat,
        longitude=versailles_lon,
        **{f"h3_res{h3_resolution}": make_h3_index(versailles_lat, versailles_lon)},
    )
    venue_orly = await VenueFactory.create_async(
        latitude=orly_lat,
        longitude=orly_lon,
        **{f"h3_res{h3_resolution}": make_h3_index(orly_lat, orly_lon)},
    )
    venue_marseille_multi = await VenueFactory.create_async(
        latitude=marseille_lat,
        longitude=marseille_lon,
        **{f"h3_res{h3_resolution}": make_h3_index(marseille_lat, marseille_lon)},
    )

    await RecommendableOffersFactory.create_async(
        unique_id="unique-versailles",
        offer_id="offer-versailles",
        item_id="item-multi",
        venue_id=venue_versailles.venue_id,
        venue_latitude=versailles_lat,
        venue_longitude=versailles_lon,
    )
    await RecommendableOffersFactory.create_async(
        unique_id="unique-orly",
        offer_id="offer-orly",
        item_id="item-multi",
        venue_id=venue_orly.venue_id,
        venue_latitude=orly_lat,
        venue_longitude=orly_lon,
    )
    await RecommendableOffersFactory.create_async(
        unique_id="unique-marseille-multi",
        offer_id="offer-marseille-multi",
        item_id="item-multi",
        venue_id=venue_marseille_multi.venue_id,
        venue_latitude=marseille_lat,
        venue_longitude=marseille_lon,
    )

    item_close = RecommendableItemFactory.build(
        item_id="item-close",
        example_offer_id="offer-paris",
        is_geolocated=True,
        total_offers=1,
        example_venue_latitude=paris_lat,
        example_venue_longitude=paris_lon,
    )
    item_far = RecommendableItemFactory.build(
        item_id="item-far",
        example_offer_id="offer-marseille",
        is_geolocated=True,
        total_offers=1,
        example_venue_latitude=marseille_lat,
        example_venue_longitude=marseille_lon,
    )
    item_multi = RecommendableItemFactory.build(
        item_id="item-multi",
        is_geolocated=True,
        total_offers=3,
    )

    mock_vertex_retrieval[0].return_value = [item_close, item_far, item_multi]
    mock_vertex_ranking[0].side_effect = lambda offers, _ctx: offers
    mocker.patch("controllers.pipeline_playlist_recommendation.log_past_offer_context_to_sink")

    response = await generate_playlist_recommendations(
        db=db_session,
        user_id=str(user.user_id),
        latitude=paris_lat,
        longitude=paris_lon,
        params=PlaylistRequestParams(),
    )

    assert "offer-paris" in response.playlist_recommended_offers
    assert "offer-marseille" not in response.playlist_recommended_offers
    assert "offer-orly" in response.playlist_recommended_offers, (
        "offer-orly (~15 km, closest) should have been selected for item-multi."
    )
    assert "offer-versailles" not in response.playlist_recommended_offers, (
        "offer-versailles (~20 km) should not appear since offer-orly is closer."
    )
    assert "offer-marseille-multi" not in response.playlist_recommended_offers, (
        "offer-marseille-multi is outside the 50 km H3 radius and must be filtered out."
    )


@pytest.mark.asyncio
async def test_pipeline_applies_diversification_correctly(
    db_session,
    mock_vertex_retrieval,
    mock_vertex_ranking,
    mocker,
):
    """
    Verifies that diversification prevents a single category from monopolising the top results.

    Setup:
    - 10 "MUSIQUE" offers dominate the top of the ranked list (highest scores).
    - 5 offers from distinct other categories follow.
    - The ranking mock preserves this order (MUSIQUE-heavy at the top).

    Expected behaviour:
    - After diversification the first 3 positions must not all belong to "MUSIQUE".
    """
    user = await EnrichedUserFactory.create_warm()

    music_offers = [
        _make_enriched_offer(f"music-{i}", search_group_name="MUSIQUE", item_score=float(100 - i)) for i in range(10)
    ]
    other_offers = [
        _make_enriched_offer("cinema-1", search_group_name="CINEMA"),
        _make_enriched_offer("livres-1", search_group_name="LIVRES"),
        _make_enriched_offer("spectacles-1", search_group_name="SPECTACLES"),
        _make_enriched_offer("jeux-1", search_group_name="JEUX_JEUX_VIDEOS"),
        _make_enriched_offer("musees-1", search_group_name="MUSEES_VISITES_CULTURELLES"),
    ]
    all_offers = music_offers + other_offers

    mock_vertex_retrieval[0].return_value = []
    mocker.patch(
        "controllers.pipeline_playlist_recommendation.resolve_closest_venues_from_items",
        new_callable=mocker.AsyncMock,
        return_value=all_offers,
    )
    mock_vertex_ranking[0].side_effect = lambda offers, _ctx: offers
    mocker.patch("controllers.pipeline_playlist_recommendation.log_past_offer_context_to_sink")

    response = await generate_playlist_recommendations(
        db=db_session,
        user_id=str(user.user_id),
        latitude=None,
        longitude=None,
        params=PlaylistRequestParams(),
    )

    assert len(response.playlist_recommended_offers) > 0

    offer_id_to_search_group = {offer.offer_id: offer.search_group_name for offer in all_offers}
    top_3_search_groups = [offer_id_to_search_group[offer_id] for offer_id in response.playlist_recommended_offers[:3]]

    assert len(set(top_3_search_groups)) > 1, (
        f"The top 3 offers are all from the same category ({top_3_search_groups}): "
        "diversification is not working correctly."
    )


@pytest.mark.asyncio
async def test_pipeline_handles_new_user_cold_start(
    db_session,
    mock_vertex_retrieval,
    mock_vertex_ranking,
    mocker,
):
    """
    Verifies that the pipeline handles a cold-start user (no booking history) gracefully.

    Expected behaviour:
    - No exception is raised.
    - The returned playlist is non-empty.
    - reco_origin is "cold_start".
    - Tracking is still called because the user is authenticated.
    """
    cold_start_user = await EnrichedUserFactory.create_cold_start()

    cold_start_items = [RecommendableItemFactory.build(is_geolocated=False, total_offers=1) for _ in range(5)]
    mock_vertex_retrieval[0].return_value = cold_start_items

    resolved_offers = [_make_enriched_offer(str(i)) for i in range(5)]
    mocker.patch(
        "controllers.pipeline_playlist_recommendation.resolve_closest_venues_from_items",
        new_callable=mocker.AsyncMock,
        return_value=resolved_offers,
    )
    mock_tracking = mocker.patch("controllers.pipeline_playlist_recommendation.log_past_offer_context_to_sink")

    response = await generate_playlist_recommendations(
        db=db_session,
        user_id=str(cold_start_user.user_id),
        latitude=None,
        longitude=None,
        params=PlaylistRequestParams(),
    )

    assert isinstance(response, RecommendationResponse)
    assert len(response.playlist_recommended_offers) > 0
    assert response.params.reco_origin == "cold_start"
    mock_tracking.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_handles_empty_retrieval_from_vertex(
    db_session,
    mock_vertex_retrieval,
    mock_vertex_ranking,
    mocker,
):
    """
    Verifies that the pipeline handles an empty Vertex retrieval response without raising.

    Expected behaviour:
    - No exception is raised.
    - The final playlist is empty.
    - The ranking function is still called once, receiving an empty list.
    """
    user = await EnrichedUserFactory.create_warm()

    mock_vertex_retrieval[0].return_value = []
    mocker.patch("controllers.pipeline_playlist_recommendation.log_past_offer_context_to_sink")

    response = await generate_playlist_recommendations(
        db=db_session,
        user_id=str(user.user_id),
        latitude=None,
        longitude=None,
        params=PlaylistRequestParams(),
    )

    assert isinstance(response, RecommendationResponse)
    assert response.playlist_recommended_offers == []
    mock_vertex_ranking[0].assert_called_once()
    assert mock_vertex_ranking[0].call_args[0][0] == []


@pytest.mark.asyncio
async def test_pipeline_skips_tracking_for_unauthenticated_user(
    db_session,
    mock_vertex_retrieval,
    mock_vertex_ranking,
    mocker,
):
    """
    Verifies that tracking is NOT called for a user who does not exist in the database.

    An unauthenticated user has no profile in EnrichedUser, so the pipeline falls back to
    generic (popularity-based) results. Associating engagement signals from such sessions
    with a non-existent user would pollute the training data with non-personalised noise
    and degrade recommendation quality over time.

    Expected behaviour:
    - The pipeline completes successfully and returns a valid RecommendationResponse.
    - log_past_offer_context_to_sink is NOT called.
    """
    unknown_user_id = "non-existent-user-id-99999"

    unauthenticated_items = [RecommendableItemFactory.build(is_geolocated=False, total_offers=1) for _ in range(5)]
    mock_vertex_retrieval[0].return_value = unauthenticated_items
    mock_vertex_ranking[0].side_effect = lambda offers, _ctx: offers
    mock_tracking = mocker.patch("controllers.pipeline_playlist_recommendation.log_past_offer_context_to_sink")

    response = await generate_playlist_recommendations(
        db=db_session,
        user_id=unknown_user_id,
        latitude=None,
        longitude=None,
        params=PlaylistRequestParams(),
    )

    assert isinstance(response, RecommendationResponse)
    assert len(response.playlist_recommended_offers) > 0
    (
        mock_tracking.assert_not_called(),
        (
            "Tracking must be skipped for unauthenticated users to avoid polluting training data "
            "with non-personalised engagement signals."
        ),
    )
    response.params.reco_origin = "unknown"
