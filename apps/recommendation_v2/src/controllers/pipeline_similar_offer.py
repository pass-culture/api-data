import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from controllers.pipeline_playlist_recommendation import generate_playlist_recommendations
from core.diversification import apply_offer_diversification
from core.geo import get_iris_id_from_coordinates
from core.geo import resolve_effective_geolocation
from core.offer_resolution import resolve_closest_venues_from_items
from core.ranking import rank_and_sort_offers_with_vertex
from core.retrieval import build_similar_offer_retrieval_payload
from core.retrieval import fetch_graph_predictions_from_vertex
from core.retrieval import fetch_retrieval_predictions_from_vertex
from core.retrieval import fetch_similar_offer_cinema_rrf_retrieval_predictions_from_vertex
from core.retrieval import filter_out_already_booked_items
from core.retrieval import is_cinema_request
from core.tracking import log_past_offer_context_to_sink
from core.user_context import UNAUTHENTICATED_USER_ID
from core.user_context import UserContext
from models.offer import RecommendableOffers
from models.user import EnrichedUser
from schemas.categories import CategoryEnum
from schemas.categories import SearchGroupNameEnum
from schemas.categories import SubcategoryEnum
from schemas.playlist_recommendation import PlaylistRequestParams
from schemas.playlist_recommendation import RecommendationMetadata
from schemas.similar_offer import SimilarOfferModelChoices
from schemas.similar_offer import SimilarOfferResponse
from services.logger import call_id_context
from services.logger import logger


SIMILAR_OFFERS_LIST_MAXIMUM_SIZE = 20


