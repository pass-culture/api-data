from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.iris import IrisFrance


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
