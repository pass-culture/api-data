from dataclasses import dataclass
from datetime import datetime


@dataclass
class EnrichedRecommendableOffer:
    """
    Represents a fully resolved and enriched offer.

    This class combines physical/database attributes (venue, dates) with
    Machine Learning attributes (scores, embeddings) and user-contextual
    attributes (calculated geographical distance).

    Using this dedicated class prevents runtime mutation of SQLAlchemy models
    and provides clear, strictly-typed attributes for the rest of the pipeline.
    """

    # --- Core Identifiers & DB Data ---
    offer_id: str
    item_id: str
    offer_creation_date: datetime | None
    stock_beginning_date: datetime | None

    # --- Geographical Context ---
    is_geolocated: bool | None
    venue_latitude: float | None
    venue_longitude: float | None
    offer_user_distance: float | None

    # --- ML & Ranking Features ---
    item_score: float | None
    item_rank: int
    item_origin: str
    semantic_emb_mean: float | None

    # --- Item Metadata & Classification ---
    stock_price: float
    category: str
    subcategory_id: str
    search_group_name: str

    # --- Popularity & Engagement Metrics ---
    booking_number: int
    booking_number_last_7_days: int
    booking_number_last_14_days: int
    booking_number_last_28_days: int

    ranking_score: float = 0.0
