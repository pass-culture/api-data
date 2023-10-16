from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from sqlalchemy.sql.expression import literal_column
from geoalchemy2.elements import WKTElement
from typing import List, Dict
from huggy.utils.cloud_logging import logger
from pydantic import parse_obj_as
from huggy.schemas.offer import Offer
from huggy.models.item_ids_mv import ItemIdsMv, ItemIds

from huggy.crud.iris import get_iris_from_coordinates


def get_offer_characteristics(
    db: Session, offer_id: str, latitude: float, longitude: float
) -> Offer:
    """Query the database in ORM mode to get characteristics of an offer.
    Return : List[item_id,  number of booking associated].
    """
    offer_characteristics = (
        db.query(ItemIdsMv).filter(ItemIdsMv.offer_id == offer_id).first()
    )

    if latitude and longitude:
        iris_id = get_iris_from_coordinates(db, latitude=latitude, longitude=longitude)
    else:
        iris_id = None

    if offer_characteristics is not None:
        offer_characteristics: ItemIds = parse_obj_as(ItemIds, offer_characteristics)
        offer = Offer(
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
        offer = Offer(
            offer_id=offer_id,
            latitude=latitude,
            longitude=longitude,
            iris_id=iris_id,
            is_geolocated=True if iris_id else False,
            found=False,
        )
    return offer
