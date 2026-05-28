from datetime import UTC
from datetime import datetime

import pytest

from core.retrieval import _build_playlist_recommendation_search_filters
from core.retrieval import _build_similar_offer_search_filters
from core.retrieval import build_playlist_recommendation_retrieval_payload
from core.retrieval import build_similar_offer_retrieval_payload
from core.retrieval import filter_out_already_booked_items
from core.retrieval import resolve_closest_venues_from_items
from core.user_context import UserContext
from schemas.categories import CategoryEnum
from schemas.categories import SearchGroupNameEnum
from schemas.categories import SubcategoryEnum
from schemas.playlist_recommendation import PlaylistRequestParams

from tests.factories.models import NonRecommendableItemsFactory
from tests.factories.schemas import RecommendableItemFactory
from tests.factories.schemas import UserContextFactory


# ---------------------------------------------------------------------------
# _build_similar_offer_search_filters
# ---------------------------------------------------------------------------


def test_build_similar_offer_search_filters_returns_empty_and_list_when_no_filters_provided():
    """When no filters are provided, should return an empty $and list."""
    result = _build_similar_offer_search_filters()

    assert result == {"$and": []}


def test_build_similar_offer_search_filters_with_single_filter_type():
    """When one filter type is provided, should return correct structure."""
    result = _build_similar_offer_search_filters(categories=[CategoryEnum.LIVRE, CategoryEnum.INSTRUMENT])

    assert result == {"$and": [{"category": {"$in": ["LIVRE", "INSTRUMENT"]}}]}


def test_build_similar_offer_search_filters_with_all_parameters_combined():
    """When all filter types are provided, should combine them in $and list."""
    result = _build_similar_offer_search_filters(
        categories=[CategoryEnum.LIVRE],
        subcategories=[SubcategoryEnum.ABO_CONCERT],
        search_group_names=[SearchGroupNameEnum.CONCERTS_FESTIVALS, SearchGroupNameEnum.CARTES_JEUNES],
    )

    assert result == {
        "$and": [
            {"category": {"$in": ["LIVRE"]}},
            {"subcategory_id": {"$in": ["ABO_CONCERT"]}},
            {"search_group_name": {"$in": ["CONCERTS_FESTIVALS", "CARTES_JEUNES"]}},
        ]
    }


def test_build_similar_offer_search_filters_ignores_empty_lists():
    """When empty lists are provided, should not include them in filters."""
    result = _build_similar_offer_search_filters(
        categories=[],
        subcategories=[SubcategoryEnum.ABO_CONCERT],
        search_group_names=[],
    )

    assert result == {"$and": [{"subcategory_id": {"$in": ["ABO_CONCERT"]}}]}


# ---------------------------------------------------------------------------
# _build_playlist_recommendation_search_filters
# ---------------------------------------------------------------------------


def _user(remaining_credit: float = 150.0) -> UserContext:
    return UserContext(user_id="user-1", remaining_credit=remaining_credit)


def test_playlist_filters_uses_stock_beginning_date_for_events():
    """Event-type offers filter by when the event starts, not when the offer was created."""
    params = PlaylistRequestParams(is_event=True, start_date=datetime(2024, 6, 1, tzinfo=UTC))
    conditions = _build_playlist_recommendation_search_filters(_user(), params)["$and"]
    assert any("stock_beginning_date" in c for c in conditions)
    assert not any("offer_creation_date" in c for c in conditions)


def test_playlist_filters_uses_offer_creation_date_for_non_events():
    """Non-event offers filter by creation date, and stock_beginning_date must be absent from conditions."""
    params = PlaylistRequestParams(is_event=False, start_date=datetime(2024, 6, 1, tzinfo=UTC))
    conditions = _build_playlist_recommendation_search_filters(_user(), params)["$and"]
    assert any("offer_creation_date" in c for c in conditions)
    assert not any("stock_beginning_date" in c for c in conditions)


def test_playlist_filters_price_is_bounded_by_price_max_when_lower_than_credit():
    """Effective price cap is min(price_max, remaining_credit); price_max wins when it is the stricter bound."""
    params = PlaylistRequestParams(price_max=50.0)
    conditions = _build_playlist_recommendation_search_filters(_user(remaining_credit=100.0), params)["$and"]
    assert {"stock_price": {"$lte": 50.0}} in conditions


def test_playlist_filters_price_is_bounded_by_credit_when_lower_than_price_max():
    """User credit wins when it is lower than the requested price_max."""
    params = PlaylistRequestParams(price_max=200.0)
    conditions = _build_playlist_recommendation_search_filters(_user(remaining_credit=80.0), params)["$and"]
    assert {"stock_price": {"$lte": 80.0}} in conditions


def test_playlist_filters_price_falls_back_to_credit_when_no_price_max():
    """When no price_max is specified, the user's remaining credit becomes the sole upper bound."""
    conditions = _build_playlist_recommendation_search_filters(_user(remaining_credit=120.0), PlaylistRequestParams())[
        "$and"
    ]
    assert {"stock_price": {"$lte": 120.0}} in conditions


