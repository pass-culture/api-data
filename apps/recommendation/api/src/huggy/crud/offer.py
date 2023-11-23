import typing as t

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.encoders import jsonable_encoder
import huggy.schemas.offer as o
from huggy.crud.iris import Iris
from huggy.models.item_ids_mv import ItemIdsMv
from huggy.utils.cloud_logging import logger


class Offer:
    async def get_item(self, db, offer_id) -> t.Optional[ItemIdsMv]:
        if offer_id is not None:
            return (
                (
                    await db.execute(
                        select(ItemIdsMv).where(ItemIdsMv.offer_id == offer_id)
                    )
                )
                .scalars()
                .first()
            )
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
                is_geolocated=True if iris_id else False,
                item_id=offer_characteristics.item_id,
                booking_number=offer_characteristics.booking_number,
                is_sensitive=True if offer_characteristics.is_sensitive else False,
                found=True,
            )
        logger.debug(
            f"offer details offer_id {offer_id}", extra=jsonable_encoder(offer.dict())
        )
        return offer
