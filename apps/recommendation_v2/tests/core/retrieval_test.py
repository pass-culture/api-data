from datetime import UTC
from datetime import datetime
from unittest.mock import MagicMock

import pytest

import config.settings as _settings
from connectors.redis_api import RedisAPI
from core.retrieval import _build_playlist_recommendation_search_filters
from core.retrieval import _build_similar_offer_search_filters
from core.retrieval import _fetch_tops_offer_resolutions_from_cache
from core.retrieval import _is_retrieval_cache_enabled_for_model_type
from core.retrieval import _resolve_multi_venue_items
from core.retrieval import _store_tops_offer_resolutions_in_cache
from core.retrieval import build_playlist_recommendation_retrieval_payload
from core.retrieval import build_similar_offer_retrieval_payload
from core.retrieval import fetch_all_playlist_recommendation_retrieval_predictions_from_vertex
from core.retrieval import fetch_graph_retrieval_predictions
from core.retrieval import fetch_retrieval_predictions
from core.retrieval import filter_out_already_booked_items
from core.retrieval import resolve_closest_venues_from_items
from core.user_context import UserContext
from schemas.categories import CategoryEnum
from schemas.categories import SearchGroupNameEnum
from schemas.categories import SubcategoryEnum
from schemas.playlist_recommendation import PlaylistRequestParams
from schemas.vertex_prediction_item import ItemOrigin

from tests.conftest import patch_all_caches_disabled
from tests.conftest import patch_all_caches_enabled
from tests.factories.models import NonRecommendableItemsFactory
from tests.factories.schemas import RecommendableItemFactory
from tests.factories.schemas import UserContextFactory
from tests.factories.schemas import VertexPredictionResultFactory


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
    params = PlaylistRequestParams(categories=[])
    conditions = _build_playlist_recommendation_search_filters(_user(), params)["$and"]
    assert not any("category" in c for c in conditions)


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


def test_playlist_filters_clamps_negative_remaining_credit_to_zero():
    """
    When a user has a negative remaining_credit (due to corrupted DB data), the effective
    price cap must be clamped to 0 instead of producing a nonsensical negative filter
    (e.g. stock_price <= -5) that would return zero results.
    """
    conditions = _build_playlist_recommendation_search_filters(_user(remaining_credit=-50.0), PlaylistRequestParams())[
        "$and"
    ]
    assert {"stock_price": {"$lte": 0.0}} in conditions


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


# ---------------------------------------------------------------------------
# fetch_all_playlist_recommendation_retrieval_predictions_from_vertex
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_all_predictions_deduplicates_items_across_endpoints(mocker):
    """
    Verifies that items returned by multiple retrieval endpoints are deduplicated correctly.

    A warm user triggers 4 parallel retrieval calls:
        - Endpoint 1 (personalized recommendation): [item-A, item-B]
        - Endpoint 2 (tops — booking_number):       [item-A, item-C]   ← item-A duplicated
        - Endpoint 3 (tops — release_trend):        [item-B, item-D]   ← item-B duplicated
        - Endpoint 4 (tops — creation_trend):       [item-C, item-E]   ← item-C duplicated

    Expected behaviour:
    - The final list contains exactly 5 unique items: [item-A, item-B, item-C, item-D, item-E].
    - The order of first occurrence is preserved (item-A before item-B, etc.).
    - No item_id appears more than once.
    """
    item_a = RecommendableItemFactory.build(item_id="item-A")
    item_b = RecommendableItemFactory.build(item_id="item-B")
    item_c = RecommendableItemFactory.build(item_id="item-C")
    item_d = RecommendableItemFactory.build(item_id="item-D")
    item_e = RecommendableItemFactory.build(item_id="item-E")

    endpoint_results = [
        VertexPredictionResultFactory.build(predictions=[item_a, item_b]),
        VertexPredictionResultFactory.build(predictions=[item_a, item_c]),
        VertexPredictionResultFactory.build(predictions=[item_b, item_d]),
        VertexPredictionResultFactory.build(predictions=[item_c, item_e]),
    ]

    mocker.patch(
        "core.retrieval.fetch_retrieval_predictions_from_vertex",
        new_callable=mocker.AsyncMock,
        side_effect=endpoint_results,
    )

    # 4 dummy payloads — one per warm-start endpoint
    dummy_payloads = [{} for _ in range(4)]

    result = await fetch_all_playlist_recommendation_retrieval_predictions_from_vertex(dummy_payloads)

    result_item_ids = [item.item_id for item in result]

    expected_unique_items_after_deduplication = 5
    assert len(result_item_ids) == expected_unique_items_after_deduplication, (
        f"Expected 5 unique items after deduplication, got {len(result_item_ids)}: {result_item_ids}"
    )
    assert len(set(result_item_ids)) == len(result_item_ids), f"Duplicate item_ids found in result: {result_item_ids}"
    assert result_item_ids == ["item-A", "item-B", "item-C", "item-D", "item-E"], (
        "First-occurrence order must be preserved across endpoints."
    )


# ---------------------------------------------------------------------------
# _is_retrieval_cache_enabled_for_model_type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("model_type", "flag_attr", "expected"),
    [
        pytest.param("similar_offer", "RETRIEVAL_CACHE_SIMILAR_OFFER_ENABLED", True, id="similar_offer_enabled"),
        pytest.param("tops", "RETRIEVAL_CACHE_PLAYLIST_TOPS_ENABLED", True, id="tops_enabled"),
        pytest.param(
            "recommendation", "RETRIEVAL_CACHE_PLAYLIST_PERSONALIZED_ENABLED", True, id="recommendation_enabled"
        ),
        pytest.param("similar_offer", "RETRIEVAL_CACHE_SIMILAR_OFFER_ENABLED", False, id="similar_offer_disabled"),
        pytest.param("tops", "RETRIEVAL_CACHE_PLAYLIST_TOPS_ENABLED", False, id="tops_disabled"),
        pytest.param(
            "recommendation", "RETRIEVAL_CACHE_PLAYLIST_PERSONALIZED_ENABLED", False, id="recommendation_disabled"
        ),
    ],
)
def test_is_retrieval_cache_enabled_for_model_type_respects_its_flag(mocker, model_type, flag_attr, expected):
    mocker.patch.object(_settings, flag_attr, new=expected)
    assert _is_retrieval_cache_enabled_for_model_type(model_type) is expected


