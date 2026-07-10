import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from connectors import graph_api_client
from connectors import retrieval_api_client
from connectors.vertex_api import VertexPredictionResult
from core.user_context import UserContext
from models.items import NonRecommendableItems
from schemas.categories import CategoryEnum
from schemas.categories import SearchGroupNameEnum
from schemas.categories import SubcategoryEnum
from schemas.playlist_recommendation import PlaylistRequestParams
from schemas.vertex_prediction_item import RecommendableItem
from services.logger import logger
from utils.benchmark import log_execution_time


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
        *[fetch_retrieval_predictions_from_vertex(payload) for payload in retrieval_payloads]
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
