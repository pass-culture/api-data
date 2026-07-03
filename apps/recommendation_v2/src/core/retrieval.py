import asyncio
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from connectors import graph_api_client
from connectors import retrieval_api_client
from connectors.redis_api import RedisAPI
from connectors.redis_api import redis_api
from connectors.vertex_api import VertexPredictionResult
from core.geo import MAX_DISTANCE_METERS_FOR_OFFER_RETRIEVAL
from core.geo import calculate_haversine_distance_in_meters
from core.geo import find_closest_offers_with_h3_index
from core.user_context import UserContext
from models.items import NonRecommendableItems
from schemas.categories import CategoryEnum
from schemas.categories import SearchGroupNameEnum
from schemas.categories import SubcategoryEnum
from schemas.enriched_offer import EnrichedRecommendableOffer
from schemas.playlist_recommendation import PlaylistRequestParams
from schemas.vertex_prediction_item import ItemOrigin
from schemas.vertex_prediction_item import RecommendableItem
from services.h3 import get_h3_index_from_coordinates
from services.logger import logger
from utils.benchmark import log_execution_time


DEFAULT_MAX_DISTANCE_IN_METERS = 100_000

# ISO v1: each retrieval endpoint fetches 150 items; 4 endpoints * 150 = up to 600 items before deduplication.
PLAYLIST_RECOMMENDATION_RETRIEVAL_SIZE_PER_ENDPOINT = 150

# ISO v1: OfferRetrievalEndpoint uses size=100.
SIMILAR_OFFER_RETRIEVAL_SIZE = 100

# ==============================================================================
# PLAYLIST RECOMMENDATION
# ==============================================================================


def _build_playlist_recommendation_search_filters(
    user_context: UserContext, params: PlaylistRequestParams
) -> dict[str, Any]:
    """
    Builds the filter dictionary required by Vertex AI Vector Search.

    Vertex AI expects a specific JSON syntax to filter embeddings before nearest-neighbor
    search. This function translates Pydantic business parameters into those strict filters.

    Args:
        user_context (UserContext): The contextual data of the current user (credit, etc.).
        params (PlaylistRequestParams): Filtering constraints provided by the API client.

    Returns:
        dict[str, Any]: A dictionary representing the '$and' filter block for Vertex AI.

    Example:
        {"$and": [{"stock_price": {"$lte": 150.0}}, {"category": {"$in": ["LIVRES", "CINEMA"]}}]}
    """
    and_conditions = []

    # 1. Date constraints
    date_field = "stock_beginning_date" if params.is_event else "offer_creation_date"
    if params.start_date:
        and_conditions.append({date_field: {"$gte": params.start_date.timestamp()}})
    if params.end_date:
        and_conditions.append({date_field: {"$lte": params.end_date.timestamp()}})

    # 2. Price constraints (bounded by user's remaining credit)
    # TODO: (jmontagnat - 2026-06-23)
    #  Corrupted data in the database can cause remaining_credit to be negative for some users.
    #  This max(0, ...) is a temporary fix to prevent an absurd price filter (e.g. stock_price <= -5).
    #  Remove this fix once the investigation is complete and the user data has been cleaned up in the database.
    effective_price_max = round(max(0, user_context.remaining_credit))
    if params.price_max is not None:
        effective_price_max = min(params.price_max, effective_price_max)

    and_conditions.append({"stock_price": {"$lte": float(effective_price_max)}})

    if params.price_min is not None:
        and_conditions.append({"stock_price": {"$gte": float(params.price_min)}})

    # 3. Boolean and contextual flags
    if params.is_duo is not None:
        and_conditions.append({"offer_is_duo": {"$eq": float(params.is_duo)}})

    # TODO: This code is ISO v1 but the logic is a bit weird since the only value possible for is_restrained is 0
    #  because is_restrained cannot be None due to default value in the Pydantic model
    is_restrained = params.is_restrained if params.is_restrained is not None else True
    if is_restrained:
        and_conditions.append({"is_restrained": {"$eq": 0.0}})

    if params.is_digital is not None:
        val = 0.0 if params.is_digital else 1.0
        and_conditions.append({"is_geolocated": {"$eq": val}})

    # 4. List mappings (Translate domain fields to Vertex specific fields)
    list_mappings = {
        "categories": "category",
        "subcategories": "subcategory_id",
        "search_group_names": "search_group_name",
    }

    for param_field, vertex_field in list_mappings.items():
        values = getattr(params, param_field)
        if values:
            and_conditions.append({vertex_field: {"$in": values}})

    return {"$and": and_conditions}


def build_playlist_recommendation_retrieval_payload(
    user_context: UserContext, call_id: str, params: PlaylistRequestParams
) -> dict[str, Any]:
    """
    Constructs the prediction payload for playlist recommendations.
    """
    search_filters = _build_playlist_recommendation_search_filters(user_context, params)

    prediction_payload: dict[str, Any] = {
        "call_id": call_id,
        "user_id": user_context.user_id,
        "params": search_filters,
        # TODO: Remove this field or rename it in the Vertex API.
        #  It is currently required, but having a hardcoded "debug" flag in production is confusing.
        "debug": 1,
        "prefilter": 1,
        "size": PLAYLIST_RECOMMENDATION_RETRIEVAL_SIZE_PER_ENDPOINT,
    }

    if user_context.is_cold_start:
        prediction_payload["model_type"] = "tops"
        # TODO find out which vector column(s) fit best for cold start scenario.
        prediction_payload["vector_column_name"] = (
            "booking_number_desc"  # "booking_creation_trend_desc", "booking_release_trend_desc"
        )
        prediction_payload["re_rank"] = 0
    else:
        prediction_payload["model_type"] = "recommendation"

    return prediction_payload