def test_is_retrieval_cache_enabled_returns_false_for_unknown_model_type(mocker):
    """Unknown model_types must never be considered cacheable, regardless of flag values."""
    mocker.patch.object(_settings, "RETRIEVAL_CACHE_SIMILAR_OFFER_ENABLED", new=True)
    mocker.patch.object(_settings, "RETRIEVAL_CACHE_PLAYLIST_TOPS_ENABLED", new=True)
    mocker.patch.object(_settings, "RETRIEVAL_CACHE_PLAYLIST_PERSONALIZED_ENABLED", new=True)

    assert _is_retrieval_cache_enabled_for_model_type("graph") is False
    assert _is_retrieval_cache_enabled_for_model_type("") is False
    assert _is_retrieval_cache_enabled_for_model_type("unknown") is False


# ---------------------------------------------------------------------------
# fetch_retrieval_predictions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_retrieval_predictions_skips_cache_when_disabled_and_calls_vertex(mocker):
    """When the cache is disabled, fetch_retrieval_predictions must call Vertex directly."""
    patch_all_caches_disabled(mocker)
    expected_result = VertexPredictionResultFactory.build()

    mock_vertex = mocker.patch(
        "core.retrieval.fetch_retrieval_predictions_from_vertex",
        new_callable=mocker.AsyncMock,
        return_value=expected_result,
    )
    mock_redis_fetch = mocker.patch(
        "core.retrieval.redis_api.fetch_cached_retrieval_predictions",
        new_callable=mocker.AsyncMock,
    )
    mock_redis_store = mocker.patch(
        "core.retrieval.redis_api.store_retrieval_predictions",
        new_callable=mocker.AsyncMock,
    )

    payload = {"call_id": "c1", "user_id": "u1", "model_type": "tops"}
    result = await fetch_retrieval_predictions(payload)

    assert result == expected_result
    mock_vertex.assert_called_once_with(payload)
    mock_redis_fetch.assert_not_called()
    mock_redis_store.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_retrieval_predictions_returns_cached_result_on_hit(mocker):
    """On a cache hit, fetch_retrieval_predictions must return the cached result without calling Vertex."""
    patch_all_caches_enabled(mocker)
    cached_items = RecommendableItemFactory.batch(3)
    serialized_cached_items = [item.model_dump(mode="json") for item in cached_items]

    mocker.patch(
        "core.retrieval.redis_api.fetch_cached_retrieval_predictions",
        new_callable=mocker.AsyncMock,
        return_value=serialized_cached_items,
    )
    mock_vertex = mocker.patch(
        "core.retrieval.fetch_retrieval_predictions_from_vertex",
        new_callable=mocker.AsyncMock,
    )
    mock_redis_store = mocker.patch(
        "core.retrieval.redis_api.store_retrieval_predictions",
        new_callable=mocker.AsyncMock,
    )

    payload = {"call_id": "c1", "user_id": "u1", "model_type": "tops"}
    result = await fetch_retrieval_predictions(payload)

    assert len(result.predictions) == len(cached_items)
    mock_vertex.assert_not_called()
    mock_redis_store.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_retrieval_predictions_stores_result_on_cache_miss(mocker):
    """On a cache miss, fetch_retrieval_predictions must fetch from Vertex and store the result in Redis."""
    patch_all_caches_enabled(mocker)
    fresh_result = VertexPredictionResultFactory.build()
    fresh_result.status = "success"

    mocker.patch(
        "core.retrieval.redis_api.fetch_cached_retrieval_predictions",
        new_callable=mocker.AsyncMock,
        return_value=None,
    )
    mocker.patch(
        "core.retrieval.fetch_retrieval_predictions_from_vertex",
        new_callable=mocker.AsyncMock,
        return_value=fresh_result,
    )
    mock_redis_store = mocker.patch(
        "core.retrieval.redis_api.store_retrieval_predictions",
        new_callable=mocker.AsyncMock,
    )

    payload = {"call_id": "c1", "user_id": "u1", "model_type": "tops"}
    result = await fetch_retrieval_predictions(payload)

    assert result == fresh_result
    mock_redis_store.assert_called_once()
    store_kwargs = mock_redis_store.call_args
    assert store_kwargs.args[0] == payload
    assert store_kwargs.kwargs["namespace"] == RedisAPI.RETRIEVAL_NAMESPACE


@pytest.mark.asyncio
async def test_fetch_retrieval_predictions_does_not_store_on_vertex_error(mocker):
    """When Vertex returns a non-success status, the result must not be stored in Redis."""
    patch_all_caches_enabled(mocker)
    error_result = VertexPredictionResultFactory.build()
    error_result.status = "error"
    error_result.predictions = []

    mocker.patch(
        "core.retrieval.redis_api.fetch_cached_retrieval_predictions",
        new_callable=mocker.AsyncMock,
        return_value=None,
    )
    mocker.patch(
        "core.retrieval.fetch_retrieval_predictions_from_vertex",
        new_callable=mocker.AsyncMock,
        return_value=error_result,
    )
    mock_redis_store = mocker.patch(
        "core.retrieval.redis_api.store_retrieval_predictions",
        new_callable=mocker.AsyncMock,
    )

    payload = {"call_id": "c1", "user_id": "u1", "model_type": "tops"}
    await fetch_retrieval_predictions(payload)

    mock_redis_store.assert_not_called()


