import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from core.diversification import apply_offer_diversification
from core.geo import get_iris_id_from_coordinates
from core.geo import resolve_effective_geolocation
from core.offer_resolution import resolve_closest_venues_from_items
from core.ranking import rank_and_sort_offers_with_vertex
from core.retrieval import build_semantic_retrieval_payload
from core.retrieval import build_similar_offer_retrieval_payload
from core.retrieval import deduplicate_candidate_items_by_item_id
from core.retrieval import fetch_graph_predictions_from_vertex
from core.retrieval import fetch_retrieval_predictions_from_vertex
from core.retrieval import fetch_semantic_predictions_from_vertex
from core.retrieval import filter_out_already_booked_items
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
     applying any provided filters.
    3. Filtering: Removes already-booked items if a user_id is provided.
    4. Resolution: Maps ML items to actual offers, resolving spatial proximity if location data is provided.
    5. Ranking: Re-orders the resolved offers using a dedicated Vertex AI scoring model.
    6. Diversification & Truncation: Shuffles and interleaves categories, then caps the list to a maximum size.
    7. Fallback (coreservation only): If the pipeline produces zero results, builds a replacement playlist
     from category-restricted tops + semantic (RFF) retrieval, then re-runs the same filter/resolve/rank/
     diversify steps (see AB TEST HACK block below).
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
    # Re-order the filtered offers using a dedicated scoring model
    ranked_offers = await rank_and_sort_offers_with_vertex(resolved_offers, user_context)

    logger.info(
        "🏆 Offers ranked by Vertex AI scoring model.",
        extra={"ranked_offers_count": len(ranked_offers)},
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
    # This fallback is meant for a genuine absence of similar offers, not for a transient Vertex AI
    # failure: when retrieval fails, vertex_raw_predictions.status is "error" (see VertexAPI), and we
    # must NOT trigger a fallback playlist — an honest empty response allows a future retry
    # instead of masking the failure behind unrelated recommendations.
    vertex_retrieval_failed = vertex_raw_predictions.status == "error"
    is_coreservation_model = retrieval_model == SimilarOfferModelChoices.coreservation
    if is_coreservation_model and len(final_similar_offers) == 0 and not vertex_retrieval_failed:
        # --- HACK for AB testing ---
        # Context: On an offer page, when the "similar offers" (coreservation) pipeline produces zero
        # results (e.g. new/niche offer with no comparable items after venue resolution/diversification),
        # the frontend still needs a playlist to display. Today's baseline ("version A") fully delegates
        # to generate_playlist_recommendations, which mixes personalized recommendation (if the user has
        # history) with three generic multi-category "tops" retrievals (top ever by booking_number,
        # trending by recent creation/release velocity) — i.e. the exact same "Tops" content already shown
        # elsewhere in the app, regardless of the original offer's category. The DS team's hypothesis is
        # that this generic "Tops" content pollutes offer-page playlists and hurts booking/consultation.
        #
        # This AB test ("version B") recomposes the fallback playlist instead:
        #   - "tops de la catégorie": tops restricted to the same category/subcategory/search_group_name
        #     filters as the original similar_offer request (instead of the unfiltered, cross-category tops
        #     used by generate_playlist_recommendations), via the existing build_similar_offer_retrieval_payload
        #     helper (item_id=None => model_type="tops", vector_column_name="booking_number_desc").
        #   - "retrieval sémantique (RFF)": item-to-item neighbors of the reference offer from the new
        #     semantic retrieval endpoint (jobs/ml_jobs/retrieval_vector "semantic" flavor, LanceDB item
        #     embeddings produced by the item_embedding microservice), fetched in parallel via
        #     build_semantic_retrieval_payload / fetch_semantic_predictions_from_vertex.
        # Both candidate pools are merged, deduplicated, then routed through the SAME
        # filter/resolve/rank/diversify pipeline as the main similar_offer flow (steps 3-6 above), so the
        # comparison between A and B isolates the *source* of the fallback candidates, not the downstream
        # ranking/diversification logic.
        #
        # Trigger condition: identical to version A — coreservation model, zero final offers after the
        # main pipeline, and no transient Vertex AI error (unchanged, not part of the AB test itself).
        #
        # Why keep the semantic call even when reference_item_id is None (offer not found in DB)?
        # build_semantic_retrieval_payload sends an empty `items` list in that case, which the semantic
        # endpoint returns as zero predictions (no anchor to search neighbors from) — the category-tops
        # leg still provides candidates, so the playlist degrades gracefully instead of crashing.
        #
        # Offer resolution cache: NOT isolated per variant. This test only changes which items are
        # retrieved (category tops + semantic neighbors vs. generic tops + personalized), not how a
        # given item_id is resolved to its closest venue (core/offer_resolution.py is untouched).
        logger.debug(
            "⚠️ 🧪 [A/B TEST] AB test hack triggered: => similar_offer fallback replaced with "
            "category tops + semantic retrieval (RFF), replacing the generic playlist_recommendation "
            "fallback (tops ever/trending across all categories).",
            extra={
                "call_id": call_id,
                "offer_id": offer_id,
                "item_id": reference_item_id,
                "original_fallback": "generate_playlist_recommendations (cross-category tops + personalized)",
                "new_fallback": "category_tops + semantic_retrieval",
                "categories": [c.value for c in categories] if categories else None,
                "subcategories": [s.value for s in subcategories] if subcategories else None,
                "search_group_names": [s.value for s in search_group_names] if search_group_names else None,
            },
        )

        category_tops_payload = build_similar_offer_retrieval_payload(
            user_context=user_context,
            call_id=call_id,
            item_id=None,
            categories=categories,
            subcategories=subcategories,
            search_group_names=search_group_names,
        )
        semantic_payload = build_semantic_retrieval_payload(
            call_id=call_id,
            user_id=user_context.user_id,
            item_id=reference_item_id,
            categories=categories,
            subcategories=subcategories,
            search_group_names=search_group_names,
        )

        category_tops_result, semantic_result = await asyncio.gather(
            fetch_retrieval_predictions_from_vertex(category_tops_payload),
            fetch_semantic_predictions_from_vertex(semantic_payload),
        )

        fallback_candidate_items = deduplicate_candidate_items_by_item_id(
            category_tops_result.predictions + semantic_result.predictions
        )

        logger.info(
            "📦 [A/B TEST] Fallback candidates retrieved (category tops + semantic).",
            extra={
                "category_tops_count": len(category_tops_result.predictions),
                "semantic_count": len(semantic_result.predictions),
                "after_dedup": len(fallback_candidate_items),
            },
        )

        if user_context.is_authenticated:
            fallback_candidate_items = await filter_out_already_booked_items(
                db=db, candidate_items=fallback_candidate_items, user_id=user_context.user_id
            )

        fallback_resolved_offers = await resolve_closest_venues_from_items(
            db=db, candidate_items=fallback_candidate_items, user_context=user_context
        )
        fallback_ranked_offers = await rank_and_sort_offers_with_vertex(fallback_resolved_offers, user_context)
        fallback_diversified_offers = apply_offer_diversification(
            fallback_ranked_offers, should_shuffle_initial_list=False
        )
        final_fallback_offers = fallback_diversified_offers[:SIMILAR_OFFERS_LIST_MAXIMUM_SIZE]

        logger.info(
            "↩️ [A/B TEST] Fallback (category tops + semantic) completed.",
            extra={"fallback_results_count": len(final_fallback_offers)},
        )

        log_past_offer_context_to_sink(
            user_context=user_context,
            final_playlist=final_fallback_offers,
            params=None,
            call_id=call_id,
            reco_origin="similar_offer_fallback_category_tops_semantic",
            context_name="similar_offer",
            model_description=settings.VERTEX_SEMANTIC_RETRIEVAL_MODEL_DESCRIPTION,
            input_offer_id=offer_id,
        )

        return SimilarOfferResponse(
            results=[offer.offer_id for offer in final_fallback_offers],
            params=RecommendationMetadata(
                reco_origin="similar_offer_fallback_category_tops_semantic",
                model_origin=settings.SIMILAR_OFFER_MODEL_CONTEXT,
                call_id=call_id,
                ab_test=settings.AB_TEST_VARIANT_LABEL,
            ),
        )
        # --- End of HACK for AB testing ---

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
