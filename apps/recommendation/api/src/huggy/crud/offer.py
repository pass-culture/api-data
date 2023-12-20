import typing as t

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import huggy.schemas.offer as o
from huggy.crud.iris import Iris
from huggy.models.item_ids import ItemIds

from asyncpg.exceptions import UndefinedTableError
from huggy.utils.exception import log_error
from huggy.utils.cloud_logging import logger


class Offer:
    async def get_item(self, db: AsyncSession, offer_id: str) -> t.Optional[ItemIds]:
        try:
            item_table: ItemIds = await ItemIds().get_available_table(db)
            if offer_id is not None:
                return (
                    (
                        await db.execute(
                            select(item_table).where(item_table.offer_id == offer_id)
                        )
                    )
                    .scalars()
                    .first()
                )
        except UndefinedTableError as exc:
            log_error(exc, message="Exception error on get_item")

        return None

    async def get_offer_characteristics(
        self, db: AsyncSession, offer_id: str
    ) -> o.Offer:
        """Query the database in ORM mode to get characteristics of an offer.
        Return : List[item_id,  number of booking associated].
        """
        offer_characteristics = await self.get_item(db, offer_id)
        iris_id = None
        offer = o.Offer(
            offer_id=offer_id,
            latitude=None,
            longitude=None,
            iris_id=None,
            is_geolocated=False,
            found=False,
        )
        try:
            if offer_characteristics is not None:
                latitude = offer_characteristics.venue_latitude
                longitude = offer_characteristics.venue_longitude
                if latitude is not None and longitude is not None:
                    iris_id = await Iris().get_iris_from_coordinates(
                        db, latitude=latitude, longitude=longitude
                    )

                offer = o.Offer(
                    offer_id=offer_id,
                    latitude=latitude,
                    longitude=longitude,
                    iris_id=iris_id,
                    is_geolocated=iris_id is not None,
                    item_id=offer_characteristics.item_id,
                    booking_number=offer_characteristics.booking_number,
                    is_sensitive=True if offer_characteristics.is_sensitive else False,
                    found=True,
                )
        except UndefinedTableError as exc:
            log_error(exc, message="Exception error on get_offer_characteristics")

        return offer
