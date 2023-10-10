from pydantic import BaseModel
from dataclasses import dataclass
import typing as t


class OfferInput(BaseModel):
    """Acceptable input in a API request for offer"""

    offer_id: str
    longitude: float = None
    latitude: float = None


@dataclass
class Offer:
    """Characteristics of an offer"""

    offer_id: str
    item_id: t.Optional[str] = None
    latitude: t.Optional[float] = None
    longitude: t.Optional[float] = None
    iris_id: t.Optional[str] = None
    booking_number: float = 0
    found: bool = False
    is_geolocated: t.Optional[bool] = None


class RecommendableOfferQuery(BaseModel):
    """ORM model for RecommendableOffer"""

    offer_id: str
    item_id: str
    venue_id: str
    user_distance: float
    booking_number: float
    category: str
    subcategory_id: str
    stock_price: float
    offer_creation_date: str
    stock_beginning_date: str
    search_group_name: str
    venue_latitude: float
    venue_longitude: float
    is_geolocated: t.Optional[bool]
    item_rank: int

    class Config:
        orm_mode = True


@dataclass
class RecommendableOffer:
    """Scored Offer"""

    offer_id: str
    item_id: str
    venue_id: str
    user_distance: float
    booking_number: float
    category: str
    subcategory_id: str
    stock_price: float
    offer_creation_date: str
    stock_beginning_date: str
    search_group_name: str
    venue_latitude: float
    venue_longitude: float
    is_geolocated: t.Optional[bool]
    item_rank: int
    offer_score: float = None  # higher = better
    offer_output: float = None  # final output
