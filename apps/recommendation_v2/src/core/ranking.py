from datetime import UTC
from datetime import datetime
from typing import Any

from config import settings
from core.user_context import UserContext
from schemas.enriched_offer import EnrichedRecommendableOffer
from services.vertex import RankingPrediction
from services.vertex import VertexService


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
    vertex_service = VertexService(endpoint_name=settings.VERTEX_RANKING_ENDPOINT_NAME)
    ranking_instances = [_build_vertex_ranking_features(offer, user_context) for offer in offers]

    predictions: list[RankingPrediction] = await vertex_service.fetch_ranking_predictions(
        feature_payloads=ranking_instances
    )

    # --- 2. Fallback Mechanism ---
    # If Vertex prediction fails or returns nothing, fallback to the retrieval 'item_rank'
    if not predictions:
        return sorted(offers, key=lambda o: o.item_rank if o.item_rank is not None else float("inf"))

    # --- 3. Map Scores & Sort ---
    prediction_score_map: dict[str, float] = {prediction.offer_id: prediction.score for prediction in predictions}

    for offer in offers:
        # Attach the dynamic score to the offer object for downstream logging (default to 0.0)
        offer.ranking_score = prediction_score_map.get(str(offer.offer_id), 0.0)

    # Sort descending based on the predicted score attached to the object (highest score first)
    return sorted(offers, key=lambda offer: offer.ranking_score, reverse=True)
