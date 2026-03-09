import math
from typing import Any

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from config import settings
from core.user_context import UserContext
from models.items import NonRecommendableItems
from models.offer import RecommendableOffers
from schemas.playlist_recommendation import PlaylistRequestParams
from schemas.vertex_prediction_item import RecommendableItem
from services.vertex import VertexPredictionResult
from services.vertex import VertexService


DEFAULT_MAX_DISTANCE_IN_METERS = 100_000
EARTH_RADIUS_METERS = 6371000
FINAL_DIVERSIFIED_PLAYLIST_MAXIMUM_SIZE = 60
VERTEX_API_CANDIDATE_ITEMS_FETCH_SIZE_LIMIT = 150


def _build_vertex_search_filters(user_context: UserContext, params: PlaylistRequestParams) -> dict[str, Any]:
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
    filters = {}
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

    # Assemble final query payload
    if and_conditions:
        for condition in and_conditions:
            filters.update(condition)

    return {"$and": filters}


async def fetch_candidate_items_from_vertex(
    user_context: UserContext, params: PlaylistRequestParams, call_id: str
) -> VertexPredictionResult:
    """
    Calls the Vertex AI matching engine to retrieve a raw list of candidate Item IDs.

    Depending on the user profile (Cold Start vs Active), it switches between
    a popularity-based model ('tops') or a personalized collaborative filtering model.

    Args:
        user_context (UserContext): The enriched user profile determining the model to use.
        params (PlaylistRequestParams): Recommendation rules requested by the client.
        call_id (str): A unique execution trace ID for logging purposes.

    Returns:
        VertexPredictionResult: A structured payload containing the raw predicted items.
    """
    vertex_service = VertexService(endpoint_name=settings.VERTEX_RETRIEVAL_ENDPOINT_NAME)
    search_filters = _build_vertex_search_filters(user_context, params)

    # Base payload structure for the Vertex AI endpoint
    prediction_instance = {
        "call_id": call_id,
        "user_id": user_context.user_id,
        "params": search_filters,
        # TODO: Remove this field or rename it in the Vertex API.
        #  It is currently required, but having a hardcoded "debug" flag in production is confusing.
        "debug": 1,
        "prefilter": 1,
        "size": VERTEX_API_CANDIDATE_ITEMS_FETCH_SIZE_LIMIT,
    }

    # Route to the appropriate model logic based on user maturity
    if user_context.is_cold_start:
        prediction_instance["model_type"] = "tops"
        # TODO find out which vector column(s) fit best for cold start scenario.
        prediction_instance["vector_column_name"] = (
            "booking_number_desc"  # "booking_creation_trend_desc", "booking_release_trend_desc"
        )
        prediction_instance["re_rank"] = 0
    else:
        prediction_instance["model_type"] = "recommendation"

    prediction_result = await vertex_service.fetch_retrieval_predictions(feature_payloads=[prediction_instance])

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


