"""
Refactored offer CRUD operations using the new service pattern

This replaces the original Offer class with cleaner, more focused functions
"""

from typing import Optional

from huggy.schemas.offer import Offer
from huggy.services.container import get_services


async def parse_offer_list_refactored(offer_ids: list[str]) -> list[Offer]:
    """
    Parse a list of offer IDs into full Offer objects

    Much cleaner than the original static method approach
    """
    async with get_services() as services:
        offer_service = services.get_offer_service()
        return await offer_service.parse_offer_list(offer_ids)


async def get_offer_characteristics_refactored(offer_id: str) -> Offer:
    """
    Get comprehensive offer characteristics including location data

    Replaces the original get_offer_characteristics method
    """
    async with get_services() as services:
        offer_service = services.get_offer_service()
        return await offer_service.get_offer_characteristics(offer_id)


async def get_offer_location(offer_id: str) -> Optional[dict]:
    """
    Get just the location information for an offer
    """
    async with get_services() as services:
        offer_service = services.get_offer_service()
        return await offer_service.get_offer_location(offer_id)


async def is_offer_sensitive(offer_id: str) -> bool:
    """
    Check if an offer is marked as sensitive content
    """
    async with get_services() as services:
        offer_service = services.get_offer_service()
        return await offer_service.is_offer_sensitive(offer_id)


async def get_offers_by_item_id(item_id: str) -> list[Offer]:
    """
    Get all offers for a specific item ID
    """
    async with get_services() as services:
        offer_service = services.get_offer_service()
        return await offer_service.get_offers_by_item_id(item_id)


async def bulk_get_offers(offer_ids: list[str]) -> dict[str, Offer]:
    """
    Efficiently get multiple offers at once
    """
    async with get_services() as services:
        offer_service = services.get_offer_service()
        return await offer_service.bulk_get_offers(offer_ids)


async def get_offer_booking_stats(offer_id: str) -> Optional[dict]:
    """
    Get booking statistics for an offer
    """
    async with get_services() as services:
        offer_service = services.get_offer_service()
        return await offer_service.get_offer_booking_stats(offer_id)


# Example of composing multiple services
async def get_offer_with_context(offer_id: str, user_id: str) -> dict:
    """
    Get offer with additional context (e.g., if it's recommendable for the user)
    Demonstrates how easy it is to compose multiple services
    """
    async with get_services() as services:
        offer_service = services.get_offer_service()
        non_rec_service = services.get_non_recommendable_offer_service()

        # Get offer details
        offer = await offer_service.get_offer_characteristics(offer_id)

        # Check if it's non-recommendable for this user (if we have item_id)
        is_non_recommendable = False
        if offer.found and offer.item_id:
            # Create a minimal user context for the check
            from huggy.schemas.user import UserContext

            user_context = UserContext(
                user_id=user_id,
                age=18,  # Default values
                longitude=None,
                latitude=None,
                found=False,
                iris_id=None,
                is_geolocated=False,
            )
            is_non_recommendable = await non_rec_service.is_item_non_recommendable(
                user_context, offer.item_id
            )

        return {
            "offer": offer,
            "is_non_recommendable": is_non_recommendable,
            "booking_stats": await offer_service.get_offer_booking_stats(offer_id)
            if offer.found
            else None,
        }