# ==============================================================================
# PLAYLIST RECOMMENDATION — MULTI-ENDPOINT (ISO v1)
# ==============================================================================


def _build_base_playlist_recommendation_payload(
    user_context: UserContext, call_id: str, params: PlaylistRequestParams
) -> dict[str, Any]:
    """
    Builds the common base fields shared by all playlist recommendation retrieval payloads.

    This base dict is injected into each specific payload variant (tops or recommendation)
    via dictionary unpacking.

    Args:
        user_context (UserContext): The contextual data of the current user.
        call_id (str): The unique identifier for the current API call.
        params (PlaylistRequestParams): Filtering constraints provided by the API client.

    Returns:
        dict[str, Any]: Base fields common to all retrieval payload variants.
    """
    search_filters = _build_playlist_recommendation_search_filters(user_context, params)

    return {
        "call_id": call_id,
        "user_id": user_context.user_id,
        "params": search_filters,
        "debug": 1,
        "size": PLAYLIST_RECOMMENDATION_RETRIEVAL_SIZE_PER_ENDPOINT,
    }


def _build_personalized_recommendation_retrieval_payload(
    user_context: UserContext, call_id: str, params: PlaylistRequestParams
) -> dict[str, Any]:
    """
    Builds the personalized collaborative filtering retrieval payload.

    ISO v1: RecommendationRetrievalEndpoint — model_type="recommendation", prefilter=1.
    Returns items predicted from the user's historical interactions.
    """
    base = _build_base_playlist_recommendation_payload(user_context, call_id, params)

    return {
        **base,
        "model_type": "recommendation",
        "prefilter": 1,
    }


def _build_booking_number_tops_retrieval_payload(
    user_context: UserContext, call_id: str, params: PlaylistRequestParams
) -> dict[str, Any]:
    """
    Builds the tops retrieval payload ranked by total booking number (overall popularity).

    ISO v1: BookingNumberRetrievalEndpoint — model_type="tops", vector_column_name="booking_number_desc".
    """
    base = _build_base_playlist_recommendation_payload(user_context, call_id, params)

    return {
        **base,
        "model_type": "tops",
        "vector_column_name": "booking_number_desc",
        "re_rank": 0,
    }


def _build_release_trend_tops_retrieval_payload(
    user_context: UserContext, call_id: str, params: PlaylistRequestParams
) -> dict[str, Any]:
    """
    Builds the tops retrieval payload ranked by recent release trend.

    ISO v1: ReleaseTrendRetrievalEndpoint — model_type="tops", vector_column_name="booking_release_trend_desc".
    """
    base = _build_base_playlist_recommendation_payload(user_context, call_id, params)

    return {
        **base,
        "model_type": "tops",
        "vector_column_name": "booking_release_trend_desc",
        "re_rank": 0,
    }


def _build_creation_trend_tops_retrieval_payload(
    user_context: UserContext, call_id: str, params: PlaylistRequestParams
) -> dict[str, Any]:
    """
    Builds the tops retrieval payload ranked by recent creation trend.

    ISO v1: CreationTrendRetrievalEndpoint — model_type="tops", vector_column_name="booking_creation_trend_desc".
    """
    base = _build_base_playlist_recommendation_payload(user_context, call_id, params)

    return {
        **base,
        "model_type": "tops",
        "vector_column_name": "booking_creation_trend_desc",
        "re_rank": 0,
    }


def build_all_playlist_recommendation_retrieval_payloads(
    user_context: UserContext, call_id: str, params: PlaylistRequestParams
) -> list[dict[str, Any]]:
    """
    Returns all retrieval payloads to be sent to Vertex AI in parallel.

    Mirrors the v1 multi-endpoint strategy:
    - Cold start (no user history): 1 payload  → tops by booking number only.
    - Warm start (user has history): 4 payloads → tops * 3 + personalized recommendation.

    Warm start payload breakdown (each fetches 150 items):
    ┌───┬────────────────────────────┬────────────────────────────────────┐
    │ # │ Model Type                 │ vector_column_name                 │
    ├───┼────────────────────────────┼────────────────────────────────────┤
    │ 1 │ recommendation (personal.) │ N/A  (user embedding)              │
    │ 2 │ tops                       │ booking_number_desc                │
    │ 3 │ tops                       │ booking_release_trend_desc         │
    │ 4 │ tops                       │ booking_creation_trend_desc        │
    └───┴────────────────────────────┴────────────────────────────────────┘

    Maximum candidate pool before deduplication: 4 * 150 = 600 items.

    Args:
        user_context (UserContext): The contextual data of the current user.
        call_id (str): The unique identifier for the current API call.
        params (PlaylistRequestParams): Filtering constraints provided by the API client.

    Returns:
        list[dict[str, Any]]: A list of prediction payloads ready to be sent in parallel to Vertex AI.

    Example:
        >>> payloads = build_all_playlist_recommendation_retrieval_payloads(user_context, call_id, params)
        >>> len(payloads)  # 4 for warm start, 1 for cold start
        4
    """
    if user_context.is_cold_start:
        return [_build_booking_number_tops_retrieval_payload(user_context, call_id, params)]

    return [
        _build_personalized_recommendation_retrieval_payload(user_context, call_id, params),
        _build_booking_number_tops_retrieval_payload(user_context, call_id, params),
        _build_release_trend_tops_retrieval_payload(user_context, call_id, params),
        _build_creation_trend_tops_retrieval_payload(user_context, call_id, params),
    ]


