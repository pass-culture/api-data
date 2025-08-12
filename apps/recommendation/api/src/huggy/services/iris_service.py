from typing import Optional

from geoalchemy2.elements import WKTElement
from huggy.database.repository import MaterializedViewRepository
from huggy.models.iris_france import (
    IrisFrance,
    IrisFranceMv,
    IrisFranceMvOld,
    IrisFranceMvTmp,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class IrisService:
    """Service for handling IRIS (geographic regions) operations"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = MaterializedViewRepository(
            session,
            IrisFrance,
            fallback_tables=[IrisFranceMv, IrisFranceMvOld, IrisFranceMvTmp],
        )

    async def get_iris_from_coordinates(
        self, latitude: Optional[float], longitude: Optional[float]
    ) -> Optional[str]:
        """
        Get IRIS ID from geographical coordinates using PostGIS spatial queries
        """
        if latitude is None or longitude is None:
            return None

        try:
            iris_table = await self.repository.get_available_model()

            # Create PostGIS point from coordinates
            point = WKTElement(f"POINT({longitude} {latitude})", srid=0)

            # Query to find which IRIS polygon contains this point
            query = select(iris_table.id.label("id")).where(
                func.ST_Contains(iris_table.shape, point)
            )

            result = await self.session.execute(query)
            iris_id = result.scalar_one_or_none()

            return str(iris_id) if iris_id is not None else None

        except Exception as exc:
            from huggy.utils.exception import log_error

            log_error(exc, message="Exception error on get_iris_from_coordinates")
            return None

    async def get_iris_info(self, iris_id: str) -> Optional[dict]:
        """Get detailed information about an IRIS region"""
        try:
            iris_table = await self.repository.get_available_model()

            query = select(iris_table).where(iris_table.id == iris_id)
            result = await self.session.execute(query)
            iris_data = result.fetchone()

            if iris_data:
                return {
                    "id": iris_data.id,
                    # Add other IRIS fields as needed
                    # "name": iris_data.name,
                    # "city": iris_data.city,
                    # etc.
                }

        except Exception as exc:
            from huggy.utils.exception import log_error

            log_error(exc, message="Exception error on get_iris_info")

        return None

    async def find_nearby_iris(
        self, latitude: float, longitude: float, radius_km: float = 5.0
    ) -> list[str]:
        """Find all IRIS regions within a given radius of coordinates"""
        try:
            iris_table = await self.repository.get_available_model()

            # Create center point
            center_point = WKTElement(f"POINT({longitude} {latitude})", srid=4326)

            # Query for IRIS regions within radius
            query = select(iris_table.id).where(
                func.ST_DWithin(
                    iris_table.shape,
                    center_point,
                    radius_km * 1000,  # Convert km to meters
                )
            )

            result = await self.session.execute(query)
            iris_ids = [str(row[0]) for row in result.fetchall()]

            return iris_ids

        except Exception as exc:
            from huggy.utils.exception import log_error

            log_error(exc, message="Exception error on find_nearby_iris")
            return []

    async def is_point_in_france(self, latitude: float, longitude: float) -> bool:
        """Check if coordinates are within France using IRIS data"""
        iris_id = await self.get_iris_from_coordinates(latitude, longitude)
        return iris_id is not None
