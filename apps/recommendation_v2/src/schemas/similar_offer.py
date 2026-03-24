from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic.alias_generators import to_camel

from schemas.playlist_recommendation import CategoryEnum
from schemas.playlist_recommendation import SearchGroupNameEnum
from schemas.playlist_recommendation import SubcategoryEnum


class SimilarOfferRequestParams(BaseModel):
    """
    Parameters for fetching similar offers.
    These parameters allow filtering the results of similarity search.
    """
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    categories: list[CategoryEnum] | None = None
    subcategories: list[SubcategoryEnum] | None = None
    search_group_names: list[SearchGroupNameEnum] | None = None


class SimilarOfferResponse(BaseModel):
    """
    Standard response for similar offers endpoint.
    """
    results: list[str]
    params: dict[str, Any]

