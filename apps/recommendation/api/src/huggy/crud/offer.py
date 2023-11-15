import typing as t

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import huggy.schemas.offer as o
from huggy.crud.iris import Iris
from huggy.models.item_ids_mv import ItemIdsMv


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
        latitude = offer_characteristics.venue_latitude
        longitude = offer_characteristics.venue_longitude
        if latitude and longitude:
            iris_id = await Iris().get_iris_from_coordinates(
                db, latitude=latitude, longitude=longitude
            )
        else:
            iris_id = None

        if offer_characteristics is not None:
            offer = o.Offer(
                offer_id=offer_id,
                latitude=latitude,
                longitude=longitude,
                iris_id=iris_id,
                is_geolocated=True if iris_id else False,
                item_id=offer_characteristics.item_id,
                booking_number=offer_characteristics.booking_number,
                is_sensitive=offer_characteristics.is_sensitive,
                found=True,
            )
        else:
            offer = o.Offer(
                offer_id=offer_id,
                latitude=latitude,
                longitude=longitude,
                iris_id=iris_id,
                is_geolocated=True if iris_id else False,
                found=False,
            )
        return offer
