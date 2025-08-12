from typing import Optional

from huggy.database.repository import MaterializedViewRepository
from huggy.models.item_ids import ItemIds, ItemIdsMv, ItemIdsMvOld, ItemIdsMvTmp
from huggy.schemas.offer import Offer
from huggy.services.iris_service import IrisService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class OfferService:
    """Service for handling offer-related operations"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = MaterializedViewRepository(
            session,
            ItemIds,
            fallback_tables=[ItemIdsMv, ItemIdsMvOld, ItemIdsMvTmp],
        )
        self.iris_service = IrisService(session)

    async def parse_offer_list(self, offer_ids: list[str]) -> list[Offer]:
        """
        Parse a list of offer IDs into full Offer objects
        """
        offers = []
        for offer_id in offer_ids:
            offer = await self.get_offer_characteristics(offer_id)
            if offer.found:
                offers.append(offer)
        return offers

    async def get_item_by_offer_id(self, offer_id: str) -> Optional[ItemIds]:
        """
        Get item information for a specific offer ID
        """
        if not offer_id:
            return None

        try:
            item_table = await self.repository.get_available_model()

            query = select(item_table).where(item_table.offer_id == offer_id)
            result = await self.session.execute(query)

            return result.scalars().first()

        except Exception as exc:
            from huggy.utils.exception import log_error

            log_error(exc, message="Exception error on get_item_by_offer_id")
            return None

    async def get_offer_characteristics(self, offer_id: str) -> Offer:
        """
        Get comprehensive offer characteristics including location data
        """
        # Default offer object
        offer = Offer(
            offer_id=offer_id,
            latitude=None,
            longitude=None,
            iris_id=None,
            is_geolocated=False,
            found=False,
        )

        try:
            # Get item data for this offer
            item_data = await self.get_item_by_offer_id(offer_id)

            if item_data is not None:
                latitude = item_data.venue_latitude
                longitude = item_data.venue_longitude
                iris_id = None

                # Get IRIS ID if coordinates are available
                if latitude is not None and longitude is not None:
                    iris_id = await self.iris_service.get_iris_from_coordinates(
                        latitude=latitude, longitude=longitude
                    )

                # Build complete offer object
                offer = Offer(
                    offer_id=offer_id,
                    latitude=latitude,
                    longitude=longitude,
                    iris_id=iris_id,
                    is_geolocated=iris_id is not None,
                    item_id=item_data.item_id,
                    booking_number=item_data.booking_number,
                    is_sensitive=bool(item_data.is_sensitive),
                    found=True,
                )

        except Exception as exc:
            from huggy.utils.exception import log_error

            log_error(exc, message="Exception error on get_offer_characteristics")

        return offer

    async def get_offers_by_item_id(self, item_id: str) -> list[Offer]:
        """
        Get all offers for a specific item ID
        """
        try:
            item_table = await self.repository.get_available_model()

            query = select(item_table).where(item_table.item_id == item_id)
            result = await self.session.execute(query)

            offers = []
            for item_data in result.scalars().all():
                offer = await self.get_offer_characteristics(item_data.offer_id)
                offers.append(offer)

            return offers

        except Exception as exc:
            from huggy.utils.exception import log_error

            log_error(exc, message="Exception error on get_offers_by_item_id")
            return []

    async def get_offer_location(self, offer_id: str) -> Optional[dict]:
        """
        Get just the location information for an offer
        """
        try:
            item_data = await self.get_item_by_offer_id(offer_id)

            if item_data and item_data.venue_latitude and item_data.venue_longitude:
                return {
                    "latitude": item_data.venue_latitude,
                    "longitude": item_data.venue_longitude,
                    "iris_id": await self.iris_service.get_iris_from_coordinates(
                        item_data.venue_latitude, item_data.venue_longitude
                    ),
                }

        except Exception as exc:
            from huggy.utils.exception import log_error

            log_error(exc, message="Exception error on get_offer_location")

        return None

    async def is_offer_sensitive(self, offer_id: str) -> bool:
        """
        Check if an offer is marked as sensitive content
        """
        try:
            item_data = await self.get_item_by_offer_id(offer_id)
            return bool(item_data.is_sensitive) if item_data else False

        except Exception:
            return False

    async def get_offer_booking_stats(self, offer_id: str) -> Optional[dict]:
        """
        Get booking statistics for an offer
        """
        try:
            item_data = await self.get_item_by_offer_id(offer_id)

            if item_data:
                return {
                    "booking_number": item_data.booking_number or 0,
                    "offer_id": offer_id,
                    "item_id": item_data.item_id,
                }

        except Exception as exc:
            from huggy.utils.exception import log_error

            log_error(exc, message="Exception error on get_offer_booking_stats")

        return None

    async def bulk_get_offers(self, offer_ids: list[str]) -> dict[str, Offer]:
        """
        Efficiently get multiple offers at once
        """
        result = {}

        try:
            item_table = await self.repository.get_available_model()

            # Get all items in one query
            query = select(item_table).where(item_table.offer_id.in_(offer_ids))
            db_result = await self.session.execute(query)

            # Process each item
            for item_data in db_result.scalars().all():
                offer_id = item_data.offer_id

                # Get IRIS ID if coordinates available
                iris_id = None
                if item_data.venue_latitude and item_data.venue_longitude:
                    iris_id = await self.iris_service.get_iris_from_coordinates(
                        item_data.venue_latitude, item_data.venue_longitude
                    )

                offer = Offer(
                    offer_id=offer_id,
                    latitude=item_data.venue_latitude,
                    longitude=item_data.venue_longitude,
                    iris_id=iris_id,
                    is_geolocated=iris_id is not None,
                    item_id=item_data.item_id,
                    booking_number=item_data.booking_number,
                    is_sensitive=bool(item_data.is_sensitive),
                    found=True,
                )

                result[offer_id] = offer

            # Add missing offers as not found
            for offer_id in offer_ids:
                if offer_id not in result:
                    result[offer_id] = Offer(
                        offer_id=offer_id,
                        latitude=None,
                        longitude=None,
                        iris_id=None,
                        is_geolocated=False,
                        found=False,
                    )

        except Exception as exc:
            from huggy.utils.exception import log_error

            log_error(exc, message="Exception error on bulk_get_offers")

        return result
