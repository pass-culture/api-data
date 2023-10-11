from fastapi import Query
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Dict, Optional
import re


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

    class Config:
        alias_generator = underscore_to_camel


class GetSimilarOfferPlaylistParams(PlaylistParams):
    user_id: str = None
    categories: List[str] = Field(Query([]))
    subcategories: List[str] = Field(Query([]))


class PostSimilarOfferPlaylistParams(PlaylistParams):
    user_id: str = None
