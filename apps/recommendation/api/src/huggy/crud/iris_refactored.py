"""
Refactored IRIS CRUD operations using the new service pattern

This replaces the original Iris class with cleaner, more focused functions
"""

from typing import Optional

from huggy.services.container import get_services


async def get_iris_from_coordinates_refactored(
    latitude: Optional[float], longitude: Optional[float]
) -> Optional[str]:
    """
    Get IRIS ID from geographical coordinates

    Replaces the original Iris.get_iris_from_coordinates method
    """
    async with get_services() as services:
        iris_service = services.get_iris_service()
        return await iris_service.get_iris_from_coordinates(latitude, longitude)


async def get_iris_info(iris_id: str) -> Optional[dict]:
    """
    Get detailed information about an IRIS region
    """
    async with get_services() as services:
        iris_service = services.get_iris_service()
        return await iris_service.get_iris_info(iris_id)


async def find_nearby_iris(
    latitude: float, longitude: float, radius_km: float = 5.0
) -> list[str]:
    """
    Find all IRIS regions within a given radius of coordinates
    """
    async with get_services() as services:
        iris_service = services.get_iris_service()
        return await iris_service.find_nearby_iris(latitude, longitude, radius_km)


async def is_point_in_france(latitude: float, longitude: float) -> bool:
    """
    Check if coordinates are within France using IRIS data
    """
    async with get_services() as services:
        iris_service = services.get_iris_service()
        return await iris_service.is_point_in_france(latitude, longitude)


# Example of a more complex operation that might be useful
async def get_location_context(latitude: float, longitude: float) -> dict:
    """
    Get comprehensive location context including IRIS and nearby regions
    """
    async with get_services() as services:
        iris_service = services.get_iris_service()

        # Get current IRIS
        current_iris = await iris_service.get_iris_from_coordinates(latitude, longitude)

        # Get nearby IRIS regions
        nearby_iris = await iris_service.find_nearby_iris(latitude, longitude, 5.0)

        # Get detailed info about current IRIS
        iris_info = None
        if current_iris:
            iris_info = await iris_service.get_iris_info(current_iris)

        return {
            "current_iris": current_iris,
            "iris_info": iris_info,
            "nearby_iris": nearby_iris,
            "is_in_france": current_iris is not None,
        }
