"""
Refactored user CRUD operations using the new service pattern

This replaces the original UserContextDB class with a much cleaner interface
"""

from typing import Optional

from huggy.schemas.user import UserContext, UserProfileDB
from huggy.services.container import get_services


async def get_user_context_refactored(
    user_id: str, latitude: float, longitude: float
) -> UserContext:
    """
    Get user context with location and profile data

    Compare this simple function to the original 97-line UserContextDB class!
    """
    async with get_services() as services:
        user_service = services.get_user_service()
        return await user_service.get_user_context(user_id, latitude, longitude)


async def get_user_profile_refactored(user_id: str) -> Optional[UserProfileDB]:
    """Get detailed user profile"""
    async with get_services() as services:
        user_service = services.get_user_service()
        return await user_service.get_user_profile(user_id)


async def check_user_exists(user_id: str) -> bool:
    """Check if user exists in the system"""
    async with get_services() as services:
        user_service = services.get_user_service()
        return await user_service.user_exists(user_id)


async def get_user_deposit_info(user_id: str) -> Optional[dict]:
    """Get user's deposit information"""
    async with get_services() as services:
        user_service = services.get_user_service()
        return await user_service.get_user_deposit_info(user_id)


async def get_user_activity_stats(user_id: str) -> Optional[dict]:
    """Get user's activity statistics"""
    async with get_services() as services:
        user_service = services.get_user_service()
        return await user_service.get_user_activity_stats(user_id)


# Example of how to use multiple services together
async def get_comprehensive_user_data(
    user_id: str, latitude: float, longitude: float
) -> dict:
    """
    Get comprehensive user data using multiple services
    Demonstrates how easy it is to compose functionality
    """
    async with get_services() as services:
        user_service = services.get_user_service()
        iris_service = services.get_iris_service()

        # Get user context
        user_context = await user_service.get_user_context(user_id, latitude, longitude)

        # Get additional location info
        iris_info = None
        if user_context.iris_id:
            iris_info = await iris_service.get_iris_info(user_context.iris_id)

        # Get activity stats
        activity_stats = await user_service.get_user_activity_stats(user_id)

        # Get deposit info
        deposit_info = await user_service.get_user_deposit_info(user_id)

        return {
            "user_context": user_context,
            "iris_info": iris_info,
            "activity_stats": activity_stats,
            "deposit_info": deposit_info,
        }
