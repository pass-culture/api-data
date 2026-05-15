import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from connectors import retrieval_api_client
from connectors.vertex_api import VertexPredictionResult
from core.geo import find_closest_offers_with_h3_index
from core.user_context import UserContext
from models.items import NonRecommendableItems
from schemas.categories import CategoryEnum
from schemas.categories import SearchGroupNameEnum
from schemas.categories import SubcategoryEnum
from schemas.enriched_offer import EnrichedRecommendableOffer
from schemas.playlist_recommendation import PlaylistRequestParams
from schemas.vertex_prediction_item import RecommendableItem
from utils.benchmark import log_execution_time


DEFAULT_MAX_DISTANCE_IN_METERS = 100_000
EARTH_RADIUS_METERS = 6371000
VERTEX_API_CANDIDATE_ITEMS_FETCH_SIZE_LIMIT = 600

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
    effective_price_max = round(user_context.remaining_credit)
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
        "gtl_ids": "gtl_id",
        "gtl_l1": "gtl_l1",
        "gtl_l2": "gtl_l2",
        "gtl_l3": "gtl_l3",
        "gtl_l4": "gtl_l4",
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
        "size": VERTEX_API_CANDIDATE_ITEMS_FETCH_SIZE_LIMIT,
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
        "size": VERTEX_API_CANDIDATE_ITEMS_FETCH_SIZE_LIMIT,
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


def calculate_haversine_distance_in_meters(
    user_lat: float | None, user_lon: float | None, offer_lat: float | None, offer_lon: float | None
) -> float | None:
    """
    Calculates the great-circle distance between two GPS points on Earth.

    Args:
        user_lat (float | None): User's latitude in decimal degrees.
        user_lon (float | None): User's longitude in decimal degrees.
        offer_lat (float | None): Offer venue's latitude in decimal degrees.
        offer_lon (float | None): Offer venue's longitude in decimal degrees.

    Returns:
        float | None: The distance in meters, or None if any coordinate is missing.
    """
    if user_lat is None or user_lon is None or offer_lat is None or offer_lon is None:
        return None

    user_lat_rad = math.radians(user_lat)
    offer_lat_rad = math.radians(offer_lat)

    delta_lat_rad = math.radians(offer_lat - user_lat)
    delta_lon_rad = math.radians(offer_lon - user_lon)

    haversine_a = (
        math.sin(delta_lat_rad / 2) ** 2
        + math.cos(user_lat_rad) * math.cos(offer_lat_rad) * math.sin(delta_lon_rad / 2) ** 2
    )

    distance = 2 * EARTH_RADIUS_METERS * math.atan2(math.sqrt(haversine_a), math.sqrt(1 - haversine_a))

    return distance


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

    return unseen_candidate_items


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
    2. Spatial Resolution: Uses PostGIS ROW_NUMBER() over ST_Distance
        to find the single closest venue for each multi-venue item.
    3. Merge: Combines both buckets into EnrichedRecommendableOffer objects and sorts by distance.

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

    for item in candidate_items:
        # Route A: Fast-Track (Digital or single-venue physical)
        if not item.is_geolocated or item.total_offers == 1:
            # Reject physical offers if user has no GPS context
            if item.is_geolocated and not user_context.is_geolocated:
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
                    continue

            # Instantiate the clean DTO directly from the ML Item
            enriched_offer = EnrichedRecommendableOffer(
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
            fast_track_enriched_offers.append(enriched_offer)

        # Route B: SQL Database Resolution (Multi-venue physical items)
        elif user_context.is_geolocated:
            multi_venue_item_ids.append(item.item_id)
            item_lookup_map[item.item_id] = item

    # --- 2. DATABASE SPATIAL RESOLUTION ---
    database_resolved_enriched_offers: list[EnrichedRecommendableOffer] = []

    if multi_venue_item_ids:
        db_rows = await find_closest_offers_with_h3_index(
            db, multi_venue_item_ids, user_context, resolution=settings.GEOSPATIAL_RETRIEVAL_H3_RESOLUTION
        )

        # Map SQL results back to Vertex ML data
        for db_offer, distance in db_rows:
            item_data = item_lookup_map.get(db_offer.item_id)
            if not item_data:
                continue

            enriched_offer = EnrichedRecommendableOffer(
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
            database_resolved_enriched_offers.append(enriched_offer)

    # --- 3. MERGE & SORT ---
    final_resolved_offers = fast_track_enriched_offers + database_resolved_enriched_offers

    final_resolved_offers.sort(
        key=lambda x: x.offer_user_distance if x.offer_user_distance is not None else float("inf")
    )

    return final_resolved_offers