def deduplicate_candidate_items_by_item_id(
    candidate_items: list[RecommendableItem],
) -> list[RecommendableItem]:
    """
    Removes duplicate items from a candidate list, keeping only the first occurrence per item_id.

    When multiple retrieval endpoints return overlapping results, the same item_id can appear
    several times. This function ensures each item_id is represented only once in the output.

    Args:
        candidate_items (list[RecommendableItem]): Raw items from one or more retrieval endpoints,
            possibly containing duplicates.

    Returns:
        list[RecommendableItem]: A deduplicated list preserving the order of first occurrences.

    Example:
        Input:  [Item("A"), Item("B"), Item("A"), Item("C")]
        Output: [Item("A"), Item("B"), Item("C")]
    """
    seen_item_ids: set[str] = set()
    deduplicated_items: list[RecommendableItem] = []

    for item in candidate_items:
        if item.item_id not in seen_item_ids:
            seen_item_ids.add(item.item_id)
            deduplicated_items.append(item)

    return deduplicated_items


@log_execution_time
async def fetch_all_playlist_recommendation_retrieval_predictions_from_vertex(
    retrieval_payloads: list[dict[str, Any]],
) -> list[RecommendableItem]:
    """
    Fetches candidate items from all retrieval payloads concurrently, then deduplicates the results.

    Calls each Vertex AI retrieval endpoint simultaneously using asyncio.gather, then merges all
    raw predictions into a single flat list and removes duplicates. This mirrors the v1 behavior
    where all retrieval endpoints are called in parallel via asyncio.gather.

    Args:
        retrieval_payloads (list[dict[str, Any]]): One payload per retrieval endpoint,
            as returned by build_all_playlist_recommendation_retrieval_payloads.

    Returns:
        list[RecommendableItem]: A flat, deduplicated list of candidate items from all endpoints.

    Example (warm start, 4 payloads):
        Each endpoint returns up to 150 items → up to 600 raw items → deduplicated output.
    """
    parallel_results: list[VertexPredictionResult] = await asyncio.gather(
        *[fetch_retrieval_predictions(payload) for payload in retrieval_payloads]
    )

    all_candidate_items: list[RecommendableItem] = []
    for result in parallel_results:
        all_candidate_items.extend(result.predictions)

    deduplicated = deduplicate_candidate_items_by_item_id(all_candidate_items)

    logger.debug(
        "🔀 Retrieval endpoints aggregated and deduplicated.",
        extra={
            "endpoint_count": len(parallel_results),
            "raw_total": len(all_candidate_items),
            "after_dedup": len(deduplicated),
            "duplicates_removed": len(all_candidate_items) - len(deduplicated),
        },
    )

    return deduplicated


# ==============================================================================
# SIMILAR OFFER
# ==============================================================================


def _build_similar_offer_search_filters(
    categories: list[CategoryEnum] | None = None,
    subcategories: list[SubcategoryEnum] | None = None,
    search_group_names: list[SearchGroupNameEnum] | None = None,
) -> dict[str, Any]:
    """
    Builds the filter dictionary required by Vertex AI Vector Search for similar offers.

    Vertex AI expects a specific JSON syntax to filter embeddings before nearest-neighbor
    search. This function translates lists of categories into those strict filters.

    Args:
        categories (list[CategoryEnum] | None): A list of categories to filter by.
        subcategories (list[SubcategoryEnum] | None): A list of subcategories to filter by.
        search_group_names (list[SearchGroupNameEnum] | None): A list of search group names to filter by.

    Returns:
        dict[str, Any]: A dictionary representing the '$and' filter block for Vertex AI.

    Example:
        {"$and": [{"category": {"$in": ["LIVRES", "CINEMA"]}}]}
    """
    and_conditions = []

    if categories:
        and_conditions.append({"category": {"$in": [c.value for c in categories]}})
    if subcategories:
        and_conditions.append({"subcategory_id": {"$in": [s.value for s in subcategories]}})
    if search_group_names:
        and_conditions.append({"search_group_name": {"$in": [s.value for s in search_group_names]}})

    return {"$and": and_conditions}


def build_similar_offer_retrieval_payload(
    user_context: UserContext,
    call_id: str,
    item_id: str | None,
    categories: list[CategoryEnum] | None = None,
    subcategories: list[SubcategoryEnum] | None = None,
    search_group_names: list[SearchGroupNameEnum] | None = None,
) -> dict[str, Any]:
    """
    Constructs the prediction payload for similar offer recommendations.

    Args:
        user_context (UserContext): Standardized user context.
        call_id (str): Tracker call id.
        item_id (str | None): ID of the item to find similarities for.
        categories (list[CategoryEnum] | None): Filter by categories.
        subcategories (list[SubcategoryEnum] | None): Filter by subcategories.
        search_group_names (list[SearchGroupNameEnum] | None): Filter by search groups.

    Returns:
        dict[str, Any]: The prediction payload required by Vertex API to retrieve similar items.
    """
    prediction_payload: dict[str, Any] = {
        "call_id": call_id,
        "user_id": user_context.user_id,
        "offer_id": item_id,
        # Vertex endpoint calls this field "offer_id" but it is actually the "item_id".
        # A bit misleading but we keep it for consistency with the Vertex API.
        "debug": 1,
        "prefilter": 1,
        "size": SIMILAR_OFFER_RETRIEVAL_SIZE,
        "search_after": None,
    }

    if categories or subcategories or search_group_names:
        prediction_payload["params"] = _build_similar_offer_search_filters(
            categories=categories,
            subcategories=subcategories,
            search_group_names=search_group_names,
        )

    if item_id is None:
        prediction_payload["model_type"] = "tops"
        prediction_payload["vector_column_name"] = (
            "booking_number_desc"  # "booking_creation_trend_desc", "booking_release_trend_desc"
        )
        prediction_payload["re_rank"] = 0
    else:
        prediction_payload["model_type"] = "similar_offer"

    return prediction_payload