# ---------------------------------------------------------------------------
# fetch_graph_retrieval_predictions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_graph_retrieval_predictions_skips_cache_when_disabled(mocker):
    """When the cache is disabled, fetch_graph_retrieval_predictions must call graph Vertex directly."""
    patch_all_caches_disabled(mocker)
    expected_result = VertexPredictionResultFactory.build()

    mock_vertex = mocker.patch(
        "core.retrieval.fetch_graph_predictions_from_vertex",
        new_callable=mocker.AsyncMock,
        return_value=expected_result,
    )
    mock_redis_fetch = mocker.patch(
        "core.retrieval.redis_api.fetch_cached_retrieval_predictions",
        new_callable=mocker.AsyncMock,
    )
    mock_redis_store = mocker.patch(
        "core.retrieval.redis_api.store_retrieval_predictions",
        new_callable=mocker.AsyncMock,
    )

    payload = {"call_id": "c1", "user_id": "u1", "model_type": "similar_offer"}
    result = await fetch_graph_retrieval_predictions(payload)

    assert result == expected_result
    mock_vertex.assert_called_once_with(payload)
    mock_redis_fetch.assert_not_called()
    mock_redis_store.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_graph_retrieval_predictions_uses_graph_namespace(mocker):
    """The graph namespace must be used, not the standard one, to prevent cache collisions."""
    patch_all_caches_enabled(mocker)
    fresh_result = VertexPredictionResultFactory.build()
    fresh_result.status = "success"

    mocker.patch(
        "core.retrieval.redis_api.fetch_cached_retrieval_predictions",
        new_callable=mocker.AsyncMock,
        return_value=None,
    )
    mocker.patch(
        "core.retrieval.fetch_graph_predictions_from_vertex",
        new_callable=mocker.AsyncMock,
        return_value=fresh_result,
    )
    mock_redis_store = mocker.patch(
        "core.retrieval.redis_api.store_retrieval_predictions",
        new_callable=mocker.AsyncMock,
    )

    payload = {"call_id": "c1", "user_id": "u1", "model_type": "similar_offer"}
    await fetch_graph_retrieval_predictions(payload)

    mock_redis_store.assert_called_once()
    store_kwargs = mock_redis_store.call_args
    assert store_kwargs.kwargs["namespace"] == RedisAPI.RETRIEVAL_GRAPH_NAMESPACE


@pytest.mark.asyncio
async def test_fetch_retrieval_predictions_does_not_cache_unknown_model_type(mocker):
    """Unknown model_types must never trigger a cache read or write."""
    patch_all_caches_enabled(mocker)
    expected_result = VertexPredictionResultFactory.build()

    mocker.patch(
        "core.retrieval.fetch_retrieval_predictions_from_vertex",
        new_callable=mocker.AsyncMock,
        return_value=expected_result,
    )
    mock_redis_fetch = mocker.patch(
        "core.retrieval.redis_api.fetch_cached_retrieval_predictions",
        new_callable=mocker.AsyncMock,
    )
    mock_redis_store = mocker.patch(
        "core.retrieval.redis_api.store_retrieval_predictions",
        new_callable=mocker.AsyncMock,
    )

    payload = {"call_id": "c1", "user_id": "u1", "model_type": "unknown_type"}
    await fetch_retrieval_predictions(payload)

    mock_redis_fetch.assert_not_called()
    mock_redis_store.assert_not_called()


# ===========================================================================
# Helpers shared by cache-strategy tests
# ===========================================================================

_PARIS = (48.8566, 2.3522)
_VERSAILLES = (48.8048, 2.1203)  # ~17 km from Paris
_LONDON = (51.5074, -0.1278)  # ~343 km from Paris

# Arbitrary H3 cell used when mocking get_h3_index_from_coordinates
_H3_CELL = "881f1d4a11fffff"


def _make_db_offer(
    item_id: str,
    offer_id: str,
    lat: float,
    lng: float,
    creation_date: datetime | None = None,
    stock_date: datetime | None = None,
) -> MagicMock:
    """
    Creates a lightweight mock mimicking a RecommendableOffers ORM row as returned
    by find_closest_offers_with_h3_index (only the attributes read by the production code).
    """
    mock = MagicMock()
    mock.item_id = item_id
    mock.offer_id = offer_id
    mock.venue_latitude = lat
    mock.venue_longitude = lng
    mock.offer_creation_date = creation_date
    mock.stock_beginning_date = stock_date
    return mock


def _cached_offer_payload(
    offer_id: str,
    lat: float,
    lng: float,
    creation_date: str | None = None,
    stock_date: str | None = None,
) -> dict:
    """Builds a minimal cache payload dict as stored by _store_tops_offer_resolutions_in_cache."""
    return {
        "offer_id": offer_id,
        "venue_latitude": lat,
        "venue_longitude": lng,
        "offer_creation_date": creation_date,
        "stock_beginning_date": stock_date,
    }


# ===========================================================================
# _fetch_tops_offer_resolutions_from_cache
# ===========================================================================


