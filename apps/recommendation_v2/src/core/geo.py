from typing import TYPE_CHECKING

import h3
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from models.iris import IrisFrance
from models.offer import RecommendableOffers
from models.venue import Venue
from services.h3 import calculate_h3_k_rings_to_cover_search_radius
from services.h3 import get_h3_index_from_coordinates
from utils.benchmark import log_execution_time


if TYPE_CHECKING:
    from core.user_context import UserContext

H3_SEARCH_RADIUS_IN_KM = 50.0
MAX_DISTANCE_METERS_FOR_OFFER_RETRIEVAL = H3_SEARCH_RADIUS_IN_KM * 1000.0


async def get_iris_id_from_coordinates(db: AsyncSession, latitude: float | None, longitude: float | None) -> str | None:
    """
    Finds the ID of the French IRIS (geographical polygon) that contains the user's GPS coordinates.

    IRIS (Îlots Regroupés pour l'Information Statistique) is a French geographical
    division used for statistical purposes. This function performs a spatial query
    using PostGIS to determine which specific polygon envelops the given point.

    Args:
        db (AsyncSession): The active asynchronous database session.
        latitude (float | None): The user's latitude in decimal degrees.
        longitude (float | None): The user's longitude in decimal degrees.

    Returns:
        str | None: The ID of the matching IRIS, or None if the coordinates are missing
                    or if the point falls outside of the known French territories.
    """

    # --- 1. Validate Input ---
    if latitude is None or longitude is None:
        return None

    # --- 2. Construct Spatial Point ---
    # WARNING: PostGIS ST_MakePoint requires coordinates in (Longitude, Latitude) order (X, Y).
    user_location_point = func.ST_MakePoint(longitude, latitude)

    # --- 3. Execute Spatial Intersection Query ---
    # ST_Contains checks if the polygon ('shape') completely envelops the 'point'
    intersecting_iris_query = select(IrisFrance.id).where(func.ST_Contains(IrisFrance.shape, user_location_point))

    result = await db.execute(intersecting_iris_query)
    iris_db_id = result.scalars().first()

    return iris_db_id


def build_haversine_distance_expression(latitude: float, longitude: float, venue_model: type[Venue]) -> ColumnElement:
    """
    Constructs a SQL expression to calculate the Haversine distance between a point and a venue.

    This function generates a SQLAlchemy expression that computes the great-circle distance
    in meters between a fixed point (latitude, longitude) and the coordinates stored
    in the venue table.

    Args:
        latitude (float): Latitude of the reference point in decimal degrees.
        longitude (float): Longitude of the reference point in decimal degrees.
        venue_model (Type): The SQLAlchemy model class representing the venue
                            (must have 'latitude' and 'longitude' columns).

    Returns:
        ColumnElement: A SQLAlchemy expression evaluating to the distance in meters.
    """
    earth_radius_meters = 6371000.0

    # Convert degrees to radians
    lat_rad = func.radians(latitude)
    lng_rad = func.radians(longitude)
    venue_lat_rad = func.radians(venue_model.latitude)
    venue_lng_rad = func.radians(venue_model.longitude)

    # Haversine formula
    # dist = R * acos( sin(lat1)*sin(lat2) + cos(lat1)*cos(lat2)*cos(lon2-lon1) )
    # Note: func.least(1.0, ...) protects against floating point errors > 1.0
    distance_expression = earth_radius_meters * func.acos(
        func.least(
            1.0,
            func.sin(lat_rad) * func.sin(venue_lat_rad)
            + func.cos(lat_rad) * func.cos(venue_lat_rad) * func.cos(venue_lng_rad - lng_rad),
        )
    )

    return distance_expression


@log_execution_time
async def find_closest_offers_with_h3_index(
    db: AsyncSession,
    item_ids: list[str],
    user_context: "UserContext",
    *,
    resolution: int,
):
    """
    Retrieves the closest offer for each item using H3 geospatial indexing.

    This method optimizes spatial queries by filtering venues within a specific
    H3 grid area around the user ('candidate cells'). It ensures that for each item,
    only the single closest venue offering that item is returned.

    Process:
    1. Determine the H3 cells covering a ~50km radius around the user.
    2. Filter venues located within these H3 cells using the indexed column.
    3. Calculate exact Haversine distance for venues in the candidate cells.
    4. Select the nearest offer for each item using DISTINCT ON.

    Args:
        db (AsyncSession): The active database session.
        item_ids (list[str]): List of Item IDs to find offers for.
        user_context (UserContext): User's context containing GPS coordinates.
        resolution (int): H3 resolution to use for grid filtering.

    Returns:
        list[Row]: A list of rows containing (RecommendableOffers, calc_distance).
    """
    if (
        not user_context.is_geolocated or user_context.latitude is None or user_context.longitude is None
    ):  # pragma: no cover
        return []

    user_lat: float = user_context.latitude
    user_lng: float = user_context.longitude

    # Identify the H3 cell containing the user
    user_h3_cell = get_h3_index_from_coordinates(user_lat, user_lng, resolution=resolution)

    # Estimate the number of H3 rings needed to cover the search radius (50km)
    k_rings = calculate_h3_k_rings_to_cover_search_radius(
        search_radius_in_km=H3_SEARCH_RADIUS_IN_KM, resolution=resolution
    )

    # Get all cells within 'rings_count' distance (filled disk)
    candidate_h3_cells = h3.grid_disk(user_h3_cell, k=k_rings)

    # Build SQL components
    distance_expr = build_haversine_distance_expression(user_lat, user_lng, Venue).label("calc_distance")
    h3_index_column = getattr(Venue, f"h3_res{resolution}")

    # Construct the query
    stmt = (
        select(RecommendableOffers, distance_expr)
        .join(Venue, RecommendableOffers.venue_id == Venue.venue_id)
        .where(
            RecommendableOffers.item_id.in_(item_ids),
            h3_index_column.in_(candidate_h3_cells),
            distance_expr <= MAX_DISTANCE_METERS_FOR_OFFER_RETRIEVAL,
        )
        # Keep only one offer per item (the closest one)
        .distinct(RecommendableOffers.item_id)
        .order_by(
            RecommendableOffers.item_id,
            distance_expr.asc(),
        )
    )

    result = await db.execute(stmt)

    return result.all()
