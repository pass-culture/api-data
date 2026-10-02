from datetime import UTC
from datetime import datetime

import pytest

from connectors.vertex_api import RankingPrediction
from connectors.vertex_api import RankingResult
from core.ranking import _build_vertex_ranking_features
from core.ranking import calculate_days_since
from core.ranking import rank_and_sort_offers_with_vertex
from core.ranking import reciprocal_rank_fusion
from core.user_context import UserContext

from tests.factories.schemas import EnrichedRecommendableOfferFactory
from tests.factories.schemas import RecommendableItemFactory
from tests.factories.schemas import UserContextFactory


# ---------------------------------------------------------------------------
# calculate_days_since
# ---------------------------------------------------------------------------


def test_calculate_days_since_returns_none_for_none_input():
    assert calculate_days_since(None) is None


def test_calculate_days_since_returns_correct_days_for_timezone_aware_date():
    """Timezone-aware dates are compared against UTC now; the elapsed day count must be exact."""
    past = datetime(2020, 1, 1, tzinfo=UTC)
    result = calculate_days_since(past)
    expected = (datetime.now(UTC) - past).days
    assert result == float(expected)


def test_calculate_days_since_handles_timezone_naive_date():
    """Naive datetimes strip the timezone from now to avoid TypeError on subtraction."""
    # no tzinfo
    past = datetime(2020, 1, 1)  # noqa: DTZ001
    result = calculate_days_since(past)
    now_naive = datetime.now(UTC).replace(tzinfo=None)
    expected = (now_naive - past).days
    assert result == float(expected)


# ---------------------------------------------------------------------------
# _build_vertex_ranking_features
# ---------------------------------------------------------------------------


def test_build_ranking_features_maps_offer_is_geolocated_to_float():
    """The ML model expects 1.0/0.0, not Python booleans."""
    offer_geo = EnrichedRecommendableOfferFactory.build(is_geolocated=True)
    offer_non_geo = EnrichedRecommendableOfferFactory.build(is_geolocated=False)
    user = UserContextFactory.build()

    assert _build_vertex_ranking_features(offer_geo, user)["offer_is_geolocated"] == 1.0
    assert _build_vertex_ranking_features(offer_non_geo, user)["offer_is_geolocated"] == 0.0


def test_build_ranking_features_returns_none_for_user_iris_when_coordinates_absent():
    user = UserContext(user_id="u", latitude=None, longitude=None)
    features = _build_vertex_ranking_features(EnrichedRecommendableOfferFactory.build(), user)
    assert features["user_iris_x"] is None
    assert features["user_iris_y"] is None


def test_build_ranking_features_returns_none_for_zero_coordinates():
    """Truthiness check means longitude=0.0 (Greenwich) and latitude=0.0 (equator) are both treated as absent."""

    user = UserContext(user_id="u", latitude=0.0, longitude=0.0)
    features = _build_vertex_ranking_features(EnrichedRecommendableOfferFactory.build(), user)
    assert features["user_iris_x"] is None
    assert features["user_iris_y"] is None


def test_build_ranking_features_context_field_combines_context_name_and_item_origin():
    offer = EnrichedRecommendableOfferFactory.build(item_origin="user_based")
    features = _build_vertex_ranking_features(offer, UserContextFactory.build(), context_name="similar_offer")
    assert features["context"] == "similar_offer:user_based"


# ---------------------------------------------------------------------------
# rank_and_sort_offers_with_vertex
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rank_returns_empty_for_empty_input(mocker):
    mocker.patch(
        "core.ranking.ranking_api_client.fetch_ranking_predictions",
        new_callable=mocker.AsyncMock,
        return_value=RankingResult(predictions=[], model_name="test-endpoint"),
    )
    result = await rank_and_sort_offers_with_vertex([], UserContextFactory.build())
    assert result == []


