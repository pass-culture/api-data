import re
from datetime import datetime
from typing import Dict, List, Optional
from dateutil.parser import parse
from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, validator
from pydantic.alias_generators import to_camel

under_pat = re.compile(r"_([a-z])")


def underscore_to_camel(name):
    """
    Parse key into camelCase format
    """
    return under_pat.sub(lambda x: x.group(1).upper(), name)


class PlaylistParams(BaseModel):
    """Acceptable input in a API request for recommendations filters."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    model_endpoint: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_event: Optional[bool] = None
    is_duo: Optional[bool] = None
    price_max: Optional[float] = None
    price_min: Optional[float] = None
    is_reco_shuffled: Optional[bool] = None
    is_digital: Optional[bool] = None
    categories: Optional[List[str]] = None
    subcategories: Optional[List[str]] = None
    offer_type_list: Optional[List[Dict]] = None
    gtl_ids: Optional[List[str]] = None
    gtl_l1: Optional[List[str]] = None
    gtl_l2: Optional[List[str]] = None
    gtl_l3: Optional[List[str]] = None
    gtl_l4: Optional[List[str]] = None
    submixing_feature_dict: Optional[dict] = None

    @validator("start_date", "end_date", pre=True)
    def parse_datetime(cls, value):
        if value is not None:
            try:
                return parse(value)
            except ValueError:
                raise ValueError("Datetime format not recognized.")
        return None


class GetSimilarOfferPlaylistParams(PlaylistParams):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    user_id: Optional[str] = Field(Query(None))
    categories: Optional[List[str]] = Field(Query([]))
    subcategories: Optional[List[str]] = Field(Query([]))


class PostSimilarOfferPlaylistParams(PlaylistParams):
    user_id: str = None