# ==============================================================================
# SHARED / POST-PROCESSING
# ==============================================================================


@log_execution_time
async def fetch_retrieval_predictions_from_vertex(prediction_payload: dict[str, Any]) -> VertexPredictionResult:
    """
    Calls the Vertex AI matching engine to retrieve a raw list of candidate Item IDs.
    """
    prediction_result = await retrieval_api_client.fetch_retrieval_predictions(feature_payloads=[prediction_payload])

    return prediction_result


@log_execution_time
async def fetch_graph_predictions_from_vertex(prediction_payload: dict[str, Any]) -> VertexPredictionResult:
    """
    Calls the Vertex AI matching engine to retrieve a raw list of candidate Item IDs.
    """
    prediction_result = await graph_api_client.fetch_retrieval_predictions(feature_payloads=[prediction_payload])

    return prediction_result


def _is_retrieval_cache_enabled_for_model_type(model_type: str) -> bool:
    """
    Returns True if the retrieval cache is active for the given Vertex model_type.

    Each model_type maps to an independent feature flag in settings, so each
    sub-strategy (similar_offer, tops, recommendation) can be toggled separately
    without affecting the others.

    ┌─────────────────┬──────────────────────────────────────────────────┐
    │ model_type      │ Feature flag                                     │
    ├─────────────────┼──────────────────────────────────────────────────┤
    │ similar_offer   │ settings.RETRIEVAL_CACHE_SIMILAR_OFFER_ENABLED   │
    │ tops            │ settings.RETRIEVAL_CACHE_PLAYLIST_TOPS_ENABLED   │
    │ recommendation  │ settings.RETRIEVAL_CACHE_PLAYLIST_PERSONALIZED_  │
    │                 │           ENABLED                                │
    ├─────────────────┼──────────────────────────────────────────────────┤
    │ (any other)     │ False — unknown model_types are never cached      │
    └─────────────────┴──────────────────────────────────────────────────┘

    Args:
        model_type: The ``model_type`` field from the Vertex prediction payload
                    (e.g. ``"similar_offer"``, ``"tops"``, ``"recommendation"``).

    Returns:
        bool: True when the retrieval cache should be consulted/written for this model_type.
    """
    model_type_to_flag: dict[str, bool] = {
        "similar_offer": settings.RETRIEVAL_CACHE_SIMILAR_OFFER_ENABLED,
        "tops": settings.RETRIEVAL_CACHE_PLAYLIST_TOPS_ENABLED,
        "recommendation": settings.RETRIEVAL_CACHE_PLAYLIST_PERSONALIZED_ENABLED,
    }
    return model_type_to_flag.get(model_type, False)


async def _reconstruct_vertex_result_from_cache(cached_predictions: list[dict]) -> VertexPredictionResult:
    """Reconstructs a VertexPredictionResult from a list of cached serialised RecommendableItem dicts."""
    predictions = [RecommendableItem.model_validate(item) for item in cached_predictions]
    return VertexPredictionResult(status="success", predictions=predictions)


async def fetch_retrieval_predictions(prediction_payload: dict[str, Any]) -> VertexPredictionResult:
    """
    Returns the retrieval predictions for the given payload, reading from the Redis cache
    when enabled and falling back to the coreservation Vertex endpoint on a miss.

    Cache eligibility is determined by the payload's ``model_type`` field via
    ``_is_retrieval_cache_enabled_for_model_type``. When the cache is disabled for this
    model_type, the function behaves identically to a direct call to
    ``fetch_retrieval_predictions_from_vertex``.

    On a cache miss, the fresh Vertex result is stored in Redis (when cache is enabled and
    the result is non-empty), so subsequent identical calls within the same cache window
    benefit from a cache hit.

    Cache flow:
    ┌──────────────────────────────────────────────────────────────────────┐
    │  cache enabled?  ──NO──► fetch from Vertex ──► return result        │
    │       │                                                              │
    │      YES                                                             │
    │       │                                                              │
    │  Redis GET ──HIT──► reconstruct result ──► return result            │
    │       │                                                              │
    │      MISS                                                            │
    │       │                                                              │
    │  fetch from Vertex ──► store in Redis ──► return result             │
    └──────────────────────────────────────────────────────────────────────┘

    Args:
        prediction_payload: The raw Vertex prediction payload (built by the retrieval builders).

    Returns:
        VertexPredictionResult: Either the cached result or a freshly fetched one.
    """
    model_type = prediction_payload.get("model_type", "")

    if _is_retrieval_cache_enabled_for_model_type(model_type):
        cached_predictions = await redis_api.fetch_cached_retrieval_predictions(
            prediction_payload, namespace=RedisAPI.RETRIEVAL_NAMESPACE
        )
        if cached_predictions is not None:
            return await _reconstruct_vertex_result_from_cache(cached_predictions)

    result = await fetch_retrieval_predictions_from_vertex(prediction_payload)

    if _is_retrieval_cache_enabled_for_model_type(model_type) and result.status == "success" and result.predictions:
        serialized = [item.model_dump(mode="json") for item in result.predictions]
        await redis_api.store_retrieval_predictions(
            prediction_payload, serialized, namespace=RedisAPI.RETRIEVAL_NAMESPACE
        )

    return result