def test_playlist_filters_is_restrained_none_still_adds_restrained_filter():
    """
    is_restrained=None is coerced back to True in the filter logic, so the restrained filter is always added
    unless explicitly False.

    This mirrors the Pydantic model default of True and prevents accidentally surfacing restrained offers.
    """
    params = PlaylistRequestParams(is_restrained=None)
    conditions = _build_playlist_recommendation_search_filters(_user(), params)["$and"]
    assert {"is_restrained": {"$eq": 0.0}} in conditions


def test_playlist_filters_is_digital_true_maps_to_not_geolocated():
    """is_digital=True means online; Vertex's vocabulary maps this to is_geolocated==0 — the logic is inverted."""
    params = PlaylistRequestParams(is_digital=True)
    conditions = _build_playlist_recommendation_search_filters(_user(), params)["$and"]
    assert {"is_geolocated": {"$eq": 0.0}} in conditions


def test_playlist_filters_is_digital_false_maps_to_geolocated_only():
    """is_digital=False means in-person; Vertex restricts to is_geolocated==1."""
    params = PlaylistRequestParams(is_digital=False)
    conditions = _build_playlist_recommendation_search_filters(_user(), params)["$and"]
    assert {"is_geolocated": {"$eq": 1.0}} in conditions


def test_playlist_filters_empty_list_fields_are_not_added():
    """Empty lists must not produce a $in [] condition that would match nothing."""
    params = PlaylistRequestParams(categories=[], gtl_ids=[])
    conditions = _build_playlist_recommendation_search_filters(_user(), params)["$and"]
    assert not any("category" in c for c in conditions)
    assert not any("gtl_id" in c for c in conditions)


def test_playlist_filters_adds_end_date_condition():
    params = PlaylistRequestParams(end_date=datetime(2024, 12, 31, tzinfo=UTC))
    conditions = _build_playlist_recommendation_search_filters(_user(), params)["$and"]
    assert any("offer_creation_date" in c and "$lte" in c["offer_creation_date"] for c in conditions)


def test_playlist_filters_adds_price_min_condition():
    params = PlaylistRequestParams(price_min=10.0)
    conditions = _build_playlist_recommendation_search_filters(_user(), params)["$and"]
    assert {"stock_price": {"$gte": 10.0}} in conditions


def test_playlist_filters_adds_is_duo_condition():
    params = PlaylistRequestParams(is_duo=True)
    conditions = _build_playlist_recommendation_search_filters(_user(), params)["$and"]
    assert {"offer_is_duo": {"$eq": 1.0}} in conditions


def test_playlist_filters_adds_non_empty_list_as_in_condition():
    params = PlaylistRequestParams(categories=[CategoryEnum.LIVRE])
    conditions = _build_playlist_recommendation_search_filters(_user(), params)["$and"]
    assert {"category": {"$in": [CategoryEnum.LIVRE]}} in conditions


# ---------------------------------------------------------------------------
# build_playlist_recommendation_retrieval_payload
# ---------------------------------------------------------------------------


def test_playlist_payload_cold_start_uses_tops_model():
    """Cold start switches to a popularity-based model and adds vector_column_name and re_rank=0.

    These keys are absent in the warm path; their presence here distinguishes the two branches.
    """
    user = UserContext(user_id="u", is_authenticated=False)
    payload = build_playlist_recommendation_retrieval_payload(user, "call-1", PlaylistRequestParams())
    assert payload["model_type"] == "tops"
    assert payload["vector_column_name"] == "booking_number_desc"
    assert payload["re_rank"] == 0


def test_playlist_payload_warm_user_uses_recommendation_model():
    """Warm users use collaborative filtering; the cold-start-specific keys must be absent from the payload."""
    user = UserContext(user_id="u", is_authenticated=True, bookings_count=2)
    payload = build_playlist_recommendation_retrieval_payload(user, "call-1", PlaylistRequestParams())
    assert payload["model_type"] == "recommendation"
    assert "vector_column_name" not in payload
    assert "re_rank" not in payload


# ---------------------------------------------------------------------------
# build_similar_offer_retrieval_payload
# ---------------------------------------------------------------------------


def test_similar_offer_payload_with_item_id_uses_similar_offer_model():
    """A known anchor item_id triggers nearest-neighbor search; cold-start vector keys must be absent."""
    payload = build_similar_offer_retrieval_payload(UserContextFactory.build(), "call-1", item_id="item-42")
    assert payload["model_type"] == "similar_offer"
    assert "vector_column_name" not in payload
    assert "re_rank" not in payload


def test_similar_offer_payload_without_item_id_uses_tops_model():
    """Without an anchor item, the API falls back to the popularity-based tops model."""
    payload = build_similar_offer_retrieval_payload(UserContextFactory.build(), "call-1", item_id=None)
    assert payload["model_type"] == "tops"
    assert payload["vector_column_name"] == "booking_number_desc"
    assert payload["re_rank"] == 0