@pytest.mark.asyncio
async def test_fetch_tops_offer_resolutions_from_cache_all_hits(mocker):
    """All tops items found in cache → cache_hits contains all items, misses list is empty."""
    tops_item_ids = ["item-1", "item-2"]
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])

    mocker.patch("core.retrieval.get_h3_index_from_coordinates", return_value=_H3_CELL)
    mocker.patch(
        "core.retrieval.redis_api.mget_resolved_offers",
        new_callable=mocker.AsyncMock,
        return_value=[
            _cached_offer_payload("offer-1", _PARIS[0], _PARIS[1]),
            _cached_offer_payload("offer-2", _PARIS[0], _PARIS[1]),
        ],
    )

    cache_hits, misses, h3_cell = await _fetch_tops_offer_resolutions_from_cache(tops_item_ids, user)

    assert set(cache_hits.keys()) == {"item-1", "item-2"}
    assert misses == []
    assert h3_cell == _H3_CELL


@pytest.mark.asyncio
async def test_fetch_tops_offer_resolutions_from_cache_all_misses(mocker):
    """No tops items found in cache → cache_hits is empty, all items are in the miss list."""
    tops_item_ids = ["item-1", "item-2"]
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])

    mocker.patch("core.retrieval.get_h3_index_from_coordinates", return_value=_H3_CELL)
    mocker.patch(
        "core.retrieval.redis_api.mget_resolved_offers",
        new_callable=mocker.AsyncMock,
        return_value=[None, None],
    )

    cache_hits, misses, h3_cell = await _fetch_tops_offer_resolutions_from_cache(tops_item_ids, user)

    assert cache_hits == {}
    assert misses == ["item-1", "item-2"]
    assert h3_cell == _H3_CELL


@pytest.mark.asyncio
async def test_fetch_tops_offer_resolutions_from_cache_partial_hits(mocker):
    """Some items in cache, some not → correct split between hits and misses."""
    tops_item_ids = ["item-1", "item-2", "item-3"]
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])

    mocker.patch("core.retrieval.get_h3_index_from_coordinates", return_value=_H3_CELL)
    mocker.patch(
        "core.retrieval.redis_api.mget_resolved_offers",
        new_callable=mocker.AsyncMock,
        return_value=[
            _cached_offer_payload("offer-1", _PARIS[0], _PARIS[1]),  # hit
            None,  # miss
            None,  # miss
        ],
    )

    cache_hits, misses, h3_cell = await _fetch_tops_offer_resolutions_from_cache(tops_item_ids, user)

    assert set(cache_hits.keys()) == {"item-1"}
    assert misses == ["item-2", "item-3"]
    assert h3_cell == _H3_CELL


@pytest.mark.asyncio
async def test_fetch_tops_offer_resolutions_from_cache_uses_h3_resolution_from_settings(mocker):
    """The H3 cell must be derived using settings.OFFER_RESOLUTION_CACHE_H3_RESOLUTION."""
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])

    mock_h3 = mocker.patch("core.retrieval.get_h3_index_from_coordinates", return_value=_H3_CELL)
    mocker.patch(
        "core.retrieval.redis_api.mget_resolved_offers",
        new_callable=mocker.AsyncMock,
        return_value=[None],
    )

    await _fetch_tops_offer_resolutions_from_cache(["item-1"], user)

    mock_h3.assert_called_once_with(_PARIS[0], _PARIS[1], resolution=_settings.OFFER_RESOLUTION_CACHE_H3_RESOLUTION)


@pytest.mark.asyncio
async def test_fetch_tops_offer_resolutions_from_cache_builds_correct_cache_keys(mocker):
    """Cache keys must follow the 'offer_resolution:r{resolution}:{h3_cell}:{item_id}' pattern."""
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])

    mocker.patch("core.retrieval.get_h3_index_from_coordinates", return_value=_H3_CELL)
    mock_mget = mocker.patch(
        "core.retrieval.redis_api.mget_resolved_offers",
        new_callable=mocker.AsyncMock,
        return_value=[None, None],
    )

    await _fetch_tops_offer_resolutions_from_cache(["item-A", "item-B"], user)

    cache_keys_passed = mock_mget.call_args.args[0]
    resolution = _settings.OFFER_RESOLUTION_CACHE_H3_RESOLUTION
    assert cache_keys_passed == [
        f"offer_resolution:r{resolution}:{_H3_CELL}:item-A",
        f"offer_resolution:r{resolution}:{_H3_CELL}:item-B",
    ]


# ===========================================================================
# _store_tops_offer_resolutions_in_cache
# ===========================================================================


@pytest.mark.asyncio
async def test_store_tops_offer_resolutions_stores_only_resolved_items(mocker):
    """Items not resolved by the DB (no matching row) must not be stored in cache."""
    resolved_offer = _make_db_offer("item-1", "offer-1", _PARIS[0], _PARIS[1])
    db_rows = [(resolved_offer, 1000.0)]  # item-1 resolved, item-2 absent
    tops_cache_misses = ["item-1", "item-2"]

    mock_mset = mocker.patch("core.retrieval.redis_api.mset_resolved_offers", new_callable=mocker.AsyncMock)
    mocker.patch.object(RedisAPI, "calculate_seconds_until_next_database_population_time", return_value=3600)

    await _store_tops_offer_resolutions_in_cache(tops_cache_misses, db_rows, h3_cell=_H3_CELL)

    mock_mset.assert_called_once()
    stored_entries: dict = mock_mset.call_args.args[0]
    assert len(stored_entries) == 1
    assert any("item-1" in key for key in stored_entries)
    assert not any("item-2" in key for key in stored_entries)


@pytest.mark.asyncio
async def test_store_tops_offer_resolutions_no_mset_when_all_items_unresolved(mocker):
    """When the DB resolves none of the cache-miss items, mset must not be called."""
    mock_mset = mocker.patch("core.retrieval.redis_api.mset_resolved_offers", new_callable=mocker.AsyncMock)
    mocker.patch.object(RedisAPI, "calculate_seconds_until_next_database_population_time", return_value=3600)

    await _store_tops_offer_resolutions_in_cache(["item-1", "item-2"], db_rows=[], h3_cell=_H3_CELL)

    mock_mset.assert_not_called()