@log_execution_time
async def fetch_graph_retrieval_predictions(prediction_payload: dict[str, Any]) -> VertexPredictionResult:
    """
    Returns the retrieval predictions for the given payload, reading from the Redis cache
    when enabled and falling back to the graph Vertex endpoint on a miss.

    Identical in behaviour to ``fetch_retrieval_predictions`` but targets the graph Vertex
    endpoint. A distinct Redis namespace (``RedisAPI.RETRIEVAL_GRAPH_NAMESPACE``) is used
    to prevent collisions with coreservation cache entries that share the same model_type
    values.

    Cache flow:
    ┌──────────────────────────────────────────────────────────────────────┐
    │  cache enabled?  ──NO──► fetch from graph Vertex ──► return result  │
    │       │                                                              │
    │      YES                                                             │
    │       │                                                              │
    │  Redis GET ──HIT──► reconstruct result ──► return result            │
    │       │                                                              │
    │      MISS                                                            │
    │       │                                                              │
    │  fetch from graph Vertex ──► store in Redis ──► return result       │
    └──────────────────────────────────────────────────────────────────────┘

    Args:
        prediction_payload: The raw Vertex prediction payload (built by the retrieval builders).

    Returns:
        VertexPredictionResult: Either the cached result or a freshly fetched one.
    """
    model_type = prediction_payload.get("model_type", "")

    if _is_retrieval_cache_enabled_for_model_type(model_type):
        cached_predictions = await redis_api.fetch_cached_retrieval_predictions(
            prediction_payload, namespace=RedisAPI.RETRIEVAL_GRAPH_NAMESPACE
        )
        if cached_predictions is not None:
            return await _reconstruct_vertex_result_from_cache(cached_predictions)

    result = await fetch_graph_predictions_from_vertex(prediction_payload)

    if _is_retrieval_cache_enabled_for_model_type(model_type) and result.status == "success" and result.predictions:
        serialized = [item.model_dump(mode="json") for item in result.predictions]
        await redis_api.store_retrieval_predictions(
            prediction_payload, serialized, namespace=RedisAPI.RETRIEVAL_GRAPH_NAMESPACE
        )

    return result


async def filter_out_already_booked_items(
    db: AsyncSession, candidate_items: list[RecommendableItem], user_id: str
) -> list[RecommendableItem]:
    """
    Removes items from the candidate list that the user has already booked or consumed.

    This function cross-references the proposed ML items with the 'NonRecommendableItems'
    table (which stores items the user has already interacted with, like past bookings).
    It guarantees that the user only sees fresh, unbooked recommendations.

    Args:
        db (AsyncSession): The asynchronous database session.
        candidate_items (list[RecommendableItem]): The raw candidate items proposed by Vertex AI.
        user_id (str): The unique identifier of the current user.

    Returns:
        list[RecommendableItem]: A filtered list of items containing only new, unseen recommendations.

    Example:
        Candidate items: [Item A, Item B, Item C]
        User previously booked: [Item B]
        Returns: [Item A, Item C]
    """
    if not candidate_items:
        return []

    already_booked_items_query = select(NonRecommendableItems.item_id).where(NonRecommendableItems.user_id == user_id)

    query_result = await db.execute(already_booked_items_query)
    already_booked_item_ids = set(query_result.scalars().all())

    unseen_candidate_items = [item for item in candidate_items if item.item_id not in already_booked_item_ids]

    logger.debug(
        "🚫 Booked items cross-referenced.",
        extra={
            "user_id": user_id,
            "already_booked_count": len(already_booked_item_ids),
            "candidates_in": len(candidate_items),
            "candidates_out": len(unseen_candidate_items),
        },
    )

    return unseen_candidate_items


async def _fetch_tops_offer_resolutions_from_cache(
    tops_item_ids: list[str],
    user_context: UserContext,
) -> tuple[dict[str, dict], list[str], str]:
    """
    Looks up pre-resolved tops offers from the Redis offer-resolution cache (single MGET round-trip).

    Args:
        tops_item_ids: IDs of "tops" items to look up in the cache. Must be non-empty.
        user_context: Standardized user context — must be geolocated when calling this function.

    Returns:
        A 3-tuple of:
        - cache_hits (dict[str, dict]): item_id → cached offer payload for items found in cache.
        - tops_cache_misses (list[str]): item IDs not found in cache, to be resolved via SQL.
        - h3_cell (str): The H3 cell used for cache key construction.
    """

    h3_cell = get_h3_index_from_coordinates(
        user_context.latitude,
        user_context.longitude,
        resolution=settings.OFFER_RESOLUTION_CACHE_H3_RESOLUTION,
    )
    assert h3_cell is not None, "h3_cell must not be None when user is geolocated"  # help ty
    cache_keys = [redis_api.build_offer_resolution_cache_key(h3_cell, iid) for iid in tops_item_ids]
    cached_values = await redis_api.mget_resolved_offers(cache_keys)

    cache_hits = {
        item_id: cached_value
        for item_id, cached_value in zip(tops_item_ids, cached_values, strict=True)
        if cached_value is not None
    }
    cache_hit_ids: set[str] = set(cache_hits)
    tops_cache_misses = [iid for iid in tops_item_ids if iid not in cache_hit_ids]

    return cache_hits, tops_cache_misses, h3_cell