def test_similar_offer_payload_omits_params_when_no_filters_provided():
    """The params key must be omitted entirely (not set to {}) when no category filters are given."""
    payload = build_similar_offer_retrieval_payload(UserContextFactory.build(), "call-1", item_id="item-1")
    assert "params" not in payload


# ---------------------------------------------------------------------------
# filter_out_already_booked_items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_booked_items_returns_empty_for_empty_input(db_session):
    result = await filter_out_already_booked_items(db_session, [], "user-1")
    assert result == []


@pytest.mark.asyncio
async def test_filter_booked_items_removes_booked_and_keeps_new(db_session):
    """Cross-references candidates against NonRecommendableItems and removes any the user has already booked."""
    await NonRecommendableItemsFactory.create_async(user_id="user-1", item_id="item-booked")

    candidates = [
        RecommendableItemFactory.build(item_id="item-booked"),
        RecommendableItemFactory.build(item_id="item-new"),
    ]

    result = await filter_out_already_booked_items(db_session, candidates, "user-1")

    assert len(result) == 1
    assert result[0].item_id == "item-new"


# ---------------------------------------------------------------------------
# resolve_closest_venues_from_items
# ---------------------------------------------------------------------------

_PARIS = (48.8566, 2.3522)
_VERSAILLES = (48.8048, 2.1203)  # ~17 km from Paris
_LONDON = (51.5074, -0.1278)  # ~343 km from Paris


@pytest.mark.asyncio
async def test_resolve_returns_empty_for_empty_input(db_session):
    result = await resolve_closest_venues_from_items(db_session, [], UserContextFactory.build())
    assert result == []


@pytest.mark.asyncio
async def test_resolve_fast_tracks_digital_item_without_computing_distance(db_session):
    """Digital (non-geolocated) items bypass the DB and are returned with no distance."""
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])
    item = RecommendableItemFactory.build(is_geolocated=False, total_offers=10)

    result = await resolve_closest_venues_from_items(db_session, [item], user)

    assert len(result) == 1
    assert result[0].offer_user_distance is None


@pytest.mark.asyncio
async def test_resolve_computes_distance_for_single_venue_geolocated_item(db_session):
    """Single-venue physical items are fast-tracked but their distance from the user is computed via haversine."""
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])
    item = RecommendableItemFactory.build(
        is_geolocated=True,
        total_offers=1,
        example_venue_latitude=_VERSAILLES[0],
        example_venue_longitude=_VERSAILLES[1],
    )

    max_distance_meters = 50_000
    result = await resolve_closest_venues_from_items(db_session, [item], user)

    assert len(result) == 1
    assert result[0].offer_user_distance is not None
    assert result[0].offer_user_distance < max_distance_meters


@pytest.mark.asyncio
async def test_resolve_skips_geolocated_item_when_user_has_no_gps(db_session):
    """A geolocated single-venue item is silently dropped when the user has no GPS coordinates."""
    user = UserContext(user_id="u")  # no GPS
    item = RecommendableItemFactory.build(is_geolocated=True, total_offers=1)

    result = await resolve_closest_venues_from_items(db_session, [item], user)

    assert result == []


@pytest.mark.asyncio
async def test_resolve_skips_item_beyond_100km(db_session):
    """Items whose closest venue exceeds the 100 km radius are excluded regardless of relevance score."""
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])
    item = RecommendableItemFactory.build(
        is_geolocated=True,
        total_offers=1,
        example_venue_latitude=_LONDON[0],
        example_venue_longitude=_LONDON[1],
    )

    result = await resolve_closest_venues_from_items(db_session, [item], user)

    assert result == []


@pytest.mark.asyncio
async def test_resolve_drops_multi_venue_item_when_user_has_no_gps(db_session):
    """
    Multi-venue items are only routed to the DB query when the user is geolocated;
    without GPS they are silently dropped.
    """
    user = UserContext(user_id="u")  # no GPS
    item = RecommendableItemFactory.build(is_geolocated=True, total_offers=5)

    result = await resolve_closest_venues_from_items(db_session, [item], user)

    assert result == []


@pytest.mark.asyncio
async def test_resolve_sorts_offers_by_distance_with_none_last(db_session):
    """
    The final list is sorted ascending by distance;
    offers with no distance (digital items) are treated as inf and sorted last.

    Mixing geolocated and digital items in the input validates both the sort key and the None-last sentinel.
    """
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])

    near_item = RecommendableItemFactory.build(
        is_geolocated=True,
        total_offers=1,
        example_venue_latitude=_VERSAILLES[0],
        example_venue_longitude=_VERSAILLES[1],
    )
    far_item = RecommendableItemFactory.build(
        is_geolocated=True,
        total_offers=1,
        example_venue_latitude=48.0,
        example_venue_longitude=1.0,
    )
    digital_item = RecommendableItemFactory.build(is_geolocated=False)

    result = await resolve_closest_venues_from_items(db_session, [far_item, near_item, digital_item], user)

    distances = [r.offer_user_distance for r in result]
    non_none = [d for d in distances if d is not None]
    assert non_none == sorted(non_none)
    assert distances[-1] is None
