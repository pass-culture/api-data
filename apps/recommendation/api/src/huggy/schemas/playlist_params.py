import re
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import Query
from pydantic import BaseModel, Field, validator

under_pat = re.compile(r"_([a-z])")


def underscore_to_camel(name):
    """
    Parse key into camelCase format
    """
    return under_pat.sub(lambda x: x.group(1).upper(), name)


class PlaylistParams(BaseModel):
    """Acceptable input in a API request for recommendations filters."""
    
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
    gtl_l4: Optional[List[str]]= None
    submixing_feature_dict: Optional[dict] = None
    
    @validator("start_date", "end_date", pre=True)
    def parse_datetime(cls, value):
        if value is not None:
            datetime_formats = [
                "%Y-%m-%d",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f%z" 
            ]

            for datetime_format in datetime_formats:
                try:
                    return datetime.strptime(value, datetime_format)
                except ValueError:
                    pass

            raise ValueError("Datetime format not recognized.")
        return None
    class Config:
        alias_generator = underscore_to_camel


class GetSimilarOfferPlaylistParams(PlaylistParams):
    user_id: str = None
    categories: List[str] = Field(Query([]))
    subcategories: List[str] = Field(Query([]))
    gtl_ids: List[str] = Field(Query([]))
    gtl_l1: List[str] = Field(Query([]))
    gtl_l2: List[str] = Field(Query([]))
    gtl_l3: List[str] = Field(Query([]))
    gtl_l4: List[str] = Field(Query([]))


class PostSimilarOfferPlaylistParams(PlaylistParams):
    user_id: str = None
    categories: List[str] = None
    subcategories: List[str] = None
    offer_type_list: str = None  # useless in similar offer


class RecommendationPlaylistParams(PlaylistParams):
    categories: List[str] = None
    subcategories: List[str] = None
    offer_type_list: List[Dict] = None
