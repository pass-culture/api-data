import typing as t
from pydantic import BaseModel
from datetime import datetime


class OfferDistance(BaseModel):
    offer_id: str
    user_distance: float

    class Config:
        orm_mode = True


class RecommendableOfferRawDB(BaseModel):
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
    stock_price: float
    offer_creation_date: t.Optional[datetime]
    stock_beginning_date: t.Optional[datetime]
    venue_latitude: t.Optional[float]
    venue_longitude: t.Optional[float]
    is_geolocated: t.Optional[bool]

    class Config:
        orm_mode = True


class RecommendableOffer(RecommendableOfferRawDB):
    """
    Recommendable Offer object based on RecommendableOfferDB model
    Contains the scored item_rank from a Retrieval Model.
    """

    item_rank: int


class RankedOffer(RecommendableOffer):
    """
    Ranked Recommendable Offer object based on RecommendableOffer model
    Contains the scoring of a Ranking Model.
    """

    offer_output: float  # final output
    offer_score: float  # higher = better