@pytest.mark.asyncio
async def test_store_tops_offer_resolutions_serializes_dates_as_iso_strings(mocker):
    """Dates in the cached payload must be ISO 8601 strings (JSON-safe for Redis)."""
    creation_dt = datetime(2024, 3, 15, 10, 30, tzinfo=UTC)
    stock_dt = datetime(2024, 5, 20, tzinfo=UTC)
    resolved_offer = _make_db_offer("item-1", "offer-1", _PARIS[0], _PARIS[1], creation_dt, stock_dt)

    mock_mset = mocker.patch("core.retrieval.redis_api.mset_resolved_offers", new_callable=mocker.AsyncMock)
    mocker.patch.object(RedisAPI, "calculate_seconds_until_next_database_population_time", return_value=3600)

    await _store_tops_offer_resolutions_in_cache(["item-1"], [(resolved_offer, 500.0)], h3_cell=_H3_CELL)

    stored_entries: dict = mock_mset.call_args.args[0]
    cached_payload = next(iter(stored_entries.values()))
    assert cached_payload["offer_creation_date"] == creation_dt.isoformat()
    assert cached_payload["stock_beginning_date"] == stock_dt.isoformat()


@pytest.mark.asyncio
async def test_store_tops_offer_resolutions_handles_none_dates(mocker):
    """When an offer has no dates, the cached payload must store None for those fields."""
    resolved_offer = _make_db_offer("item-1", "offer-1", _PARIS[0], _PARIS[1], creation_date=None, stock_date=None)

    mock_mset = mocker.patch("core.retrieval.redis_api.mset_resolved_offers", new_callable=mocker.AsyncMock)
    mocker.patch.object(RedisAPI, "calculate_seconds_until_next_database_population_time", return_value=3600)

    await _store_tops_offer_resolutions_in_cache(["item-1"], [(resolved_offer, 200.0)], h3_cell=_H3_CELL)

    stored_entries: dict = mock_mset.call_args.args[0]
    cached_payload = next(iter(stored_entries.values()))
    assert cached_payload["offer_creation_date"] is None
    assert cached_payload["stock_beginning_date"] is None


@pytest.mark.asyncio
async def test_store_tops_offer_resolutions_uses_ttl_until_next_reset(mocker):
    """The TTL passed to mset must come from calculate_seconds_until_next_database_population_time."""
    resolved_offer = _make_db_offer("item-1", "offer-1", _PARIS[0], _PARIS[1])
    expected_ttl = 7200

    mock_mset = mocker.patch("core.retrieval.redis_api.mset_resolved_offers", new_callable=mocker.AsyncMock)
    mocker.patch.object(RedisAPI, "calculate_seconds_until_next_database_population_time", return_value=expected_ttl)

    await _store_tops_offer_resolutions_in_cache(["item-1"], [(resolved_offer, 500.0)], h3_cell=_H3_CELL)

    ttl_passed = mock_mset.call_args.args[1]
    assert ttl_passed == expected_ttl


@pytest.mark.asyncio
async def test_store_tops_offer_resolutions_builds_correct_cache_key(mocker):
    """Each stored entry key must follow 'offer_resolution:r{resolution}:{h3_cell}:{item_id}'."""
    resolved_offer = _make_db_offer("item-42", "offer-42", _PARIS[0], _PARIS[1])

    mock_mset = mocker.patch("core.retrieval.redis_api.mset_resolved_offers", new_callable=mocker.AsyncMock)
    mocker.patch.object(RedisAPI, "calculate_seconds_until_next_database_population_time", return_value=3600)

    await _store_tops_offer_resolutions_in_cache(["item-42"], [(resolved_offer, 100.0)], h3_cell=_H3_CELL)

    stored_entries: dict = mock_mset.call_args.args[0]
    expected_key = f"offer_resolution:r{_settings.OFFER_RESOLUTION_CACHE_H3_RESOLUTION}:{_H3_CELL}:item-42"
    assert expected_key in stored_entries


# ===========================================================================
# _resolve_multi_venue_items — offer-resolution cache strategy
# ===========================================================================


@pytest.mark.asyncio
async def test_resolve_multi_venue_items_cache_disabled_skips_cache_and_uses_db(mocker):
    """
    When OFFER_RESOLUTION_CACHE_ENABLED=False, the MGET lookup must be skipped,
    all items must go to the DB, and MSET must never be called.
    """
    patch_all_caches_disabled(mocker)

    tops_item = RecommendableItemFactory.build(
        item_id="item-tops", is_geolocated=True, total_offers=3, item_origin=ItemOrigin.TOPS
    )
    item_lookup_map = {"item-tops": tops_item}
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])

    mock_mget = mocker.patch("core.retrieval.redis_api.mget_resolved_offers", new_callable=mocker.AsyncMock)
    mock_mset = mocker.patch("core.retrieval.redis_api.mset_resolved_offers", new_callable=mocker.AsyncMock)
    db_offer = _make_db_offer("item-tops", "offer-from-db", _PARIS[0], _PARIS[1])
    mocker.patch(
        "core.retrieval.find_closest_offers_with_h3_index",
        new_callable=mocker.AsyncMock,
        return_value=[(db_offer, 500.0)],
    )

    result = await _resolve_multi_venue_items(mocker.MagicMock(), ["item-tops"], item_lookup_map, user)

    mock_mget.assert_not_called()
    mock_mset.assert_not_called()
    assert len(result) == 1
    assert result[0].offer_id == "offer-from-db"


