import typing as t
from datetime import datetime

from pydantic import BaseModel


class RecommendableItem(BaseModel):
    item_id: str
    item_rank: int  # Rank of the retrieval model (lower = better)
    item_score: t.Optional[float]  # scoring of the retrieval model (real distance)
    item_origin: str
    item_cluster_id: t.Optional[str]
    item_topic_id: t.Optional[str]
    semantic_emb_mean: t.Optional[float]
    is_geolocated: t.Optional[bool]
    booking_number: float
    booking_number_last_7_days: float
    booking_number_last_14_days: float
    booking_number_last_28_days: float
    stock_price: float
    category: str
    subcategory_id: str
    search_group_name: str
    offer_creation_date: t.Optional[datetime]
    stock_beginning_date: t.Optional[datetime]
    gtl_id: t.Optional[str]
    gtl_l3: t.Optional[str]
    gtl_l4: t.Optional[str]
    total_offers: float
    example_offer_id: t.Optional[str]
    example_venue_latitude: t.Optional[float]
    example_venue_longitude: t.Optional[float]
