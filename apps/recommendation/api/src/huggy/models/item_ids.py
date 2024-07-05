import typing as t

from huggy.database.base import Base, MaterializedBase
from sqlalchemy import Column, Float, String
from sqlalchemy.types import Boolean


class ItemIds(MaterializedBase):
    """
    Database model of recommendable_offers table.
    """

    def materialized_tables(self):
        return [
            ItemIdsMv,
            ItemIdsMvOld,
            ItemIdsMvTmp,
        ]

    """Database model of item_ids materialized view."""

    item_id = Column(String)
    offer_id = Column(String, primary_key=True)
    booking_number = Column(Float)
    is_sensitive = Column(Boolean)
    venue_latitude = Column(Float)
    venue_longitude = Column(Float)


class ItemIdsMv(ItemIds, Base):
    __tablename__ = "item_ids_mv"


class ItemIdsMvTmp(ItemIds, Base):
    __tablename__ = "item_ids_mv_tmp"


class ItemIdsMvOld(ItemIds, Base):
    __tablename__ = "item_ids_mv_old"