async def generate_similar_offers(  # noqa: PLR0913, PLR0915
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
     applying any provided filters. AB test "ab-test-algo-cine-rrf": for cinema requests using the
     coreservation model, this instead fuses semantic_item_retrieval + coreservation via RRF
     (see is_cinema_request / fetch_similar_offer_cinema_rrf_retrieval_predictions_from_vertex).
    3. Filtering: Removes already-booked items if a user_id is provided.
    4. Resolution: Maps ML items to actual offers, resolving spatial proximity if location data is provided.
    5. Ranking: Re-orders the resolved offers using a dedicated Vertex AI scoring model. Skipped for
     the cinema RRF AB test variant, whose RRF-fused item_rank is the final ranking instead.
    6. Diversification & Truncation: Shuffles and interleaves categories, then caps the list to a maximum size.
    7. Fallback (coreservation only): If the pipeline produces zero results, delegates entirely to
     generate_playlist_recommendations, preserving the original category filters.
    8. Logging: Pushes the context and results to storage for future analysis.

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

    # 1.1. Fetch the reference offer from the database.
    # We use .limit(1) because an offer_id can have multiple rows (e.g. different cinema screenings).
    offer_query_result = await db.execute(
        select(RecommendableOffers).where(RecommendableOffers.offer_id == offer_id).limit(1)
    )
    reference_offer = offer_query_result.scalar_one_or_none()

    if not reference_offer:
        logger.warning(
            "Offer not found in recommendable offers table. Falling back to 'tops' model.",
            extra={"offer_id": offer_id},
        )
        reference_item_id = None
    else:
        reference_item_id = reference_offer.item_id

    # 1.2. Fetch user record (needed for subscription location fallback below)
    effective_user_id = user_id if user_id else UNAUTHENTICATED_USER_ID
    db_user = await db.get(EnrichedUser, effective_user_id)

    # 1.3. Determine geolocation context
    # Priority: GPS > user's subscription department centroid > reference offer's venue location
    effective_latitude, effective_longitude, geolocation_source = resolve_effective_geolocation(
        latitude=latitude,
        longitude=longitude,
        database_user_record=db_user,
        fallback_venue_latitude=reference_offer.venue_latitude if reference_offer else None,
        fallback_venue_longitude=reference_offer.venue_longitude if reference_offer else None,
        log_extra={"offer_id": offer_id, "user_id": effective_user_id},
    )

    iris_id = await get_iris_id_from_coordinates(db, effective_latitude, effective_longitude)
    # If latitude and longitude are None, get_iris_id_from_coordinates returns None

    user_context = UserContext.build_from_database_record(
        user_id=effective_user_id,
        database_user_record=db_user,
        latitude=effective_latitude,
        longitude=effective_longitude,
        iris_id=iris_id,
        geolocation_source=geolocation_source,
    )

    logger.info(
        "🚀 Starting similar_offers pipeline.",
        extra={
            "offer_id": offer_id,
            "item_id": reference_item_id,
            "retrieval_model": retrieval_model,
            "user_id": effective_user_id,
            "is_authenticated": user_context.is_authenticated,
            "is_geolocated": user_context.is_geolocated,
            "has_filters": any([categories, subcategories, search_group_names]),
        },
    )

    # --- 2. Retrieval Phase ---
    logger.info(
        "📡 Fetching similar offers from Vertex AI.",
        extra={
            "item_id": reference_item_id,
            "has_filters": any([categories, subcategories, search_group_names]),
        },
    )
    # --- HACK for AB testing ---
    # Context: "ab-test-algo-cine-rrf" (see docs/ab_test_algo_cine_rrf.md). similar_offer/{offer_id}
    # normally retrieves candidates from a single Vertex endpoint chosen by `retrieval_model`:
    # coreservation -> retrieval_api_client (model_type="similar_offer", item-anchored on the
    # reference offer's item_id), or graph -> graph_api_client. Both use the same payload from
    # build_similar_offer_retrieval_payload.
    #
    # For cinema-scoped requests using the coreservation model, this test instead fetches from two
    # Vertex AI endpoints in parallel using that SAME item-anchored payload —
    # "semantic_item_retrieval" (content-based) and the standard coreservation "similar_offer"
    # endpoint — up to CINEMA_RRF_RETRIEVAL_SIZE_PER_ENDPOINT (500) items each, fused via
    # Reciprocal Rank Fusion (core/rrf.py). This tests whether combining a content-based and a
    # collaborative co-occurrence signal produces better cinema "similar offers" than coreservation
    # alone. The RRF-fused order is the *final* ranking for this variant — see the second HACK
    # block below (step 5), which skips the Vertex ranking-model rerank so RRF order is preserved
    # end to end.
    #
    # Trigger condition: fires only when retrieval_model == coreservation (graph is untouched) AND
    # is_cinema_request(categories, subcategories) — categories must be exactly {CINEMA, FILM} and
    # subcategories, if provided, must be exactly the movie-screening subcategories
    # (core/retrieval.py). Nesting under coreservation keeps the existing Stage 7 zero-results
    # fallback to generate_playlist_recommendations active unchanged, since that fallback already
    # only fires for is_coreservation_model == True.
    #
    # Downstream stages shared by both variants: booked-item filtering, offer resolution,
    # diversification, truncation, tracking, and the Stage 7 fallback. Only retrieval (this block)
    # and ranking (step 5 below) differ for cinema.
    #
    # Offer resolution cache: NOT isolated for this test. The variant changes which items are
    # retrieved, not how a given item resolves to a venue, so resolving the same item_id to the
    # same venue is identical across variants (see docs/ab_testing.md, section 6).
    is_cinema_similar_offer_request = retrieval_model == SimilarOfferModelChoices.coreservation and is_cinema_request(
        categories, subcategories
    )
    if is_cinema_similar_offer_request:
        logger.debug(
            "🎬🧪 [A/B TEST] AB test hack triggered: => using cinema RRF retrieval "
            "(semantic_item_retrieval + coreservation, fused via RRF) instead of the standard "
            "single-endpoint retrieval.",
            extra={
                "call_id": call_id,
                "offer_id": offer_id,
                "item_id": reference_item_id,
                "requested_categories": [c.value for c in categories or []],
                "requested_subcategories": [s.value for s in subcategories or []],
            },
        )
        vertex_raw_predictions = await fetch_similar_offer_cinema_rrf_retrieval_predictions_from_vertex(
            user_context=user_context,
            call_id=call_id,
            item_id=reference_item_id,
            categories=categories,
            subcategories=subcategories,
            search_group_names=search_group_names,
        )
    else:
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
    # --- End of HACK for AB testing ---

    logger.info(
        "📦 Raw candidates retrieved from Vertex AI.",
        extra={"raw_candidate_count": len(vertex_raw_predictions.predictions)},
    )

    # --- 3. Filtering Phase ---
    # Remove already-booked items if the user is authenticated
    if user_context.is_authenticated:
        unbooked_candidate_items = await filter_out_already_booked_items(
            db=db, candidate_items=vertex_raw_predictions.predictions, user_id=user_context.user_id
        )
        logger.info(
            "🚫 Already-booked items filtered out.",
            extra={
                "before_filter": len(vertex_raw_predictions.predictions),
                "after_filter": len(unbooked_candidate_items),
                "filtered_out": len(vertex_raw_predictions.predictions) - len(unbooked_candidate_items),
            },
        )
    else:
        unbooked_candidate_items = vertex_raw_predictions.predictions
        logger.info(
            "⏭️ Skipping already-booked filter: user is not authenticated or not in database.",
            extra={"user_id": effective_user_id},
        )

    # --- 4. Resolution Phase ---
    # Convert abstract items into actionable offers, keeping only the closest venues for physical items
    resolved_offers = await resolve_closest_venues_from_items(
        db=db, candidate_items=unbooked_candidate_items, user_context=user_context
    )

    logger.info(
        "📍 Offers resolved from items (venue proximity applied).",
        extra={"resolved_offers_count": len(resolved_offers)},
    )

    # --- 5. Ranking Phase ---
    # --- HACK for AB testing ---
    # Context: "ab-test-algo-cine-rrf" — see the retrieval HACK block above for full context;
    # `is_cinema_similar_offer_request` is computed there and reused here.
    #
    # For cinema requests, the RRF fusion computed during retrieval already *is* the ranking under
    # test — calling the Vertex ranking model afterwards would overwrite it with an unrelated
    # model's opinion. So the rerank is skipped and resolved offers are sorted by `item_rank`,
    # which reciprocal_rank_fusion (core/rrf.py) already set to the fused rank (1 = best).
    if is_cinema_similar_offer_request:
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
        extra={
            "ranked_offers_count": len(ranked_offers),
            "is_cinema_similar_offer_request": is_cinema_similar_offer_request,
        },
    )

    # --- 6. Diversification & Truncation Phase ---
    # Shuffle and interleave categories to ensure a diverse final list
    diversified_offers = apply_offer_diversification(ranked_offers, should_shuffle_initial_list=False)

    # Cap the final list to a strict maximum
    final_similar_offers = diversified_offers[:SIMILAR_OFFERS_LIST_MAXIMUM_SIZE]

    logger.info(
        "🎨 Diversification applied — final similar offers list ready.",
        extra={
            "after_diversification": len(diversified_offers),
            "final_list_size": len(final_similar_offers),
        },
    )

    # --- 7. Fallback Phase (coreservation only) ---
    # If the full pipeline produced zero results, delegate entirely to generate_playlist_recommendations.
    # That function handles its own retrieval, ranking, diversification, and logging — no duplication needed.
    # This fallback is meant for a genuine absence of similar offers, not for a transient Vertex AI
    # failure: when retrieval fails, vertex_raw_predictions.status is "error" (see VertexAPI), and we
    # must NOT delegate to the playlist pipeline — an honest empty response allows a future retry
    # instead of masking the failure behind unrelated playlist recommendations.
    vertex_retrieval_failed = vertex_raw_predictions.status == "error"
    is_coreservation_model = retrieval_model == SimilarOfferModelChoices.coreservation
    if is_coreservation_model and len(final_similar_offers) == 0 and not vertex_retrieval_failed:
        logger.warning(
            "⚠️ No similar offers found with coreservation model. Falling back to standard recommendation pipeline.",
            extra={
                "offer_id": offer_id,
                "latitude": latitude,
                "longitude": longitude,
                "categories": categories,
                "subcategories": subcategories,
                "search_group_names": search_group_names,
            },
        )
        fallback_params = PlaylistRequestParams(
            categories=categories,
            subcategories=subcategories,
            search_group_names=search_group_names,
        )
        fallback_response = await generate_playlist_recommendations(
            db=db,
            user_id=user_context.user_id,
            latitude=user_context.latitude,
            longitude=user_context.longitude,
            params=fallback_params,
        )

        logger.info(
            "↩️ Fallback to playlist_recommendation pipeline completed.",
            extra={
                "fallback_call_id": fallback_response.params.call_id,
                "fallback_results_count": len(
                    fallback_response.playlist_recommended_offers[:SIMILAR_OFFERS_LIST_MAXIMUM_SIZE]
                ),
            },
        )

        return SimilarOfferResponse(
            results=fallback_response.playlist_recommended_offers[:SIMILAR_OFFERS_LIST_MAXIMUM_SIZE],
            params=RecommendationMetadata(
                reco_origin="recommendation_fallback",
                model_origin=fallback_response.params.model_origin,
                call_id=call_id,
                ab_test=settings.AB_TEST_VARIANT_LABEL,
            ),
        )

    # --- 8. Logging Phase ---
    recommendation_origin = "similar_offer" if retrieval_model == SimilarOfferModelChoices.coreservation else "graph"
    model_description = (
        settings.VERTEX_SIMILAR_OFFER_MODEL_DESCRIPTION
        if retrieval_model == SimilarOfferModelChoices.coreservation
        else settings.VERTEX_GRAPH_RETRIEVAL_MODEL_DESCRIPTION
    )

    log_past_offer_context_to_sink(
        user_context=user_context,
        final_playlist=final_similar_offers,
        params=None,
        call_id=call_id,
        reco_origin=recommendation_origin,
        context_name="similar_offer",
        model_description=model_description,
        input_offer_id=offer_id,
    )

    return SimilarOfferResponse(
        results=[offer.offer_id for offer in final_similar_offers],
        params=RecommendationMetadata(
            reco_origin=recommendation_origin,
            model_origin=settings.SIMILAR_OFFER_MODEL_CONTEXT,
            call_id=call_id,
            ab_test=settings.AB_TEST_VARIANT_LABEL,
        ),
    )
