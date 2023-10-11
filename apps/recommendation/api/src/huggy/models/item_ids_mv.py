from sqlalchemy import Column, String, Integer

from huggy.utils.database import Base
from pydantic import BaseModel


class ItemIdsMv(Base):
    """Database model of item_ids materialized view."""

    __tablename__ = "item_ids_mv"
    item_id = Column(String, primary_key=True)
    offer_id = Column(String, primary_key=True)
    booking_number = Column(Integer)


class ItemIds(BaseModel):
    """Objet of the model of the ItemIds."""

    item_id: str
    offer_id: str
    booking_number: int

    class Config:
        orm_mode = True