async def _store_tops_offer_resolutions_in_cache(
    tops_cache_misses: list[str],
    db_rows: list,
    h3_cell: str,
) -> None:
    """
    Stores newly DB-resolved tops offer resolutions in the Redis cache (single MSET pipeline).

    Only items that were actually resolved (i.e. had at least one venue within the search radius)
    are written to cache. Unresolved items (no venue found) are intentionally not cached.

    Args:
        tops_cache_misses: Item IDs that were not found in cache and were resolved via SQL.
        db_rows: Raw results from the spatial DB query, as (db_offer, distance) tuples.
        h3_cell: The H3 cell identifier used as part of each cache key.
    """
    db_resolved_by_item_id = {db_offer.item_id: db_offer for db_offer, _ in db_rows}
    new_cache_entries: dict[str, dict] = {
        redis_api.build_offer_resolution_cache_key(h3_cell, item_id): {
            "offer_id": db_offer.offer_id,
            "venue_latitude": float(db_offer.venue_latitude) if db_offer.venue_latitude is not None else None,
            "venue_longitude": float(db_offer.venue_longitude) if db_offer.venue_longitude is not None else None,
            # Serialize as ISO 8601 strings for JSON-safe Redis storage
            "offer_creation_date": db_offer.offer_creation_date.isoformat() if db_offer.offer_creation_date else None,
            "stock_beginning_date": db_offer.stock_beginning_date.isoformat()
            if db_offer.stock_beginning_date
            else None,
        }
        for item_id in tops_cache_misses
        # Item was not resolved (e.g. no venue within radius) — do not cache absence.
        if (db_offer := db_resolved_by_item_id.get(item_id)) is not None
    }

    if new_cache_entries:
        ttl = RedisAPI.calculate_seconds_until_next_database_population_time()
        await redis_api.mset_resolved_offers(new_cache_entries, ttl)
        logger.debug(
            "💾 Newly resolved tops offers stored in cache.",
            extra={
                "stored_count": len(new_cache_entries),
                "not_resolved_count": len(tops_cache_misses) - len(new_cache_entries),
                "ttl_seconds": ttl,
                "h3_cell": h3_cell,
            },
        )