@pytest.mark.asyncio
async def test_resolve_multi_venue_items_cache_enabled_but_no_tops_items_skips_mget(mocker):
    """
    When cache is enabled but there are no tops items, the MGET round-trip must be
    skipped entirely — only non-tops items go through the DB.
    """
    patch_all_caches_enabled(mocker)

    reco_item = RecommendableItemFactory.build(
        item_id="item-reco", is_geolocated=True, total_offers=3, item_origin=ItemOrigin.USER_BASED
    )
    item_lookup_map = {"item-reco": reco_item}
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])

    mock_mget = mocker.patch("core.retrieval.redis_api.mget_resolved_offers", new_callable=mocker.AsyncMock)
    mock_mset = mocker.patch("core.retrieval.redis_api.mset_resolved_offers", new_callable=mocker.AsyncMock)
    db_offer = _make_db_offer("item-reco", "offer-reco-db", _PARIS[0], _PARIS[1])
    mocker.patch(
        "core.retrieval.find_closest_offers_with_h3_index",
        new_callable=mocker.AsyncMock,
        return_value=[(db_offer, 500.0)],
    )

    result = await _resolve_multi_venue_items(mocker.MagicMock(), ["item-reco"], item_lookup_map, user)

    mock_mget.assert_not_called()
    mock_mset.assert_not_called()
    assert len(result) == 1


@pytest.mark.asyncio
async def test_resolve_multi_venue_items_all_tops_cache_hits_skip_db_query(mocker):
    """
    When all tops items are served from cache, the spatial SQL query must not be triggered
    and MSET must not be called (nothing new to store).
    """
    patch_all_caches_enabled(mocker)

    tops_item = RecommendableItemFactory.build(
        item_id="item-tops", is_geolocated=True, total_offers=3, item_origin=ItemOrigin.TOPS
    )
    item_lookup_map = {"item-tops": tops_item}
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])

    mocker.patch("core.retrieval.get_h3_index_from_coordinates", return_value=_H3_CELL)
    mocker.patch(
        "core.retrieval.redis_api.mget_resolved_offers",
        new_callable=mocker.AsyncMock,
        return_value=[_cached_offer_payload("offer-cached", _PARIS[0], _PARIS[1])],
    )
    mock_db_query = mocker.patch(
        "core.retrieval.find_closest_offers_with_h3_index",
        new_callable=mocker.AsyncMock,
    )
    mock_mset = mocker.patch("core.retrieval.redis_api.mset_resolved_offers", new_callable=mocker.AsyncMock)

    result = await _resolve_multi_venue_items(mocker.MagicMock(), ["item-tops"], item_lookup_map, user)

    mock_db_query.assert_not_called()
    mock_mset.assert_not_called()
    assert len(result) == 1
    assert result[0].offer_id == "offer-cached"


@pytest.mark.asyncio
async def test_resolve_multi_venue_items_all_tops_cache_misses_resolved_via_db_and_stored(mocker):
    """
    When all tops items miss the cache:
    - The spatial DB query is called for those items.
    - Resolved items are written to cache via MSET.
    """
    patch_all_caches_enabled(mocker)

    tops_item = RecommendableItemFactory.build(
        item_id="item-tops", is_geolocated=True, total_offers=3, item_origin=ItemOrigin.TOPS
    )
    item_lookup_map = {"item-tops": tops_item}
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])

    mocker.patch("core.retrieval.get_h3_index_from_coordinates", return_value=_H3_CELL)
    mocker.patch(
        "core.retrieval.redis_api.mget_resolved_offers",
        new_callable=mocker.AsyncMock,
        return_value=[None],  # cache miss
    )
    db_offer = _make_db_offer("item-tops", "offer-from-db", _PARIS[0], _PARIS[1])
    mocker.patch(
        "core.retrieval.find_closest_offers_with_h3_index",
        new_callable=mocker.AsyncMock,
        return_value=[(db_offer, 500.0)],
    )
    mock_mset = mocker.patch("core.retrieval.redis_api.mset_resolved_offers", new_callable=mocker.AsyncMock)
    mocker.patch.object(RedisAPI, "calculate_seconds_until_next_database_population_time", return_value=3600)

    result = await _resolve_multi_venue_items(mocker.MagicMock(), ["item-tops"], item_lookup_map, user)

    mock_mset.assert_called_once()
    assert len(result) == 1
    assert result[0].offer_id == "offer-from-db"


@pytest.mark.asyncio
async def test_resolve_multi_venue_items_partial_tops_hits_only_misses_sent_to_db(mocker):
    """
    With a partial cache hit:
    - Cache-hit items must be built from the cache payload (DB query not called for them).
    - Cache-miss items must be sent to the DB.
    - Only the cache-miss item that was resolved gets stored via MSET.
    """
    patch_all_caches_enabled(mocker)

    tops_hit = RecommendableItemFactory.build(
        item_id="item-hit", is_geolocated=True, total_offers=3, item_origin=ItemOrigin.TOPS
    )
    tops_miss = RecommendableItemFactory.build(
        item_id="item-miss", is_geolocated=True, total_offers=3, item_origin=ItemOrigin.TOPS
    )
    item_lookup_map = {"item-hit": tops_hit, "item-miss": tops_miss}
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])

    mocker.patch("core.retrieval.get_h3_index_from_coordinates", return_value=_H3_CELL)
    mocker.patch(
        "core.retrieval.redis_api.mget_resolved_offers",
        new_callable=mocker.AsyncMock,
        return_value=[
            _cached_offer_payload("offer-from-cache", _PARIS[0], _PARIS[1]),  # hit
            None,  # miss
        ],
    )
    db_offer = _make_db_offer("item-miss", "offer-from-db", _PARIS[0], _PARIS[1])
    mock_db_query = mocker.patch(
        "core.retrieval.find_closest_offers_with_h3_index",
        new_callable=mocker.AsyncMock,
        return_value=[(db_offer, 1000.0)],
    )
    mock_mset = mocker.patch("core.retrieval.redis_api.mset_resolved_offers", new_callable=mocker.AsyncMock)
    mocker.patch.object(RedisAPI, "calculate_seconds_until_next_database_population_time", return_value=3600)

    result = await _resolve_multi_venue_items(mocker.MagicMock(), ["item-hit", "item-miss"], item_lookup_map, user)

    # DB query must have been called only with the cache-miss item
    db_item_ids_passed = mock_db_query.call_args.args[1]
    assert "item-miss" in db_item_ids_passed
    assert "item-hit" not in db_item_ids_passed

    # Both offers must appear in the result
    result_offer_ids = {r.offer_id for r in result}
    assert "offer-from-cache" in result_offer_ids
    assert "offer-from-db" in result_offer_ids

    # MSET called once (for the cache miss that was resolved)
    mock_mset.assert_called_once()


