import typing as t

from pydantic import BaseModel, ConfigDict


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


class OfferDistance(BaseModel):
    """Offer details in a recommendation context."""

    model_config = ConfigDict(from_attributes=True)
    offer_id: str
    item_id: str
    user_distance: t.Optional[float]
    venue_latitude: t.Optional[float]
    venue_longitude: t.Optional[float]
