from datetime import UTC
from datetime import datetime

from core.user_context import UserContext
from schemas.enriched_offer import EnrichedRecommendableOffer
from schemas.playlist_recommendation import PlaylistRequestParams
from services.logger import logger


def log_past_offer_context_to_sink(
    user_context: UserContext,
    final_playlist: list[EnrichedRecommendableOffer],
    params: PlaylistRequestParams,
    call_id: str,
    reco_origin: str,
    context_name: str,
) -> None:
    """
    Formats and logs the full context of the generated recommendation playlist.

    CRITICAL INFRASTRUCTURE WARNING:
    This function does not just output standard application logs. It acts as the
    entry point for our Data Engineering and Machine Learning pipeline.

    Architecture Flow:
    1. This JSON payload is logged to standard output (stdout).
    2. Google Cloud Logging captures it.
    3. A GCP Log Sink matches the 'event_type' label ('NEW_recommendation_past_offer_context_sink').
    4. The payload is automatically routed and ingested into a BigQuery table.
    5. Data Scientists use this historical BigQuery data to compute user engagement
       and train future iterations of the Vertex AI recommendation models.

    Changing the keys or formats in this payload without syncing with the Data team
    will break the BigQuery schema and halt model training.

    Args:
        user_context (UserContext): The current state/profile of the user.
        final_playlist (list[RecommendableOffers]): The ordered list of offers shown to the user.
        params (PlaylistRequestParams): The input filters requested by the client.
        call_id (str): The unique execution trace ID to link multiple logs together.
        reco_origin (str): Indicates if this was a 'cold_start' or an 'algo' recommendation.
        context_name (str): The specific endpoint or UI context calling this function.
    """

    # --- 1. Compute Shared Context ---
    # We compute these values once outside the loop to optimize performance
    current_utc_date = datetime.now(UTC).isoformat()

    request_extra_data = {
        "reco_origin": reco_origin,
        "context": context_name,
        "params_in": params.model_dump(by_alias=True, exclude_none=True),
    }

    # --- 2. Iterate and Log Each Offer ---
    for rank_index, offer in enumerate(final_playlist):
        # TODO: Tech Debt - Create a strict Pydantic model for this specific log payload.
        # This dictionary maps directly to a BigQuery table schema. Using a Pydantic model
        # here would enforce type safety, prevent schema mismatches, and provide self-documenting code.

        log_payload = {
            # --- GCP Sink Routing Label ---
            "labels": {
                "event_type": "NEW_recommendation_past_offer_context_sink",
            },
            # --- Execution Metadata ---
            "call_id": call_id,
            "context": f"{context_name}:{offer.item_origin}",
            "context_extra_data": request_extra_data,
            "date": current_utc_date,
            # --- User Context & Features ---
            "user_id": user_context.user_id,
            "user_bookings_count": user_context.bookings_count,
            "user_clicks_count": user_context.clicks_count,
            "user_favorites_count": user_context.favorites_count,
            "user_deposit_remaining_credit": user_context.remaining_credit,
            "user_iris_id": user_context.iris_id,
            "user_is_geolocated": user_context.is_geolocated,
            "user_latitude": None,
            "user_longitude": None,
            "user_extra_data": {},
            # --- Offer Data & Features ---
            "offer_id": offer.offer_id,
            "offer_item_id": offer.item_id,
            "offer_user_distance": offer.offer_user_distance,
            "offer_is_geolocated": offer.is_geolocated,
            "offer_booking_number": offer.booking_number,
            "offer_stock_price": offer.stock_price,
            "offer_category": offer.category,
            "offer_subcategory_id": offer.subcategory_id,
            "offer_item_rank": offer.item_rank,
            "offer_item_score": offer.item_score,
            "offer_order": rank_index,  # Critical for understanding ranking performance
            "offer_venue_id": None,
            "offer_creation_date": offer.offer_creation_date.isoformat() if offer.offer_creation_date else None,
            "offer_stock_beginning_date": offer.stock_beginning_date.isoformat()
            if offer.stock_beginning_date
            else None,
            # --- Extra Model & Ranking Scores ---
            "offer_extra_data": {
                "offer_ranking_score": getattr(offer, "ranking_score", None),  # ?
                "offer_ranking_origin": "model" if getattr(offer, "ranking_score", None) else "item_rank",
                "offer_booking_number_last_7_days": offer.booking_number_last_7_days,
                "offer_booking_number_last_14_days": offer.booking_number_last_14_days,
                "offer_booking_number_last_28_days": offer.booking_number_last_28_days,
                "offer_semantic_emb_mean": offer.semantic_emb_mean,
            },
        }

        # Send to stdout for the GCP Logging Agent to capture
        logger.info("Past Offer Context", extra_data=log_payload)
