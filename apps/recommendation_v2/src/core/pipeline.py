import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.diversification import apply_offer_diversification
from core.geo import get_iris_id_from_coordinates
from core.ranking import rank_and_sort_offers_with_vertex
from core.retrieval import fetch_candidate_items_from_vertex
from core.retrieval import resolve_and_filter_closest_venues
from core.tracking import log_past_offer_context_to_sink
from core.user_context import UserContext
from models.user import EnrichedUser
from schemas.playlist_recommendation import PlaylistRequestParams
from schemas.playlist_recommendation import RecommendationMetadata
from schemas.playlist_recommendation import RecommendationResponse


async def generate_playlist_recommendations(
    db: AsyncSession, user_id: str, latitude: float | None, longitude: float | None, params: PlaylistRequestParams
) -> RecommendationResponse:
    """
    Orchestrates the entire recommendation pipeline to generate a personalized playlist of offers.

    This function acts as the main controller for the recommendation engine, following a standard
    two-tower architecture flow: Retrieve -> Filter -> Rank -> Diversify.

    Pipeline Stages:
    1. Context Building: Fetches user profile and geographical data to build a standardized context.
    2. Retrieval: Calls Vertex AI to fetch a broad list of candidate items based on user history and filters.
    3. Resolution: Maps ML items to actual physical/digital offers, resolving spatial proximity.
    4. Ranking: Scores and re-orders the resolved offers using a secondary Vertex AI ranking model.
    5. Diversification: Applies business rules (e.g., round-robin) to avoid category fatigue.
    6. Logging: Pushes the final context and results to storage for future model training.

    Args:
        db (AsyncSession): The active asynchronous database session.
        user_id (str): The unique identifier of the user requesting the playlist.
        latitude (float | None): The user's current latitude (if geolocated).
        longitude (float | None): The user's current longitude (if geolocated).
        params (PlaylistRequestParams): Filtering parameters and business rules sent by the client.

    Returns:
        RecommendationResponse: A formatted payload containing the ordered list of recommended offer IDs
                              and execution metadata.
    """

    # --- 1. Initialization & Context Building ---
    call_id = str(uuid.uuid4())

    db_user = await db.get(EnrichedUser, user_id)
    iris_id = await get_iris_id_from_coordinates(db, latitude, longitude)

    user_context = UserContext.build_from_database_record(
        user_id=user_id,
        database_user_record=db_user,
        latitude=latitude,
        longitude=longitude,
        iris_id=iris_id,
    )

    # --- 2. Retrieval Phase ---
    # Fetch a broad array of raw item candidates from the ML model
    raw_candidates = await fetch_candidate_items_from_vertex(user_context, params, call_id)

    # --- 3. Resolution & Filtering Phase ---
    # Convert abstract items into actionable offers, keeping only the closest venues for physical items
    resolved_offers = await resolve_and_filter_closest_venues(
        db=db, candidate_items=raw_candidates.predictions, user_context=user_context
    )

    # --- 4. Ranking Phase ---
    # Re-order the filtered offers using a dedicated scoring model
    ranked_offers = await rank_and_sort_offers_with_vertex(resolved_offers, user_context)

    # --- 5. Diversification & Truncation Phase ---
    # Shuffle and interleave categories to ensure a diverse final playlist
    diversified_offers = apply_offer_diversification(ranked_offers, should_shuffle_initial_list=False)

    # Cap the final playlist to a strict maximum of 60 items
    final_playlist = diversified_offers[:60]

    # --- 6. Logging & Formatting Phase ---
    recommendation_origin = "cold_start" if user_context.is_cold_start else "algo"

    log_past_offer_context_to_sink(
        user_context=user_context,
        final_playlist=final_playlist,
        params=params,
        call_id=call_id,
        reco_origin=recommendation_origin,
        context_name="recommendation",
    )

    return RecommendationResponse(
        playlist_recommended_offers=[offer.offer_id for offer in final_playlist],
        params=RecommendationMetadata(reco_origin=recommendation_origin, model_origin="default", call_id=call_id),
    )
