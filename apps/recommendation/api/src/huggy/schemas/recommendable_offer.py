import typing as t

from huggy.schemas.item import RecommendableItem


class RecommendableOffer(RecommendableItem):
    """
    Retrieved Offer in a given context (latitude and longitude)

    """

    offer_id: str
    user_distance: t.Optional[float]
    venue_latitude: t.Optional[float]
    venue_longitude: t.Optional[float]
    new_offer_is_geolocated: t.Optional[bool]
    new_offer_creation_days: t.Optional[int]
    new_offer_stock_price: t.Optional[float]
    new_offer_stock_beginning_days: t.Optional[int]
    new_offer_centroid_x: t.Optional[float]
    new_offer_centroid_y: t.Optional[float]


class RankedOffer(RecommendableOffer):
    """
    Ranked Recommendable Offer object based on RecommendableOffer model
    Contains the scoring of a Ranking Model.

    """

    offer_rank: float  # final output (lower = better)
    offer_score: t.Optional[float]  # scoring of the ranking model
    offer_origin: t.Optional[str]  # origin of the scoring
