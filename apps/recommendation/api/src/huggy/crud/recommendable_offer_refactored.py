"""
Refactored version of recommendable_offer.py using the new service pattern

This demonstrates how much cleaner the code becomes with proper separation of concerns
"""

from typing import Optional

from huggy.schemas.item import RecommendableItem
from huggy.schemas.model_selection.model_configuration import QueryOrderChoices
from huggy.schemas.offer import Offer, OfferDistance
from huggy.schemas.user import UserContext
from huggy.services.container import get_services


async def get_nearest_offers_refactored(
    user: UserContext,
    recommendable_items: list[RecommendableItem],
    limit: int = 500,
    input_offers: Optional[list[Offer]] = None,
    query_order: QueryOrderChoices = QueryOrderChoices.ITEM_RANK,
) -> list[OfferDistance]:
    """
    Refactored version that's much cleaner and easier to understand

    Compare this to the original 179-line function in recommendable_offer.py!
    """
    async with get_services() as services:
        offer_service = services.get_recommendable_offer_service()

        return await offer_service.get_nearest_offers(
            user=user,
            recommendable_items=recommendable_items,
            limit=limit,
            input_offers=input_offers,
            query_order=query_order,
        )


async def get_offers_by_ids_refactored(offer_ids: list[str]) -> list[dict]:
    """Simple function to get offers by IDs"""
    async with get_services() as services:
        offer_service = services.get_recommendable_offer_service()
        return await offer_service.get_offers_by_ids(offer_ids)


async def find_offers_near_location(
    latitude: float,
    longitude: float,
    radius_km: float = 10.0,
    limit: int = 100,
) -> list[dict]:
    """New functionality that's easy to add with the service pattern"""
    async with get_services() as services:
        offer_service = services.get_recommendable_offer_service()
        return await offer_service.get_offers_in_radius(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            limit=limit,
        )
