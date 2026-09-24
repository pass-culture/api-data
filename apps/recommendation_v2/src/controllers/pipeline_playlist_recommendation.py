import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from core.diversification import apply_offer_diversification
from core.geo import get_iris_id_from_coordinates
from core.geo import resolve_effective_geolocation
from core.offer_resolution import resolve_closest_venues_from_items
from core.ranking import rank_and_sort_offers_with_vertex
from core.retrieval import build_all_playlist_recommendation_retrieval_payloads
from core.retrieval import fetch_all_playlist_recommendation_retrieval_predictions_from_vertex
from core.retrieval import fetch_cinema_rrf_retrieval_predictions_from_vertex
from core.retrieval import filter_out_already_booked_items
from core.retrieval import is_cinema_playlist_request
from core.tracking import log_past_offer_context_to_sink
from core.user_context import UNAUTHENTICATED_USER_ID
from core.user_context import UserContext
from models.user import EnrichedUser
from schemas.playlist_recommendation import PlaylistRequestParams
from schemas.playlist_recommendation import RecommendationMetadata
from schemas.playlist_recommendation import RecommendationResponse
from services.logger import call_id_context
from services.logger import logger


PLAYLIST_RECOMMENDATION_MAXIMUM_SIZE = 20


async def generate_playlist_recommendations(
    db: AsyncSession, user_id: str, latitude: float | None, longitude: float | None, params: PlaylistRequestParams
) -> RecommendationResponse:
    """
    Orchestrates the entire recommendation pipeline to generate a personalized playlist of offers.

    This function acts as the main controller for the recommendation engine, following a standard
    recommender architecture flow: Retrieve -> Filter -> Rank -> Diversify.

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
    call_id_context.set(call_id)

    db_user = await db.get(EnrichedUser, user_id)

    effective_latitude, effective_longitude, geolocation_source = resolve_effective_geolocation(
        latitude=latitude,
        longitude=longitude,
        database_user_record=db_user,
        log_extra={"user_id": user_id},
    )

    iris_id = await get_iris_id_from_coordinates(db, effective_latitude, effective_longitude)

    user_context = UserContext.build_from_database_record(
        user_id=user_id,
        database_user_record=db_user,
        latitude=effective_latitude,
        longitude=effective_longitude,
        iris_id=iris_id,
        geolocation_source=geolocation_source,
    )

    logger.info(
        "🚀 Starting playlist_recommendation pipeline.",
        extra={
            "user_id": user_id,
            "is_authenticated": user_context.is_authenticated,
            "is_cold_start": user_context.is_cold_start,
            "is_geolocated": user_context.is_geolocated,
            "iris_id": iris_id,
            "remaining_credit": user_context.remaining_credit,
            "bookings_count": user_context.bookings_count,
        },
    )

    # --- 2. Retrieval Phase ---
    # --- HACK for AB testing ---
    # Context: "ab-test-algo-cine-rrf". The playlist_recommendation endpoint normally retrieves
    # candidates from 4 payloads sent to a single Vertex endpoint (personalized + 3 tops variants,
    # see build_all_playlist_recommendation_retrieval_payloads), merged by plain dedup.
    #
    # For cinema playlists, this test replaces that retrieval strategy entirely: candidates are
    # instead sourced from two Vertex AI endpoints — "semantic_item_retrieval" (content-based) and
    # "recommendation_user_retrieval" (collaborative filtering) — fetching 500 items from each, and
    # fusing the two ranked lists with Reciprocal Rank Fusion (see core/retrieval.py) instead of a
    # plain concat/dedup. This tests whether combining a content-based and a collaborative signal
    # produces better cinema recommendations than the standard 4-source strategy. The RRF-fused
    # order is the *final* ranking for this variant — see the second HACK block below (step 4),
    # which skips the Vertex ranking-model rerank for cinema so RRF order is preserved end to end.
    #
    # Trigger condition: fires only when the client explicitly requests cinema items — see
    # is_cinema_playlist_request (core/retrieval.py) for the exact predicate: categories must be
    # exactly {CINEMA, FILM} (MOVIE_LIKE_CATEGORIES) AND subcategories, if provided at all, must be
    # exactly the movie-screening subcategories (AVAILABLE_MOVIE_SUBCATEGORIES). The cinema
    # retrieval itself further narrows subcategories internally when building its Vertex payloads —
    # this does not mutate `params`, so the client's original request is still what gets logged to
    # the tracking sink below.
    #
    # Downstream stages shared by both variants: booked-item filtering, offer resolution,
    # diversification, truncation to PLAYLIST_RECOMMENDATION_MAXIMUM_SIZE. Only the retrieval/
    # candidate-merge step (this block) and the ranking step (step 4 below) differ for cinema.
    #
    # Offer resolution cache: NOT isolated for this test. The variant changes which items are
    # retrieved, not how a given item resolves to a venue, so resolving the same item_id to the
    # same venue is identical across variants (see docs/ab_testing.md, section 6).
    is_cinema_request = is_cinema_playlist_request(params)
    if is_cinema_request:
        logger.debug(
            "🎬🧪 [A/B TEST] AB test hack triggered: => using cinema RRF retrieval "
            "(semantic_item_retrieval + recommendation_user_retrieval, fused via RRF) "
            "instead of the standard 4-payload retrieval.",
            extra={
                "call_id": call_id,
                "original_retrieval_strategy": "build_all_playlist_recommendation_retrieval_payloads",
                "new_retrieval_strategy": "fetch_cinema_rrf_retrieval_predictions_from_vertex",
                "requested_categories": [c.value for c in params.categories or []],
                "requested_subcategories": [s.value for s in params.subcategories or []],
            },
        )
        raw_candidate_items = await fetch_cinema_rrf_retrieval_predictions_from_vertex(
            user_context=user_context, call_id=call_id, params=params
        )
    else:
        # Build all retrieval payloads (1 for cold start, 4 for warm start) and fetch them in parallel
        retrieval_payloads = build_all_playlist_recommendation_retrieval_payloads(
            user_context=user_context, call_id=call_id, params=params
        )

        logger.info(
            "📡 Sending retrieval payloads to Vertex AI.",
            extra={
                "payload_count": len(retrieval_payloads),
                "is_cold_start": user_context.is_cold_start,
            },
        )

        raw_candidate_items = await fetch_all_playlist_recommendation_retrieval_predictions_from_vertex(
            retrieval_payloads=retrieval_payloads
        )
    # --- End of HACK for AB testing ---

    logger.info(
        "📦 Raw candidates retrieved from Vertex AI.",
        extra={"raw_candidate_count": len(raw_candidate_items)},
    )

    # --- 3. Filtering Phase & Resolution ---
    if user_context.is_authenticated:
        unbooked_candidate_items = await filter_out_already_booked_items(
            db=db, candidate_items=raw_candidate_items, user_id=user_context.user_id
        )
        logger.info(
            "🚫 Already-booked items filtered out.",
            extra={
                "before_filter": len(raw_candidate_items),
                "after_filter": len(unbooked_candidate_items),
                "filtered_out": len(raw_candidate_items) - len(unbooked_candidate_items),
            },
        )
    else:
        unbooked_candidate_items = raw_candidate_items
        logger.info(
            "⏭️ Skipping already-booked filter: user is not authenticated or not in database.",
            extra={"user_id": user_id},
        )

    # Convert abstract items into actionable offers, keeping only the closest venues for physical items
    resolved_offers = await resolve_closest_venues_from_items(
        db=db, candidate_items=unbooked_candidate_items, user_context=user_context
    )

    logger.info(
        "📍 Offers resolved from items (venue proximity applied).",
        extra={"resolved_offers_count": len(resolved_offers)},
    )

    # --- 4. Ranking Phase ---
    # --- HACK for AB testing ---
    # Context: "ab-test-algo-cine-rrf" (see the retrieval HACK block above for full context and
    # trigger condition — `is_cinema_request` is computed there and reused here).
    #
    # For cinema playlists, the Reciprocal Rank Fusion computed during retrieval already *is* the
    # ranking under test — calling the Vertex AI ranking model afterwards would overwrite it with
    # an unrelated model's opinion, which is not what this test measures. So for cinema, the
    # ranking-model rerank is skipped entirely and resolved offers are instead sorted by
    # `item_rank`, which reciprocal_rank_fusion (core/rrf.py, called from core/retrieval.py)
    # already set to the fused RRF rank (1 = best). This mirrors the existing no-predictions
    # fallback sort in rank_and_sort_offers_with_vertex, applied here unconditionally for cinema.
    #
    # Diversification (step 5 below) still runs afterwards for both variants, unchanged.
    if is_cinema_request:
        logger.debug(
            "🎬🧪 [A/B TEST] AB test hack triggered: => skipping Vertex AI ranking-model rerank, "
            "sorting by RRF-fused item_rank instead.",
            extra={"call_id": call_id, "resolved_offers_count": len(resolved_offers)},
        )
        ranked_offers = sorted(
            resolved_offers, key=lambda offer: offer.item_rank if offer.item_rank is not None else float("inf")
        )
    else:
        # Re-order the filtered offers using a dedicated scoring model
        ranked_offers = await rank_and_sort_offers_with_vertex(resolved_offers, user_context)
    # --- End of HACK for AB testing ---

    logger.info(
        "🏆 Offers ranked.",
        extra={"ranked_offers_count": len(ranked_offers), "is_cinema_playlist_request": is_cinema_request},
    )

    # --- 5. Diversification & Truncation Phase ---
    # Shuffle and interleave categories to ensure a diverse final playlist
    diversified_offers = apply_offer_diversification(ranked_offers, should_shuffle_initial_list=False)

    # Cap the final playlist to a strict maximum
    final_playlist = diversified_offers[:PLAYLIST_RECOMMENDATION_MAXIMUM_SIZE]

    logger.info(
        "🎨 Diversification applied — final playlist ready.",
        extra={
            "after_diversification": len(diversified_offers),
            "final_playlist_size": len(final_playlist),
            "truncated": len(diversified_offers) > len(final_playlist),
        },
    )

    # --- 6. Logging & Formatting Phase ---
    if user_context.user_id == UNAUTHENTICATED_USER_ID:
        recommendation_origin = "unknown"
    else:
        recommendation_origin = "cold_start" if user_context.is_cold_start else "algo"

    if user_context.is_authenticated:
        log_past_offer_context_to_sink(
            user_context=user_context,
            final_playlist=final_playlist,
            params=params,
            call_id=call_id,
            reco_origin=recommendation_origin,
            context_name="recommendation",
            model_description=settings.VERTEX_RECOMMENDATION_MODEL_DESCRIPTION,
        )
    else:
        # If the user does not exist in our database (is_authenticated=False), we skip tracking to avoid polluting
        # the dataset with guest/unknown users who cannot produce engagement signals (clicks/bookings).
        logger.debug(
            "⏭️ Skipping tracking: User is not authenticated (guest/unknown user).",
            extra={"user_id": user_id},
        )

    return RecommendationResponse(
        playlist_recommended_offers=[offer.offer_id for offer in final_playlist],
        params=RecommendationMetadata(
            reco_origin=recommendation_origin,
            model_origin=settings.PLAYLIST_RECOMMENDATION_MODEL_CONTEXT,
            call_id=call_id,
            ab_test=settings.AB_TEST_VARIANT_LABEL,
        ),
        from_cache=False,
    )
