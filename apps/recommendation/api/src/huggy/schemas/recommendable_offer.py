import typing as t
from pydantic import BaseModel
from datetime import datetime


class RecommendableOfferDB(BaseModel):
    """ORM model for RecommendableOffer"""

    offer_id: str
    item_id: str
    venue_id: str
    user_distance: t.Optional[float]
    booking_number: float
    category: str
    subcategory_id: str
    search_group_name: str
    stock_price: float
    offer_creation_date: t.Optional[datetime]
    stock_beginning_date: t.Optional[datetime]
    venue_latitude: t.Optional[float]
    venue_longitude: t.Optional[float]
    is_geolocated: t.Optional[bool]

    class Config:
        orm_mode = True


class RecommendableOffer(RecommendableOfferDB):
    """Recommendable Offer object"""

    item_rank: int


class RankedOffer(RecommendableOffer):
    """Scored Offer"""

    offer_output: float  # final output
    offer_score: float  # higher = better
