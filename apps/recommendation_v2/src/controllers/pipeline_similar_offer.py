import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.diversification import apply_offer_diversification
from core.geo import get_iris_id_from_coordinates
from core.ranking import rank_and_sort_offers_with_vertex
from core.retrieval import build_similar_offer_retrieval_payload
from core.retrieval import fetch_graph_predictions_from_vertex
from core.retrieval import fetch_retrieval_predictions_from_vertex
from core.retrieval import filter_out_already_booked_items
from core.retrieval import resolve_closest_venues_from_items
from core.tracking import log_past_offer_context_to_sink
from core.user_context import UNAUTHENTICATED_USER_ID
from core.user_context import UserContext
from models.offer import RecommendableOffers
from models.user import EnrichedUser
from schemas.categories import CategoryEnum
from schemas.categories import SearchGroupNameEnum
from schemas.categories import SubcategoryEnum
from schemas.playlist_recommendation import RecommendationMetadata
from schemas.similar_offer import SimilarOfferModelChoices
from schemas.similar_offer import SimilarOfferResponse
from services.logger import call_id_context
from services.logger import logger


SIMILAR_OFFERS_LIST_MAXIMUM_SIZE = 20


async def generate_similar_offers(  # noqa: PLR0913
    db: AsyncSession,
    offer_id: str,
    retrieval_model: SimilarOfferModelChoices = SimilarOfferModelChoices.coreservation,
    user_id: str | None = None,
    categories: list[CategoryEnum] | None = None,
    subcategories: list[SubcategoryEnum] | None = None,
    search_group_names: list[SearchGroupNameEnum] | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> SimilarOfferResponse:
    """
    Orchestrates the pipeline to generate a list of offers similar to a given offer.

    This function is specifically designed for the "similar offers" use case, where the input is a single
    offer ID rather than a user ID. It follows a similar flow to the main recommendation pipeline but is
    optimized for item-to-item similarity rather than personalized user recommendations.

    Pipeline Stages:
    1. Context Building: Builds a minimal context based on the input offer and optional user/location data.
    2. Retrieval: Calls Vertex AI to fetch candidate offers that are similar to the input offer,
     applying any provided filters.
    3. Filtering: Removes already-booked items if a user_id is provided.
    4. Resolution: Maps ML items to actual offers, resolving spatial proximity if location data is provided.
    5. Ranking & Diversification: Ranks and diversifies the results for better user experience.
    6. Logging: Pushes the context and results to storage for future analysis.

    Args:
        db (AsyncSession): The active asynchronous database session.
        offer_id (str): The unique identifier of the offer to find similarities for.
        user_id (str | None): Optional user ID for personalized filtering (e.g., excluding booked items).
        categories (list[CategoryEnum] | None): Optional list of categories to filter the similar offers.
        subcategories (list[SubcategoryEnum] | None): Optional list of subcategories to filter the similar offers.
        search_group_names (list[SearchGroupNameEnum] | None):
                        Optional list of search group names to filter the similar offers.
        latitude (float | None): The user's current latitude (if geolocated).
        longitude (float | None): The user's current longitude (if geolocated).
        retrieval_model (SimilarOfferModelChoices):
                        The retrieval model to use for similar offers (coreservation or graph).
    Returns:
        SimilarOfferResponse: A structured payload containing the ordered list of similar offer IDs.
    """

    # --- 1. Initialization & Context Building ---
    call_id = str(uuid.uuid4())
    call_id_context.set(call_id)

    # 1.1. Fetch the reference offer from the database
    offer_query_result = await db.execute(select(RecommendableOffers).where(RecommendableOffers.offer_id == offer_id))
    reference_offer = offer_query_result.scalar_one_or_none()

    if not reference_offer:
        logger.warning(
            "Offer not found in recommendable offers table. Falling back to 'tops' model.",
            extra={"offer_id": offer_id, "call_id": call_id},
        )
        reference_item_id = None
    else:
        reference_item_id = reference_offer.item_id

    # 1.2. Determine geolocation context
    user_location_missing = latitude is None or longitude is None
    offer_has_location = reference_offer and reference_offer.venue_latitude and reference_offer.venue_longitude

    if user_location_missing and reference_offer and offer_has_location:
        # Fallback to the offer's venue location if user location is not provided
        latitude = reference_offer.venue_latitude
        longitude = reference_offer.venue_longitude

    # 1.3. Build user context (use provided user_id or default to unauthenticated)
    effective_user_id = user_id if user_id else UNAUTHENTICATED_USER_ID
    db_user = await db.get(EnrichedUser, effective_user_id)
    iris_id = await get_iris_id_from_coordinates(db, latitude, longitude)
    # If latitude and longitude are None, get_iris_id_from_coordinates returns None

    user_context = UserContext.build_from_database_record(
        user_id=effective_user_id,
        database_user_record=db_user,
        latitude=latitude,
        longitude=longitude,
        iris_id=iris_id,
    )

    # --- 2. Retrieval Phase ---
    logger.info(
        "Fetching similar offers from Vertex AI.",
        extra={
            "item_id": reference_item_id,
            "call_id": call_id,
            "has_filters": any([categories, subcategories, search_group_names]),
        },
    )
    retrieval_payload = build_similar_offer_retrieval_payload(
        user_context=user_context,
        call_id=call_id,
        item_id=reference_item_id,
        categories=categories,
        subcategories=subcategories,
        search_group_names=search_group_names,
    )
    if retrieval_model == SimilarOfferModelChoices.graph:
        vertex_raw_predictions = await fetch_graph_predictions_from_vertex(prediction_payload=retrieval_payload)
    else:
        vertex_raw_predictions = await fetch_retrieval_predictions_from_vertex(prediction_payload=retrieval_payload)

    # --- 3. Filtering Phase ---
    # Remove already-booked items if the user is authenticated
    if user_context.is_authenticated and user_context.user_id:
        unbooked_candidate_items = await filter_out_already_booked_items(
            db=db, candidate_items=vertex_raw_predictions.predictions, user_id=user_context.user_id
        )
    else:
        unbooked_candidate_items = vertex_raw_predictions.predictions

    # --- 4. Resolution Phase ---
    # Convert abstract items into actionable offers, keeping only the closest venues for physical items
    resolved_offers = await resolve_closest_venues_from_items(
        db=db, candidate_items=unbooked_candidate_items, user_context=user_context
    )

    # --- 5. Ranking Phase ---
    # Re-order the filtered offers using a dedicated scoring model
    ranked_offers = await rank_and_sort_offers_with_vertex(resolved_offers, user_context)

    # --- 6. Diversification & Truncation Phase ---
    # Shuffle and interleave categories to ensure a diverse final list
    diversified_offers = apply_offer_diversification(ranked_offers, should_shuffle_initial_list=False)

    # Cap the final list to a strict maximum
    final_similar_offers = diversified_offers[:SIMILAR_OFFERS_LIST_MAXIMUM_SIZE]

    # --- 7. Logging Phase ---
    recommendation_origin = "similar_offer"

    log_past_offer_context_to_sink(
        user_context=user_context,
        final_playlist=final_similar_offers,
        params=None,
        call_id=call_id,
        reco_origin=recommendation_origin,
        context_name="similar_offer",
    )

    return SimilarOfferResponse(
        results=[offer.offer_id for offer in final_similar_offers],
        params=RecommendationMetadata(reco_origin=recommendation_origin, model_origin=retrieval_model, call_id=call_id),
    )
