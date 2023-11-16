import typing as t

from pydantic import BaseModel


class OfferInput(BaseModel):
    """Acceptable input in a API request for offer"""

    offer_id: str
    longitude: float = None
    latitude: float = None


class Offer(BaseModel):
    """Characteristics of an offer."""

    offer_id: str
    item_id: t.Optional[str] = None
    latitude: t.Optional[float] = None
    longitude: t.Optional[float] = None
    iris_id: t.Optional[str] = None
    booking_number: float = 0
    is_sensitive: bool = False
    found: bool = False
    is_geolocated: t.Optional[bool] = None
