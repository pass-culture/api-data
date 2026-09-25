from core.rrf import reciprocal_rank_fusion

from tests.factories.schemas import RecommendableItemFactory


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