async def _resolve_multi_venue_items_with_cache(
    db: AsyncSession,
    multi_venue_item_ids: list[str],
    item_lookup_map: dict[str, RecommendableItem],
    user_context: UserContext,
) -> list[EnrichedRecommendableOffer]:
    """
    Resolves multi-venue physical items into their closest offers, using the offer-resolution
    cache to skip the spatial SQL query for "tops" items already resolved in the same H3 zone.

    Strategy:
    - "tops" items (most redundant in Vertex retrieval results) are checked in Redis first (MGET).
      Cache hits skip the SQL query entirely; their distance is recomputed via pure-Python Haversine.
    - Cache misses and non-tops items are resolved via a single batched spatial SQL query.
    - Newly DB-resolved tops items are written back to Redis in a single pipeline (MSET).

    Cached payload per item (minimal — only what cannot be derived from Vertex AI item data):
        offer_id, venue_latitude, venue_longitude, offer_creation_date, stock_beginning_date

    Args:
        db: The async database session.
        multi_venue_item_ids: IDs of items requiring SQL spatial resolution.
        item_lookup_map: Mapping of item_id → RecommendableItem (Vertex AI data).
        user_context: Standardized user context — must be geolocated when calling this function.

    Returns:
        list[EnrichedRecommendableOffer]: Resolved offers from both cache and DB, unsorted.
    """
    resolved_offers: list[EnrichedRecommendableOffer] = []

    # --- 1. Split tops vs non-tops ---
    # Only "tops" items are cached: they are the most stable and redundant across requests.
    tops_item_ids: list[str] = [
        iid for iid in multi_venue_item_ids if item_lookup_map[iid].item_origin == ItemOrigin.TOPS
    ]
    non_tops_item_ids: list[str] = [
        iid for iid in multi_venue_item_ids if item_lookup_map[iid].item_origin != ItemOrigin.TOPS
    ]

    # --- 2. Cache lookup for tops items (single MGET round-trip) ---
    cache_hits: dict[str, dict] = {}
    tops_cache_misses: list[str] = tops_item_ids  # default: all tops go to DB
    h3_cell: str | None = None

    if settings.OFFER_RESOLUTION_CACHE_ENABLED and tops_item_ids:
        cache_hits, tops_cache_misses, h3_cell = await _fetch_tops_offer_resolutions_from_cache(
            tops_item_ids, user_context
        )

    items_to_resolve_in_db: list[str] = tops_cache_misses + non_tops_item_ids

    logger.debug(
        "💾 Offer resolution cache lookup.",
        extra={
            "offer_resolution_cache_enabled": settings.OFFER_RESOLUTION_CACHE_ENABLED,
            "multi_venue_total": len(multi_venue_item_ids),
            "tops_items_total": len(tops_item_ids),
            "non_tops_items_total": len(non_tops_item_ids),
            "cache_hits_count": len(cache_hits),
            "cache_misses_count": len(tops_cache_misses),
            "items_sent_to_db": len(items_to_resolve_in_db),
            "db_calls_saved": len(cache_hits),
            "h3_cell": h3_cell,
            "h3_resolution": settings.OFFER_RESOLUTION_CACHE_H3_RESOLUTION
            if settings.OFFER_RESOLUTION_CACHE_ENABLED
            else None,
        },
    )

    # --- 3. Build enriched offers from cache hits (no SQL needed) ---
    cache_hits_skipped_too_far = 0
    for item_id, cached_offer in cache_hits.items():
        item_data = item_lookup_map[item_id]

        # Recompute exact distance from cached venue coordinates (fast, pure Python Haversine)
        distance = calculate_haversine_distance_in_meters(
            user_context.latitude,
            user_context.longitude,
            cached_offer["venue_latitude"],
            cached_offer["venue_longitude"],
        )

        # Guard: skip if the venue falls outside the search radius for this specific user position.
        # (Unlikely with H3 res-8 cells, but protects against zone boundary edge cases.)
        if distance is not None and distance > MAX_DISTANCE_METERS_FOR_OFFER_RETRIEVAL:
            cache_hits_skipped_too_far += 1
            continue

        # Deserialize offer-level dates stored in cache as ISO 8601 strings
        offer_creation_date = (
            datetime.fromisoformat(cached_offer["offer_creation_date"])
            if cached_offer.get("offer_creation_date")
            else None
        )
        stock_beginning_date = (
            datetime.fromisoformat(cached_offer["stock_beginning_date"])
            if cached_offer.get("stock_beginning_date")
            else None
        )

        resolved_offers.append(
            EnrichedRecommendableOffer(
                offer_id=cached_offer["offer_id"],
                item_id=item_id,
                offer_creation_date=offer_creation_date,
                stock_beginning_date=stock_beginning_date,
                is_geolocated=item_data.is_geolocated,
                venue_latitude=cached_offer["venue_latitude"],
                venue_longitude=cached_offer["venue_longitude"],
                offer_user_distance=distance,
                item_score=item_data.item_score,
                item_rank=item_data.item_rank,
                item_origin=item_data.item_origin,
                semantic_emb_mean=item_data.semantic_emb_mean,
                stock_price=item_data.stock_price,
                category=item_data.category,
                subcategory_id=item_data.subcategory_id,
                search_group_name=item_data.search_group_name,
                booking_number=item_data.booking_number,
                booking_number_last_7_days=item_data.booking_number_last_7_days,
                booking_number_last_14_days=item_data.booking_number_last_14_days,
                booking_number_last_28_days=item_data.booking_number_last_28_days,
            )
        )

    if cache_hits_skipped_too_far > 0:
        logger.debug(
            "⚠️ Cache hits skipped: resolved venue now outside search radius for current user position.",
            extra={"skipped_count": cache_hits_skipped_too_far},
        )

    # --- 4. DB resolution for cache misses + non-tops items ---
    db_rows = []
    if items_to_resolve_in_db:
        logger.debug(
            "🗺️ Resolving multi-venue items via spatial DB query.",
            extra={
                "multi_venue_item_count": len(items_to_resolve_in_db),
                "user_lat": user_context.latitude,
                "user_lng": user_context.longitude,
            },
        )
        db_rows = await find_closest_offers_with_h3_index(
            db, items_to_resolve_in_db, user_context, resolution=settings.GEOSPATIAL_RETRIEVAL_H3_RESOLUTION
        )

    # --- 5. Store newly DB-resolved tops items in cache (single MSET pipeline) ---
    if settings.OFFER_RESOLUTION_CACHE_ENABLED and tops_cache_misses and h3_cell and db_rows:
        await _store_tops_offer_resolutions_in_cache(tops_cache_misses, db_rows, h3_cell)

    # --- 6. Build enriched offers from DB rows ---
    for db_offer, distance in db_rows:
        item_data = item_lookup_map.get(db_offer.item_id)
        if not item_data:
            continue

        resolved_offers.append(
            EnrichedRecommendableOffer(
                offer_id=db_offer.offer_id,
                item_id=db_offer.item_id,
                offer_creation_date=db_offer.offer_creation_date,
                stock_beginning_date=db_offer.stock_beginning_date,
                is_geolocated=item_data.is_geolocated,
                venue_latitude=db_offer.venue_latitude,
                venue_longitude=db_offer.venue_longitude,
                offer_user_distance=float(distance) if distance is not None else None,
                item_score=item_data.item_score,
                item_rank=item_data.item_rank,
                item_origin=item_data.item_origin,
                semantic_emb_mean=item_data.semantic_emb_mean,
                stock_price=item_data.stock_price,
                category=item_data.category,
                subcategory_id=item_data.subcategory_id,
                search_group_name=item_data.search_group_name,
                booking_number=item_data.booking_number,
                booking_number_last_7_days=item_data.booking_number_last_7_days,
                booking_number_last_14_days=item_data.booking_number_last_14_days,
                booking_number_last_28_days=item_data.booking_number_last_28_days,
            )
        )

    logger.debug(
        "🗺️ Multi-venue items fully resolved.",
        extra={
            "multi_venue_requested": len(multi_venue_item_ids),
            "cache_hits_resolved": len(cache_hits) - cache_hits_skipped_too_far,
            "db_resolved_count": len(db_rows),
            "total_resolved": len(resolved_offers),
        },
    )

    return resolved_offers


