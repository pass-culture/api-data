from pydantic import BaseModel
import typing as t
from dataclasses import dataclass

from enum import Enum


class RetrievalChoices(Enum):
    MIX = "mix"
    TOPS = "tops"
    MIX_TOPS = "mix_and_tops"
    RECOMMENDATION = "recommendation"
    RECOMMENDATION_VERSIONB = "recommendaton_version_b"
    MIX_VERSION_B = "mix_version_b"
    SEMANTIC = "semantic"


class RankingChoices(Enum):
    MODEL = "model"
    DISTANCE = "user_distance"
    NO_POPULARITY = "no_popularity"
    OFF = "off"


class DiversificationChoices(Enum):
    ON = "on"
    GTL_ID = "gtl_id"
    GTL_LVL3 = "glt_lvl3"
    GTL_LVL4 = "glt_lvl4"
    OFF = "off"


class QueryOrderChoices(Enum):
    ITEM_RANK = "item_rank"
    BOOKING_NUMBER = "booking_number"
    USER_DISTANCE = "user_distance"


class ForkParamsInput(BaseModel):
    bookings_count: t.Optional[int] = 0
    clicks_count: t.Optional[int] = 0
    favorites_count: t.Optional[int] = 0


class ModelTypeInput(BaseModel):
    retrieval: RetrievalChoices = RetrievalChoices.MIX
    ranking: RankingChoices = RankingChoices.MODEL
    query_order: QueryOrderChoices = QueryOrderChoices.ITEM_RANK


class DiversificationParamsInput(BaseModel):
    diversication_type: DiversificationChoices = DiversificationChoices.ON


class WarnModelTypeDefaultInput(ModelTypeInput):
    retrieval: RetrievalChoices = RetrievalChoices.MIX
    ranking: RankingChoices = RankingChoices.MODEL


class ColdStartModelTypeDefaultInput(ModelTypeInput):
    retrieval: RetrievalChoices = RetrievalChoices.TOPS
    ranking: RankingChoices = RankingChoices.MODEL