async def resolve_and_filter_closest_venues(  # noqa: PLR0915
    db: AsyncSession, candidate_items: list[RecommendableItem], user_context: UserContext
) -> list[RecommendableOffers]:
    """
    Transforms abstract ML 'Items' into physical or digital 'Offers', keeping only the closest one.

    This function acts as a smart spatial funnel. To optimize memory and performance,
    it splits candidates into two processing routes (Fast-Track vs Database) to avoid
    loading thousands of duplicate physical offers into RAM.

    Processing Flow:
    1. Blacklist Filtering: Removes items the user has already seen or booked.
    2. Routing: Segregates items into a Fast-Track bucket (digital/single venue) and a SQL bucket (multi-venue).
    3. Spatial Resolution: Uses PostGIS ROW_NUMBER() over ST_Distance
        to find the single closest venue for each multi-venue item.
    4. Merge: Combines both buckets and sorts the final list by distance.

    Args:
        db (AsyncSession): The async database session.
        candidate_items (list[RecommendableItem]): Raw items returned by Vertex AI.
        user_context (UserContext): Standardized user context (geo, credit, etc.).

    Returns:
        list[RecommendableOffers]: A list of fully enriched RecommendableOffers, sorted by distance.
    """

    if not candidate_items:
        return []

    # --- 1. BLACKLIST FILTERING ---
    blacklisted_items_query = select(NonRecommendableItems.item_id).where(
        NonRecommendableItems.user_id == user_context.user_id
    )
    blacklist_result = await db.execute(blacklisted_items_query)
    blacklisted_ids = set(blacklist_result.scalars().all())

    valid_candidates = [item for item in candidate_items if item.item_id not in blacklisted_ids]

    # --- 2. FAST-TRACK & DB ROUTING ---
    fast_track_offers = []
    multi_venue_item_ids = []
    item_lookup_map: dict[str, RecommendableItem] = {}

    for item in valid_candidates:
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

            # Manually build the offer object to save DB calls
            offer = RecommendableOffers(
                offer_id=item.example_offer_id,
                item_id=item.item_id,
                venue_latitude=item.example_venue_latitude,
                venue_longitude=item.example_venue_longitude,
                offer_creation_date=item.offer_creation_date,
                stock_beginning_date=item.stock_beginning_date,
            )

            # Dynamic enrichment from ML payload
            offer.is_geolocated = item.is_geolocated
            offer.offer_user_distance = calculated_distance
            offer.stock_price = item.stock_price
            offer.category = item.category
            offer.subcategory_id = item.subcategory_id
            offer.search_group_name = item.search_group_name
            offer.booking_number = item.booking_number
            offer.booking_number_last_7_days = item.booking_number_last_7_days
            offer.booking_number_last_14_days = item.booking_number_last_14_days
            offer.booking_number_last_28_days = item.booking_number_last_28_days
            offer.item_score = item.item_score
            offer.item_rank = item.item_rank
            offer.item_origin = item.item_origin
            offer.semantic_emb_mean = item.semantic_emb_mean

            fast_track_offers.append(offer)

        # Route B: SQL Database Resolution (Multi-venue physical items)
        elif user_context.is_geolocated:
            multi_venue_item_ids.append(item.item_id)
            item_lookup_map[item.item_id] = item

    # --- 3. DATABASE SPATIAL RESOLUTION ---
    database_resolved_offers = []

    if multi_venue_item_ids:
        # Define the user's geographical point for PostGIS calculations
        user_geography_point = func.ST_GeographyFromText(f"POINT({user_context.longitude} {user_context.latitude})")
        distance_expression = func.ST_Distance(user_geography_point, RecommendableOffers.venue_geo)

        # Window function: partition by item_id and rank offers by ascending distance
        distance_rank = (
            func.row_number()
            .over(partition_by=RecommendableOffers.item_id, order_by=distance_expression.asc())
            .label("distance_rank")
        )

        calc_distance = distance_expression.label("calc_distance")

        # Subquery fetching all venues for the targeted physical items
        venues_subquery = (
            select(RecommendableOffers, calc_distance, distance_rank)
            .where(RecommendableOffers.item_id.in_(multi_venue_item_ids))
            .subquery()
        )

        aliased_offer = aliased(RecommendableOffers, venues_subquery)
        max_allowed_distance = func.coalesce(aliased_offer.default_max_distance, DEFAULT_MAX_DISTANCE_IN_METERS)

        # Fetch only the closest venue (distance_rank == 1) within the allowed radius
        closest_venues_query = select(aliased_offer, venues_subquery.c.calc_distance).where(
            (venues_subquery.c.distance_rank == 1) & (venues_subquery.c.calc_distance <= max_allowed_distance)
        )

        db_result = await db.execute(closest_venues_query)

        # Map SQL results back to Vertex ML data
        for offer, distance in db_result.all():
            item_data = item_lookup_map.get(offer.item_id)
            if not item_data:
                continue

            offer.offer_user_distance = float(distance) if distance is not None else None
            offer.is_geolocated = item_data.is_geolocated
            offer.stock_price = item_data.stock_price
            offer.category = item_data.category
            offer.subcategory_id = item_data.subcategory_id
            offer.search_group_name = item_data.search_group_name
            offer.booking_number = item_data.booking_number
            offer.booking_number_last_7_days = item_data.booking_number_last_7_days
            offer.booking_number_last_14_days = item_data.booking_number_last_14_days
            offer.booking_number_last_28_days = item_data.booking_number_last_28_days
            offer.item_score = item_data.item_score
            offer.item_rank = item_data.item_rank
            offer.item_origin = item_data.item_origin
            offer.semantic_emb_mean = item_data.semantic_emb_mean

            database_resolved_offers.append(offer)

    # --- 4. MERGE & SORT ---
    final_resolved_offers = fast_track_offers + database_resolved_offers

    # Sort closest first (digital items with a distance of None fallback to infinity and go to the end)
    final_resolved_offers.sort(
        key=lambda x: x.offer_user_distance if x.offer_user_distance is not None else float("inf")
    )

    return final_resolved_offers