@pytest.mark.asyncio
async def test_resolve_multi_venue_items_cache_hit_beyond_max_distance_is_excluded(mocker):
    """
    A cache hit whose stored venue exceeds MAX_DISTANCE_METERS_FOR_OFFER_RETRIEVAL (50 km)
    must be excluded from the result — the guard prevents stale cross-zone entries from
    being served to users near a zone boundary.
    """
    patch_all_caches_enabled(mocker)

    tops_item = RecommendableItemFactory.build(
        item_id="item-far", is_geolocated=True, total_offers=3, item_origin=ItemOrigin.TOPS
    )
    item_lookup_map = {"item-far": tops_item}
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])

    mocker.patch("core.retrieval.get_h3_index_from_coordinates", return_value=_H3_CELL)
    # London is ~343 km from Paris — well beyond the 50 km search radius
    mocker.patch(
        "core.retrieval.redis_api.mget_resolved_offers",
        new_callable=mocker.AsyncMock,
        return_value=[_cached_offer_payload("offer-london", _LONDON[0], _LONDON[1])],
    )
    mocker.patch(
        "core.retrieval.find_closest_offers_with_h3_index",
        new_callable=mocker.AsyncMock,
        return_value=[],
    )
    mocker.patch("core.retrieval.redis_api.mset_resolved_offers", new_callable=mocker.AsyncMock)

    result = await _resolve_multi_venue_items(mocker.MagicMock(), ["item-far"], item_lookup_map, user)

    assert result == []


@pytest.mark.asyncio
async def test_resolve_multi_venue_items_non_tops_items_always_go_to_db_when_cache_enabled(mocker):
    """
    Non-tops items (USER_BASED, GRAPH) are never eligible for caching.
    Even when OFFER_RESOLUTION_CACHE_ENABLED=True, they must bypass the MGET lookup
    and go directly to the DB.  MSET must not be called (no tops misses).
    """
    patch_all_caches_enabled(mocker)

    user_based_item = RecommendableItemFactory.build(
        item_id="item-user-based", is_geolocated=True, total_offers=3, item_origin=ItemOrigin.USER_BASED
    )
    item_lookup_map = {"item-user-based": user_based_item}
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])

    mock_mget = mocker.patch("core.retrieval.redis_api.mget_resolved_offers", new_callable=mocker.AsyncMock)
    mock_db_query = mocker.patch(
        "core.retrieval.find_closest_offers_with_h3_index",
        new_callable=mocker.AsyncMock,
        return_value=[],
    )
    mock_mset = mocker.patch("core.retrieval.redis_api.mset_resolved_offers", new_callable=mocker.AsyncMock)

    await _resolve_multi_venue_items(mocker.MagicMock(), ["item-user-based"], item_lookup_map, user)

    mock_mget.assert_not_called()
    mock_db_query.assert_called_once()
    mock_mset.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_multi_venue_items_mixed_tops_and_non_tops_correct_routing(mocker):
    """
    Mixed scenario (tops + non-tops in the same call):
    - Tops item served from cache → not in DB call.
    - Non-tops item goes to DB → not in MGET call.
    - Both contribute to the final resolved offers list.
    - MSET not called (no tops cache misses).
    """
    patch_all_caches_enabled(mocker)

    tops_item = RecommendableItemFactory.build(
        item_id="item-tops", is_geolocated=True, total_offers=3, item_origin=ItemOrigin.TOPS
    )
    reco_item = RecommendableItemFactory.build(
        item_id="item-reco", is_geolocated=True, total_offers=5, item_origin=ItemOrigin.USER_BASED
    )
    item_lookup_map = {"item-tops": tops_item, "item-reco": reco_item}
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])

    mocker.patch("core.retrieval.get_h3_index_from_coordinates", return_value=_H3_CELL)
    mocker.patch(
        "core.retrieval.redis_api.mget_resolved_offers",
        new_callable=mocker.AsyncMock,
        return_value=[_cached_offer_payload("offer-tops-cached", _PARIS[0], _PARIS[1])],
    )
    db_offer = _make_db_offer("item-reco", "offer-reco-db", _PARIS[0], _PARIS[1])
    mock_db_query = mocker.patch(
        "core.retrieval.find_closest_offers_with_h3_index",
        new_callable=mocker.AsyncMock,
        return_value=[(db_offer, 2000.0)],
    )
    mock_mset = mocker.patch("core.retrieval.redis_api.mset_resolved_offers", new_callable=mocker.AsyncMock)

    result = await _resolve_multi_venue_items(mocker.MagicMock(), ["item-tops", "item-reco"], item_lookup_map, user)

    # DB must have been called only with the non-tops item
    db_item_ids_passed = mock_db_query.call_args.args[1]
    assert "item-reco" in db_item_ids_passed
    assert "item-tops" not in db_item_ids_passed

    # Both offers in result
    result_offer_ids = {r.offer_id for r in result}
    assert "offer-tops-cached" in result_offer_ids
    assert "offer-reco-db" in result_offer_ids

    # No tops cache misses → no MSET
    mock_mset.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_multi_venue_items_deserializes_iso_dates_from_cache_payload(mocker):
    """
    Dates stored in the Redis cache as ISO 8601 strings must be correctly
    deserialized into datetime objects on the resulting EnrichedRecommendableOffer.
    """
    patch_all_caches_enabled(mocker)

    tops_item = RecommendableItemFactory.build(
        item_id="item-tops", is_geolocated=True, total_offers=3, item_origin=ItemOrigin.TOPS
    )
    item_lookup_map = {"item-tops": tops_item}
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])

    creation_dt = datetime(2024, 3, 15, 10, 30, tzinfo=UTC)
    stock_dt = datetime(2024, 5, 20, tzinfo=UTC)

    mocker.patch("core.retrieval.get_h3_index_from_coordinates", return_value=_H3_CELL)
    mocker.patch(
        "core.retrieval.redis_api.mget_resolved_offers",
        new_callable=mocker.AsyncMock,
        return_value=[
            _cached_offer_payload(
                "offer-dated",
                _PARIS[0],
                _PARIS[1],
                creation_date=creation_dt.isoformat(),
                stock_date=stock_dt.isoformat(),
            )
        ],
    )
    mocker.patch(
        "core.retrieval.find_closest_offers_with_h3_index",
        new_callable=mocker.AsyncMock,
        return_value=[],
    )
    mocker.patch("core.retrieval.redis_api.mset_resolved_offers", new_callable=mocker.AsyncMock)

    result = await _resolve_multi_venue_items(mocker.MagicMock(), ["item-tops"], item_lookup_map, user)

    assert len(result) == 1
    assert result[0].offer_creation_date == creation_dt
    assert result[0].stock_beginning_date == stock_dt


