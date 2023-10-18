import typing as t

from sqlalchemy import Column, Float, String

from huggy.database.base import Base


class ItemIdsMv(Base):
    """Database model of item_ids materialized view."""

    __tablename__ = "item_ids_mv"
    item_id = Column(String)
    offer_id = Column(String, primary_key=True)
    booking_number = Column(Float)
