from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic.alias_generators import to_camel

from schemas.categories import CategoryEnum
from schemas.categories import SearchGroupNameEnum
from schemas.categories import SubcategoryEnum


class PlaylistRequestParams(BaseModel):
    """
    Strict validation schema for incoming HTTP POST payloads.

    This model acts as a gatekeeper, ensuring the frontend sends correctly
    formatted filters. It uses an alias generator to automatically convert
    incoming camelCase JSON (e.g., 'startDate') into Pythonic snake_case
    attributes ('start_date').
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    # --- Temporal Constraints ---
    start_date: datetime | None = None
    end_date: datetime | None = None
    is_event: bool | None = None

    # --- Contextual & Format Constraints ---
    is_duo: bool | None = None
    is_restrained: bool | None = True
    is_digital: bool | None = None

    # --- Financial Constraints ---
    price_max: float | None = None
    price_min: float | None = None

    # --- Categorization Filters ---
    categories: list[CategoryEnum] | None = None
    subcategories: list[SubcategoryEnum] | None = None
    search_group_names: list[SearchGroupNameEnum] | None = None


class RecommendationMetadata(BaseModel):
    """
    Metadata describing how the recommendation was generated.
    Useful for client-side analytics, A/B testing, and debugging.
    """

    reco_origin: str
    model_origin: str
    call_id: str


class RecommendationResponse(BaseModel):
    """
    The final standard payload returned to the client application.
    Contains the ordered list of offer IDs to display in the UI.
    """

    playlist_recommended_offers: list[str]
    params: RecommendationMetadata
    from_cache: bool = False