@pytest.mark.asyncio
async def test_resolve_multi_venue_items_no_mset_when_db_returns_nothing_for_tops_misses(mocker):
    """
    When the DB resolves no rows for tops cache-miss items (e.g. no venue within radius),
    MSET must not be called — absence of an offer must not be cached.
    """
    patch_all_caches_enabled(mocker)

    tops_item = RecommendableItemFactory.build(
        item_id="item-tops", is_geolocated=True, total_offers=3, item_origin=ItemOrigin.TOPS
    )
    item_lookup_map = {"item-tops": tops_item}
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])

    mocker.patch("core.retrieval.get_h3_index_from_coordinates", return_value=_H3_CELL)
    mocker.patch(
        "core.retrieval.redis_api.mget_resolved_offers",
        new_callable=mocker.AsyncMock,
        return_value=[None],  # miss
    )
    mocker.patch(
        "core.retrieval.find_closest_offers_with_h3_index",
        new_callable=mocker.AsyncMock,
        return_value=[],  # DB resolves nothing
    )
    mock_mset = mocker.patch("core.retrieval.redis_api.mset_resolved_offers", new_callable=mocker.AsyncMock)

    result = await _resolve_multi_venue_items(mocker.MagicMock(), ["item-tops"], item_lookup_map, user)

    mock_mset.assert_not_called()
    assert result == []


_PARIS_VERSAILLES_MAX_DISTANCE_METERS = 30_000  # Paris ↔ Versailles ≈ 17 km, well within this bound


@pytest.mark.asyncio
async def test_resolve_multi_venue_items_cache_hit_blends_cache_and_vertex_data(mocker):
    """
    An EnrichedRecommendableOffer built from a cache hit must correctly blend:
    - offer_id, venue coordinates (from the cached payload)
    - item_score, item_rank, category, booking_number, etc. (from the Vertex item data)
    - offer_user_distance computed via Haversine from the cached venue coordinates
    """
    patch_all_caches_enabled(mocker)

    tops_item = RecommendableItemFactory.build(
        item_id="item-tops",
        is_geolocated=True,
        total_offers=3,
        item_origin=ItemOrigin.TOPS,
    )
    item_lookup_map = {"item-tops": tops_item}
    user = UserContext(user_id="u", latitude=_PARIS[0], longitude=_PARIS[1])

    mocker.patch("core.retrieval.get_h3_index_from_coordinates", return_value=_H3_CELL)
    mocker.patch(
        "core.retrieval.redis_api.mget_resolved_offers",
        new_callable=mocker.AsyncMock,
        return_value=[_cached_offer_payload("offer-versailles", _VERSAILLES[0], _VERSAILLES[1])],
    )
    mocker.patch(
        "core.retrieval.find_closest_offers_with_h3_index",
        new_callable=mocker.AsyncMock,
        return_value=[],
    )
    mocker.patch("core.retrieval.redis_api.mset_resolved_offers", new_callable=mocker.AsyncMock)

    result = await _resolve_multi_venue_items(mocker.MagicMock(), ["item-tops"], item_lookup_map, user)

    assert len(result) == 1
    offer = result[0]

    # DB-side fields come from the cache payload
    assert offer.offer_id == "offer-versailles"
    assert offer.item_id == "item-tops"
    assert offer.venue_latitude == _VERSAILLES[0]
    assert offer.venue_longitude == _VERSAILLES[1]

    # Vertex-side fields come from item_lookup_map
    assert offer.item_score == tops_item.item_score
    assert offer.item_rank == tops_item.item_rank
    assert offer.category == tops_item.category
    assert offer.booking_number == tops_item.booking_number

    # Distance recomputed via Haversine (Paris ↔ Versailles ≈ 17 km)
    assert offer.offer_user_distance is not None
    assert offer.offer_user_distance < _PARIS_VERSAILLES_MAX_DISTANCE_METERS
