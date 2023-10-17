from pydantic import parse_obj_as
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import huggy.schemas.offer as o
from huggy.crud.iris import Iris
from huggy.models.item_ids_mv import ItemIds, ItemIdsMv


class Offer:
    async def get_offer_characteristics(
        self, db: AsyncSession, offer_id: str, latitude: float, longitude: float
    ) -> o.Offer:
        """Query the database in ORM mode to get characteristics of an offer.
        Return : List[item_id,  number of booking associated].
        """
        offer_characteristics = (
            await db.execute(select(ItemIdsMv).where(ItemIdsMv.offer_id == offer_id))
        ).fetchone()

        if latitude and longitude:
            iris_id = await Iris().get_iris_from_coordinates(
                db, latitude=latitude, longitude=longitude
            )
        else:
            iris_id = None

        if offer_characteristics is not None:
            offer_characteristics: ItemIds = parse_obj_as(
                ItemIds, offer_characteristics
            )
            offer = o.Offer(
                offer_id=offer_id,
                latitude=latitude,
                longitude=longitude,
                iris_id=iris_id,
                is_geolocated=True if iris_id else False,
                item_id=offer_characteristics.item_id,
                booking_number=offer_characteristics.booking_number,
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