@pytest.mark.asyncio
async def test_rank_falls_back_to_item_rank_when_predictions_empty(mocker):
    """When Vertex returns nothing, offers are sorted ascending by item_rank so retrieval order is preserved."""
    mocker.patch(
        "core.ranking.ranking_api_client.fetch_ranking_predictions",
        new_callable=mocker.AsyncMock,
        return_value=RankingResult(predictions=[], model_name="test-endpoint"),
    )

    offers = [
        EnrichedRecommendableOfferFactory.build(item_rank=3),
        EnrichedRecommendableOfferFactory.build(item_rank=1),
        EnrichedRecommendableOfferFactory.build(item_rank=2),
    ]

    result = await rank_and_sort_offers_with_vertex(offers, UserContextFactory.build())

    assert [o.item_rank for o in result] == [1, 2, 3]


@pytest.mark.asyncio
async def test_rank_sorts_offers_descending_by_prediction_score(mocker):
    offers = [
        EnrichedRecommendableOfferFactory.build(offer_id="offer-a"),
        EnrichedRecommendableOfferFactory.build(offer_id="offer-b"),
        EnrichedRecommendableOfferFactory.build(offer_id="offer-c"),
    ]
    predictions = [
        RankingPrediction(offer_id="offer-a", score=0.3),
        RankingPrediction(offer_id="offer-b", score=0.9),
        RankingPrediction(offer_id="offer-c", score=0.6),
    ]
    mocker.patch(
        "core.ranking.ranking_api_client.fetch_ranking_predictions",
        new_callable=mocker.AsyncMock,
        return_value=RankingResult(predictions=predictions, model_name="test-endpoint"),
    )

    result = await rank_and_sort_offers_with_vertex(offers, UserContextFactory.build())

    assert [o.offer_id for o in result] == ["offer-b", "offer-c", "offer-a"]


@pytest.mark.asyncio
async def test_rank_assigns_zero_score_to_offer_absent_from_predictions(mocker):
    """An offer not returned by Vertex gets ranking_score=0.0 and sinks to the bottom."""

    scored_offer = EnrichedRecommendableOfferFactory.build(offer_id="offer-scored")
    unscored_offer = EnrichedRecommendableOfferFactory.build(offer_id="offer-unscored")
    predictions = [RankingPrediction(offer_id="offer-scored", score=0.8)]
    mocker.patch(
        "core.ranking.ranking_api_client.fetch_ranking_predictions",
        new_callable=mocker.AsyncMock,
        return_value=RankingResult(predictions=predictions, model_name="test-endpoint"),
    )

    result = await rank_and_sort_offers_with_vertex([scored_offer, unscored_offer], UserContextFactory.build())

    assert result[0].offer_id == "offer-scored"
    assert result[-1].offer_id == "offer-unscored"
    assert result[-1].ranking_score == 0.0


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
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

    result = reciprocal_rank_fusion(
        semantic_items=[item_x, item_y_semantic], recommendation_items=[item_y_recommendation, item_z], k=60
    )

    assert [item.item_id for item in result] == ["Y", "X", "Z"]


def test_rrf_merge_deduplicates_by_item_id():
    item_a_semantic = RecommendableItemFactory.build(item_id="A")
    item_a_recommendation = RecommendableItemFactory.build(item_id="A")

    result = reciprocal_rank_fusion(semantic_items=[item_a_semantic], recommendation_items=[item_a_recommendation])

    assert len(result) == 1
    assert result[0].item_id == "A"


def test_rrf_merge_overwrites_item_rank_with_fused_rank():
    item_x = RecommendableItemFactory.build(item_id="X", item_rank=999)
    item_y = RecommendableItemFactory.build(item_id="Y", item_rank=999)

    result = reciprocal_rank_fusion(semantic_items=[item_x, item_y], recommendation_items=[])

    assert [item.item_rank for item in result] == [1, 2]


def test_rrf_merge_empty_lists_returns_empty():
    assert reciprocal_rank_fusion(semantic_items=[], recommendation_items=[]) == []


def test_rrf_merge_respects_custom_weights():
    """A source weighted to 0 must not influence the fused order at all."""
    item_x = RecommendableItemFactory.build(item_id="X")  # rank 1 in semantic (weighted out)
    item_y = RecommendableItemFactory.build(item_id="Y")  # rank 1 in recommendation

    result = reciprocal_rank_fusion(
        semantic_items=[item_x], recommendation_items=[item_y], semantic_weight=0.0, recommendation_weight=1.0
    )

    assert result[0].item_id == "Y"
    assert result[1].item_score == 0.0
