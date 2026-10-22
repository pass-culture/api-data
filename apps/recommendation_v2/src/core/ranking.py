from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from connectors import ranking_api_client
from core.user_context import UserContext
from schemas.enriched_offer import EnrichedRecommendableOffer
from schemas.vertex_prediction_item import RecommendableItem
from services.logger import logger


if TYPE_CHECKING:
    from connectors.vertex_api import RankingResult


DEFAULT_K = 60  # Standard RRF smoothing constant (see Cormack et al., 2009).
DEFAULT_WEIGHT = 1.0


def calculate_days_since(target_date: datetime | None) -> float | None:
    """
    Calculates the number of full days elapsed between a given date and now.

    Handles timezone-aware and naive datetimes gracefully.

    Args:
        target_date (datetime | None): The date to compare against current time.

    Returns:
        float | None: The number of days elapsed, or None if the input date is missing.
    """
    if target_date is None:
        return None

    now_utc = datetime.now(UTC)

    current_time = now_utc if target_date.tzinfo is not None else now_utc.replace(tzinfo=None)

    time_delta = current_time - target_date
    return float(time_delta.days)


def _build_vertex_ranking_features(
    offer: EnrichedRecommendableOffer,
    user_context: UserContext,
    context_name: str = "recommendation",
) -> dict[str, Any]:
    """
    Constructs the feature vector required by the Vertex AI Ranking model.

    This maps our internal database/context models to the exact schema expected
    by the ML ranking endpoint (ISO V1 format).

    Args:
        offer (EnrichedRecommendableOffer): The resolved offer to be scored.
        user_context (UserContext): The user's profile and behavioral data.
        context_name (str): The origin context of the recommendation.

    Returns:
        dict[str, Any]: A flat dictionary of features ready for Vertex AI prediction.
    """

    # TODO: Investigate if all these features strictly require casting to float,
    #  as it might mask underlying type issues or add unnecessary overhead.

    # TODO: Create a dedicated Pydantic model for this feature vector payload
    #  to ensure strict validation, type safety, and automatic serialization.

    return {
        # --- Identifiers & Context ---
        "offer_id": str(offer.offer_id),
        "context": f"{context_name}:{offer.item_origin}",
        # --- User Behavioral Features ---
        "user_bookings_count": float(user_context.bookings_count),
        "user_clicks_count": float(user_context.clicks_count),
        "user_favorites_count": float(user_context.favorites_count),
        "user_deposit_remaining_credit": float(user_context.remaining_credit),
        # --- User Geographical Features ---
        "user_is_geolocated": float(user_context.is_geolocated),
        "user_iris_x": float(user_context.longitude) if user_context.longitude else None,
        "user_iris_y": float(user_context.latitude) if user_context.latitude else None,
        "offer_user_distance": offer.offer_user_distance,
        # --- Offer Static Features ---
        "offer_subcategory_id": offer.subcategory_id,
        "offer_stock_price": float(offer.stock_price or 0.0),
        "offer_semantic_emb_mean": float(offer.semantic_emb_mean or 0.0),
        "offer_is_geolocated": 1.0 if offer.is_geolocated else 0.0,
        # --- Offer Temporal Features ---
        "offer_creation_days": calculate_days_since(offer.offer_creation_date),
        "offer_stock_beginning_days": calculate_days_since(offer.stock_beginning_date),
        # --- Offer Popularity/Score Features ---
        "offer_booking_number": float(offer.booking_number),
        "offer_booking_number_last_7_days": float(offer.booking_number_last_7_days),
        "offer_booking_number_last_14_days": float(offer.booking_number_last_14_days),
        "offer_booking_number_last_28_days": float(offer.booking_number_last_28_days),
        "offer_item_score": float(offer.item_score or 0.0),
        "offer_item_rank": float(offer.item_rank),
        # --- Real-Time Contextual Features ---
        "day_of_the_week": datetime.now(UTC).weekday(),
        "hour_of_the_day": datetime.now(UTC).hour,
    }


async def rank_and_sort_offers_with_vertex(
    offers: list[EnrichedRecommendableOffer], user_context: UserContext
) -> list[EnrichedRecommendableOffer]:
    """
    Scores a list of candidate offers using the Vertex AI Ranking model and sorts them.

    If the ML model fails or returns empty predictions, it falls back to a deterministic
    sorting based on the baseline 'item_rank' provided during the retrieval phase.

    Args:
        offers (list[EnrichedRecommendableOffer]): The filtered list of offers to be ranked.
        user_context (UserContext): The current user's profile and state.

    Returns:
        list[EnrichedRecommendableOffer]: The same offers, mutually sorted by their predicted ranking score (descending)
    """
    if not offers:
        return []

    # --- 1. Prepare Features & Call Model ---
    ranking_instances = [_build_vertex_ranking_features(offer, user_context) for offer in offers]

    logger.debug(
        "📤 Sending offers to Vertex AI ranking model.",
        extra={"offers_to_rank": len(ranking_instances), "user_id": user_context.user_id},
    )

    ranking_result: RankingResult = await ranking_api_client.fetch_ranking_predictions(
        feature_payloads=ranking_instances
    )
    predictions = ranking_result.predictions

    # --- 2. Fallback Mechanism ---
    # If Vertex prediction fails or returns nothing, fallback to the retrieval 'item_rank'
    if not predictions:
        logger.warning(
            "⚠️ Vertex ranking returned no predictions — falling back to item_rank ordering.",
            extra={"offers_count": len(offers), "user_id": user_context.user_id},
        )
        # Attach model provenance even in fallback case (ranking_score stays 0.0)
        for offer in offers:
            offer.ranking_model_name = ranking_result.model_name
            offer.ranking_model_version = ranking_result.model_version
        return sorted(offers, key=lambda o: o.item_rank if o.item_rank is not None else float("inf"))

    # --- 3. Map Scores & Sort ---
    prediction_score_map: dict[str, float] = {prediction.offer_id: prediction.score for prediction in predictions}

    for offer in offers:
        # Attach the dynamic score and ranking model provenance to the offer object
        offer.ranking_score = prediction_score_map.get(str(offer.offer_id), 0.0)
        offer.ranking_model_name = ranking_result.model_name
        offer.ranking_model_version = ranking_result.model_version

    logger.debug(
        "✅ Ranking scores applied to offers.",
        extra={
            "ranked_count": len(predictions),
            "unmatched_count": len(offers) - len(predictions),
            "user_id": user_context.user_id,
            "ranking_model_name": ranking_result.model_name,
            "ranking_model_version": ranking_result.model_version,
        },
    )

    # Sort descending based on the predicted score attached to the object (highest score first)
    return sorted(offers, key=lambda offer: offer.ranking_score, reverse=True)


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
