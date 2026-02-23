from datetime import datetime

from pydantic import BaseModel


class RecommendableItem(BaseModel):
    """
    Standardized schema for raw prediction items returned by the Vertex AI Retrieval model.

    In the recommendation system, an "Item" is an abstract concept (e.g., the movie "Inception").
    It will later be resolved into one or multiple physical/digital "Offers" (e.g., a specific
    screening at a specific cinema).

    This schema ensures strict type validation when deserializing the gRPC/JSON response
    from Google Vertex AI before it hits the spatial resolution and database filtering phases.
    """

    # --- Core Identifiers ---
    item_id: str
    item_origin: str

    # --- ML & Ranking Scores ---
    item_rank: int
    item_score: float | None
    item_cluster_id: str | None
    item_topic_id: str | None
    semantic_emb_mean: float | None

    # --- Popularity & Engagement Metrics ---
    # These metrics define the historical performance of the item on the platform
    booking_number: int
    booking_number_last_7_days: int
    booking_number_last_14_days: int
    booking_number_last_28_days: int

    # --- Item Metadata & Classification ---
    stock_price: float
    category: str
    subcategory_id: str
    search_group_name: str
    offer_creation_date: datetime | None
    stock_beginning_date: datetime | None

    # Granular classification tags (GTL - Global Taxonomy Level)
    gtl_id: str | None
    gtl_l3: str | None
    gtl_l4: str | None

    # --- Fast-Track Resolution Data ---
    # Used to bypass the database for digital or single-venue items (optimizing RAM/CPU)
    is_geolocated: bool | None
    total_offers: int
    example_offer_id: str | None
    example_venue_latitude: float | None
    example_venue_longitude: float | None
