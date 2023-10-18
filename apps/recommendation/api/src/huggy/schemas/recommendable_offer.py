import typing as t
from datetime import datetime

from pydantic import BaseModel


class OfferDistance(BaseModel):
    offer_id: str
    user_distance: float

    class Config:
        orm_mode = True


class RecommendableOffer(BaseModel):
    """
    ORM model for RecommendableOfferRaw database query.
    This is used only as a db query output of crud.recommendable_offer queries.
    """

    offer_id: str
    item_id: str
    venue_id: str
    user_distance: t.Optional[float]
    booking_number: float
    category: str
    subcategory_id: str
    search_group_name: str
    gtl_ids: t.Optional[str]
    gtl_l1: t.Optional[str]
    gtl_l2: t.Optional[str]
    gtl_l3: t.Optional[str]
    gtl_l4: t.Optional[str]
    stock_price: float
    offer_creation_date: t.Optional[datetime]
    stock_beginning_date: t.Optional[datetime]
    venue_latitude: t.Optional[float]
    venue_longitude: t.Optional[float]
    is_geolocated: t.Optional[bool]
    item_rank: int

    class Config:
        orm_mode = True


class RankedOffer(RecommendableOffer):
    """
    Ranked Recommendable Offer object based on RecommendableOffer model
    Contains the scoring of a Ranking Model.
    """

    offer_output: float  # final output
    offer_score: float  # higher = better
