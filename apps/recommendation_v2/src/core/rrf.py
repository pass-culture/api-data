"""
Reciprocal Rank Fusion (RRF) for merging two ranked retrieval lists.

Generic, dependency-free logic — no Vertex AI, HTTP, or DB dependency — so it is
unit-testable in isolation. Defaults to classic unweighted RRF (k=60, semantic_weight=1.5, recommendation_weight=1.0),
letting callers compare the two signals and give a relative importance to semantic over collaborative signals
to reduce importance of top-booked items from dominating the fused list.
"""

from schemas.vertex_prediction_item import RecommendableItem


DEFAULT_K = 60  # Standard RRF smoothing constant (see Cormack et al., 2009).
DEFAULT_WEIGHT = 1.0


def reciprocal_rank_fusion(
    semantic_items: list[RecommendableItem],
    recommendation_items: list[RecommendableItem],
    k: int = DEFAULT_K,
    semantic_weight: float = DEFAULT_WEIGHT,
    recommendation_weight: float = DEFAULT_WEIGHT,
) -> list[RecommendableItem]:
    """
    Fuses two ranked candidate lists into a single ranked, deduplicated list using
    (weighted) Reciprocal Rank Fusion.

    For each item, RRF sums weight / (k + rank) across every source list it appears in (rank is
    1-indexed per list; a source an item is absent from contributes 0). Items are then sorted by
    descending fused score. This naturally rewards items that rank highly in both sources, without
    requiring the raw retrieval scores of each source to be comparable (they generally aren't,
    since they come from different models).

    Args:
        semantic_items (list[RecommendableItem]): Ranked, best-first predictions from the
            semantic (content-based) retrieval source.
        recommendation_items (list[RecommendableItem]): Ranked, best-first predictions from the
            recommendation (collaborative-filtering) retrieval source.
        k (int): RRF smoothing constant. Higher values flatten the influence of top ranks
            relative to lower ones. Defaults to the standard value of 60.
        semantic_weight (float): Weight applied to the semantic list's contribution.
        recommendation_weight (float): Weight applied to the recommendation list's contribution.

    Returns:
        list[RecommendableItem]: A deduplicated list of items ordered by descending fused score,
            with `item_rank`/`item_score` overwritten to reflect the fused rank (1-indexed) and score.

    Example (equal weights, k=60):
        semantic_items:       [Item("X"), Item("Y")]   (X rank 1, Y rank 2)
        recommendation_items: [Item("Y"), Item("Z")]   (Y rank 1, Z rank 2)
        RRF scores: X = 1/61, Y = 1/62 + 1/61, Z = 1/62
        Output order: Y, X, Z
    """
    fused_scores: dict[str, float] = {}
    item_by_id: dict[str, RecommendableItem] = {}

    for rank, item in enumerate(semantic_items, start=1):
        fused_scores[item.item_id] = fused_scores.get(item.item_id, 0.0) + semantic_weight / (k + rank)
        item_by_id.setdefault(item.item_id, item)

    for rank, item in enumerate(recommendation_items, start=1):
        fused_scores[item.item_id] = fused_scores.get(item.item_id, 0.0) + recommendation_weight / (k + rank)
        # If the item was already seen in semantic_items, keep that instance (arbitrary but
        # deterministic provenance); otherwise this is the first time we see it.
        item_by_id.setdefault(item.item_id, item)

    fused_item_ids = sorted(fused_scores, key=lambda item_id: fused_scores[item_id], reverse=True)

    fused_items: list[RecommendableItem] = []
    for fused_rank, item_id in enumerate(fused_item_ids, start=1):
        item = item_by_id[item_id]
        item.item_rank = fused_rank
        item.item_score = fused_scores[item_id]
        fused_items.append(item)

    return fused_items
