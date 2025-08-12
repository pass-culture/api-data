"""
Refactored non-recommendable offer CRUD operations using the new service pattern

This replaces the original get_non_recommendable_items function with a cleaner interface
"""

from huggy.schemas.user import UserContext
from huggy.services.container import get_services


async def get_non_recommendable_items_refactored(user: UserContext) -> list[str]:
    """
    Get list of item IDs that should not be recommended to the user

    Replaces the original get_non_recommendable_items function
    """
    async with get_services() as services:
        non_rec_service = services.get_non_recommendable_offer_service()
        return await non_rec_service.get_non_recommendable_items(user)


async def is_item_non_recommendable(user: UserContext, item_id: str) -> bool:
    """
    Check if a specific item is non-recommendable for the user
    """
    async with get_services() as services:
        non_rec_service = services.get_non_recommendable_offer_service()
        return await non_rec_service.is_item_non_recommendable(user, item_id)


async def filter_recommendable_items(
    user: UserContext, item_ids: list[str]
) -> list[str]:
    """
    Filter out non-recommendable items from a list
    """
    async with get_services() as services:
        non_rec_service = services.get_non_recommendable_offer_service()
        return await non_rec_service.filter_recommendable_items(user, item_ids)


async def get_non_recommendable_count(user: UserContext) -> int:
    """
    Get the count of non-recommendable items for a user
    """
    async with get_services() as services:
        non_rec_service = services.get_non_recommendable_offer_service()
        return await non_rec_service.get_non_recommendable_count(user)


async def bulk_check_non_recommendable(
    user: UserContext, item_ids: list[str]
) -> dict[str, bool]:
    """
    Efficiently check multiple items for non-recommendable status
    """
    async with get_services() as services:
        non_rec_service = services.get_non_recommendable_offer_service()
        return await non_rec_service.bulk_check_non_recommendable(user, item_ids)


# Example of a more complex operation
async def get_filtered_recommendations(
    user: UserContext, candidate_items: list[str], limit: int = 50
) -> dict:
    """
    Get filtered recommendations with statistics about filtering
    """
    async with get_services() as services:
        non_rec_service = services.get_non_recommendable_offer_service()

        # Get non-recommendable items
        non_recommendable = await non_rec_service.get_non_recommendable_items(user)

        # Filter candidates
        filtered_items = await non_rec_service.filter_recommendable_items(
            user, candidate_items
        )

        # Apply limit
        final_recommendations = filtered_items[:limit]

        return {
            "recommendations": final_recommendations,
            "total_candidates": len(candidate_items),
            "after_filtering": len(filtered_items),
            "final_count": len(final_recommendations),
            "non_recommendable_count": len(non_recommendable),
            "filtered_out": len(candidate_items) - len(filtered_items),
        }
