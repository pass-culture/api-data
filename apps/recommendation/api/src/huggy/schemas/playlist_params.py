import re
from datetime import datetime
from typing import Optional

from dateutil.parser import parse
from fastapi import Query
from huggy.crud.offer import Offer
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel
from pydantic_core.core_schema import ValidationInfo
from sqlalchemy.ext.asyncio import AsyncSession

under_pat = re.compile(r"_([a-z])")


def underscore_to_camel(name):
    """
    Parse key into camelCase format
    """
    return under_pat.sub(lambda x: x.group(1).upper(), name)


class PlaylistParams(BaseModel):
    """Acceptable input in a API request for recommendations filters."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, protected_namespaces=()
    )
    model_endpoint: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_event: Optional[bool] = None
    is_duo: Optional[bool] = None
    price_max: Optional[float] = None
    price_min: Optional[float] = None
    is_reco_shuffled: Optional[bool] = None
    is_restrained: Optional[str] = None
    is_digital: Optional[bool] = None
    categories: Optional[list[str]] = None
    subcategories: Optional[list[str]] = None
    offer_type_list: Optional[list[dict]] = None
    gtl_ids: Optional[list[str]] = None
    gtl_l1: Optional[list[str]] = None
    gtl_l2: Optional[list[str]] = None
    gtl_l3: Optional[list[str]] = None
    gtl_l4: Optional[list[str]] = None
    submixing_feature_dict: Optional[dict] = None
    offers: Optional[list[str]] = None

    @field_validator("start_date", "end_date", mode="before")
    def parse_datetime(cls, value, info: ValidationInfo) -> datetime:
        if value is not None:
            try:
                return parse(value)
            except ValueError:
                raise ValueError("Datetime format not recognized.")
        return None

    def playlist_type(self):
        if self.categories and len(self.categories) > 1:
            return "multipleCategoriesRecommendations"
        if self.categories and len(self.categories) == 1:
            return "singleCategoryRecommendations"
        if self.subcategories and len(self.subcategories) > 1:
            return "multipleSubCategoriesRecommendations"
        if self.subcategories and len(self.subcategories) == 1:
            return "singleSubCategoryRecommendations"
        return "GenericRecommendations"

    async def parse_offers(self, db: AsyncSession) -> list[Offer]:
        if self.offers and len(self.offers) > 0:
            offer_list = []
            for offer_id in self.offers:
                offer = await Offer().get_offer_characteristics(db, offer_id)
                offer_list.append(offer)
            self.offers = offer_list

    async def to_dict(self):
        return self.dict()


class GetSimilarOfferPlaylistParams(PlaylistParams):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    user_id: Optional[str] = Field(Query(None))
    categories: Optional[list[str]] = Field(Query([]))
    subcategories: Optional[list[str]] = Field(Query([]))

    def playlist_type(self):
        if len(self.categories) > 1:
            return "otherCategoriesSimilarOffers"
        if len(self.subcategories) > 1:
            return "otherSubCategoriesSimilarOffers"
        if len(self.categories) == 1:
            return "sameCategorySimilarOffers"
        if len(self.subcategories) == 1:
            return "sameSubCategorySimilarOffers"
        return "GenericSimilarOffers"


class PostSimilarOfferPlaylistParams(PlaylistParams):
    user_id: str = None
