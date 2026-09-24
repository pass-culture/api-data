from datetime import UTC
from datetime import datetime

import pytest

from core.retrieval import AVAILABLE_MOVIE_SUBCATEGORIES
from core.retrieval import MOVIE_LIKE_CATEGORIES
from core.retrieval import _build_playlist_recommendation_search_filters
from core.retrieval import _build_similar_offer_search_filters
from core.retrieval import build_cinema_recommendation_user_retrieval_payload
from core.retrieval import build_cinema_semantic_item_retrieval_payload
from core.retrieval import build_playlist_recommendation_retrieval_payload
from core.retrieval import build_similar_offer_retrieval_payload
from core.retrieval import fetch_all_playlist_recommendation_retrieval_predictions_from_vertex
from core.retrieval import fetch_cinema_rrf_retrieval_predictions_from_vertex
from core.retrieval import filter_out_already_booked_items
from core.retrieval import merge_candidate_items_with_reciprocal_rank_fusion
from core.user_context import UserContext
from schemas.categories import CategoryEnum
from schemas.categories import SearchGroupNameEnum
from schemas.categories import SubcategoryEnum
from schemas.playlist_recommendation import PlaylistRequestParams

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
# build_cinema_semantic_item_retrieval_payload / build_cinema_recommendation_user_retrieval_payload
# ---------------------------------------------------------------------------


def test_cinema_payloads_use_size_500_and_recommendation_model_type():
    user = UserContextFactory.build(user_id="u", is_authenticated=True)
    semantic_payload = build_cinema_semantic_item_retrieval_payload(user, "call-1", PlaylistRequestParams())
    recommendation_payload = build_cinema_recommendation_user_retrieval_payload(user, "call-1", PlaylistRequestParams())

    for payload in (semantic_payload, recommendation_payload):
        assert payload["size"] == 500
        assert payload["model_type"] == "recommendation"
        assert payload["call_id"] == "call-1"
        assert payload["user_id"] == "u"


def test_cinema_payloads_restrict_filters_to_movie_subcategories_regardless_of_requested_categories():
    """
    Even if the client requested other categories/subcategories, the cinema retrieval payloads must
    only ever filter on MOVIE_LIKE_CATEGORIES / AVAILABLE_MOVIE_SUBCATEGORIES — this narrows the
    broad CINEMA/FILM categories down to actual movie-screening subcategories.
    """
    user = UserContextFactory.build(user_id="u", is_authenticated=True)
    params = PlaylistRequestParams(categories=[CategoryEnum.LIVRE], subcategories=[SubcategoryEnum.ABO_CONCERT])

    payload = build_cinema_semantic_item_retrieval_payload(user, "call-1", params)
    conditions = payload["params"]["$and"]

    assert {"category": {"$in": MOVIE_LIKE_CATEGORIES}} in conditions
    assert {"subcategory_id": {"$in": AVAILABLE_MOVIE_SUBCATEGORIES}} in conditions


def test_cinema_payload_builders_do_not_mutate_caller_params():
    """The original PlaylistRequestParams instance must stay untouched — it is still what's tracked to BigQuery."""
    user = UserContextFactory.build(user_id="u", is_authenticated=True)
    params = PlaylistRequestParams(categories=[CategoryEnum.LIVRE])

    build_cinema_semantic_item_retrieval_payload(user, "call-1", params)

    assert params.categories == [CategoryEnum.LIVRE]


# ---------------------------------------------------------------------------
# merge_candidate_items_with_reciprocal_rank_fusion
# ---------------------------------------------------------------------------


def test_rrf_merge_orders_items_appearing_in_both_lists_first():
    """
    Semantic list:       [X, Y] (X rank 1, Y rank 2)
    Recommendation list: [Y, Z] (Y rank 1, Z rank 2)
    Y appears in both lists and should be fused to the top, ahead of X and Z.
    """
    item_x = RecommendableItemFactory.build(item_id="X")
    item_y_semantic = RecommendableItemFactory.build(item_id="Y")
    item_y_recommendation = RecommendableItemFactory.build(item_id="Y")
    item_z = RecommendableItemFactory.build(item_id="Z")

    result = merge_candidate_items_with_reciprocal_rank_fusion(
        semantic_items=[item_x, item_y_semantic], recommendation_items=[item_y_recommendation, item_z], k=60
    )

    assert [item.item_id for item in result] == ["Y", "X", "Z"]


def test_rrf_merge_deduplicates_by_item_id():
    item_a_semantic = RecommendableItemFactory.build(item_id="A")
    item_a_recommendation = RecommendableItemFactory.build(item_id="A")

    result = merge_candidate_items_with_reciprocal_rank_fusion(
        semantic_items=[item_a_semantic], recommendation_items=[item_a_recommendation]
    )

    assert len(result) == 1
    assert result[0].item_id == "A"


def test_rrf_merge_overwrites_item_rank_with_fused_rank():
    item_x = RecommendableItemFactory.build(item_id="X", item_rank=999)
    item_y = RecommendableItemFactory.build(item_id="Y", item_rank=999)

    result = merge_candidate_items_with_reciprocal_rank_fusion(semantic_items=[item_x, item_y], recommendation_items=[])

    assert [item.item_rank for item in result] == [1, 2]


def test_rrf_merge_empty_lists_returns_empty():
    assert merge_candidate_items_with_reciprocal_rank_fusion(semantic_items=[], recommendation_items=[]) == []


def test_rrf_merge_respects_custom_weights():
    """A source weighted to 0 must not influence the fused order at all."""
    item_x = RecommendableItemFactory.build(item_id="X")  # rank 1 in semantic (weighted out)
    item_y = RecommendableItemFactory.build(item_id="Y")  # rank 1 in recommendation

    result = merge_candidate_items_with_reciprocal_rank_fusion(
        semantic_items=[item_x], recommendation_items=[item_y], semantic_weight=0.0, recommendation_weight=1.0
    )

    assert result[0].item_id == "Y"
    assert result[1].item_score == 0.0


# ---------------------------------------------------------------------------
# fetch_cinema_rrf_retrieval_predictions_from_vertex
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_cinema_rrf_retrieval_calls_both_endpoints_and_fuses_results(mocker):
    item_semantic_only = RecommendableItemFactory.build(item_id="item-semantic-only")
    item_shared = RecommendableItemFactory.build(item_id="item-shared")
    item_recommendation_only = RecommendableItemFactory.build(item_id="item-recommendation-only")

    mocker.patch(
        "core.retrieval.fetch_semantic_item_retrieval_predictions_from_vertex",
        new_callable=mocker.AsyncMock,
        return_value=VertexPredictionResultFactory.build(predictions=[item_semantic_only, item_shared]),
    )
    mocker.patch(
        "core.retrieval.fetch_retrieval_predictions_from_vertex",
        new_callable=mocker.AsyncMock,
        return_value=VertexPredictionResultFactory.build(predictions=[item_shared, item_recommendation_only]),
    )

    user = UserContextFactory.build(user_id="u", is_authenticated=True)
    result = await fetch_cinema_rrf_retrieval_predictions_from_vertex(user, "call-1", PlaylistRequestParams())

    result_item_ids = {item.item_id for item in result}
    assert result_item_ids == {"item-semantic-only", "item-shared", "item-recommendation-only"}
    # The item present in both sources should be fused to the top (rank 1).
    assert result[0].item_id == "item-shared"