async def resolve_closest_venues_from_items(
    db: AsyncSession, candidate_items: list[RecommendableItem], user_context: UserContext
) -> list[EnrichedRecommendableOffer]:
    """
    Transforms abstract ML 'Items' into physical or digital 'Offers', keeping only the closest one.

    This function acts as a smart spatial funnel. To optimize memory and performance,
    it splits candidates into two processing routes (Fast-Track vs Database) to avoid
    loading thousands of duplicate physical offers into RAM.

    Processing Flow:
    1. Routing: Segregates items into a Fast-Track bucket (digital/single venue) and a SQL bucket (multi-venue).
    2. Cache-assisted spatial resolution: delegates multi-venue items to
       _resolve_multi_venue_items_with_cache, which handles Redis cache lookup/write
       and falls back to a batched spatial SQL query for misses.
    3. Merge & Sort: Combines both buckets and sorts by ascending distance.

    Args:
        db (AsyncSession): The async database session.
        candidate_items (list[RecommendableItem]): Raw items returned by Vertex AI.
        user_context (UserContext): Standardized user context (geo, credit, etc.).

    Returns:
        list[EnrichedRecommendableOffer]: A clean list of fully enriched offers, sorted by distance.
    """
    if not candidate_items:
        return []

    # --- 1. FAST-TRACK & DB ROUTING ---
    fast_track_enriched_offers: list[EnrichedRecommendableOffer] = []
    multi_venue_item_ids: list[str] = []
    item_lookup_map: dict[str, RecommendableItem] = {}
    skipped_no_geo_context = 0
    skipped_too_far = 0

    for item in candidate_items:
        # Route A: Fast-Track (Digital or single-venue physical)
        if not item.is_geolocated or item.total_offers == 1:
            # Reject physical offers if user has no GPS context
            if item.is_geolocated and not user_context.is_geolocated:
                skipped_no_geo_context += 1
                continue

            calculated_distance = None
            if item.is_geolocated and user_context.is_geolocated:
                calculated_distance = calculate_haversine_distance_in_meters(
                    user_context.latitude,
                    user_context.longitude,
                    item.example_venue_latitude,
                    item.example_venue_longitude,
                )

                # Reject if beyond default max radius (100km)
                if calculated_distance is not None and calculated_distance > DEFAULT_MAX_DISTANCE_IN_METERS:
                    skipped_too_far += 1
                    continue

            fast_track_enriched_offers.append(
                EnrichedRecommendableOffer(
                    offer_id=item.example_offer_id,
                    item_id=item.item_id,
                    offer_creation_date=item.offer_creation_date,
                    stock_beginning_date=item.stock_beginning_date,
                    is_geolocated=item.is_geolocated,
                    venue_latitude=item.example_venue_latitude,
                    venue_longitude=item.example_venue_longitude,
                    offer_user_distance=calculated_distance,
                    item_score=item.item_score,
                    item_rank=item.item_rank,
                    item_origin=item.item_origin,
                    semantic_emb_mean=item.semantic_emb_mean,
                    stock_price=item.stock_price,
                    category=item.category,
                    subcategory_id=item.subcategory_id,
                    search_group_name=item.search_group_name,
                    booking_number=item.booking_number,
                    booking_number_last_7_days=item.booking_number_last_7_days,
                    booking_number_last_14_days=item.booking_number_last_14_days,
                    booking_number_last_28_days=item.booking_number_last_28_days,
                )
            )

        # Route B: Cache-assisted spatial resolution (Multi-venue physical items)
        elif user_context.is_geolocated:
            multi_venue_item_ids.append(item.item_id)
            item_lookup_map[item.item_id] = item

    logger.debug(
        "🔀 Venue resolution routing.",
        extra={
            "candidates_in": len(candidate_items),
            "fast_track_count": len(fast_track_enriched_offers),
            "multi_venue_db_count": len(multi_venue_item_ids),
            "skipped_no_geo_context": skipped_no_geo_context,
            "skipped_too_far": skipped_too_far,
        },
    )

    # --- 2. CACHE-ASSISTED SPATIAL RESOLUTION ---
    database_resolved_enriched_offers: list[EnrichedRecommendableOffer] = []

    if multi_venue_item_ids:
        if not user_context.is_geolocated or user_context.latitude is None or user_context.longitude is None:
            logger.debug(
                "⏭️ Skipping spatial DB resolution: user has no GPS context.",
                extra={
                    "multi_venue_item_count": len(multi_venue_item_ids),
                    "is_geolocated": user_context.is_geolocated,
                },
            )
        else:
            database_resolved_enriched_offers = await _resolve_multi_venue_items_with_cache(
                db=db,
                multi_venue_item_ids=multi_venue_item_ids,
                item_lookup_map=item_lookup_map,
                user_context=user_context,
            )

    # --- 3. MERGE & SORT ---
    final_resolved_offers = fast_track_enriched_offers + database_resolved_enriched_offers

    final_resolved_offers.sort(
        key=lambda x: x.offer_user_distance if x.offer_user_distance is not None else float("inf")
    )

    return final_resolved_offers
