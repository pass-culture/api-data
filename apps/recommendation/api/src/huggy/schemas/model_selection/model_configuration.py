import typing as t
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class RetrievalChoices(Enum):
    MIX = "mix"
    TOPS = "tops"
    MIX_TOPS = "m&t"
    RECOMMENDATION = "reco"
    MIX_RECOMMENDATION = "mix_reco"
    RAW_RETRIEVAL = "raw_retrieval"
    RECOMMENDATION_VERSION_B = "reco_b"
    MIX_VERSION_B = "mix_b"
    MIX_VERSION_C = "mix_c"
    MIX_TOPS_VERSION_B = "m&t_b"
    MIX_TOPS_VERSION_C = "m&t_c"
    SEMANTIC = "sm"
    GRAPH = "graph"


class RankingChoices(Enum):
    MODEL = "model"
    VERSION_B = "version_b"
    DISTANCE = "dist"
    NO_POPULARITY = "no_pop"
    OFF = "off"


class DiversificationChoices(Enum):
    ON = "on"
    GTL_ID = "gtl_id"
    GTL_LVL3 = "glt_lvl3"
    GTL_LVL4 = "glt_lvl4"
    OFF = "off"


class QueryOrderChoices(Enum):
    ITEM_RANK = "irank"
    BOOKING_NUMBER = "book"
    USER_DISTANCE = "dist"


class ForkParamsInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    bookings_count: t.Optional[int] = Field(alias="b", default=1)
    clicks_count: t.Optional[int] = Field(alias="c", default=25)
    favorites_count: t.Optional[int] = Field(alias="f", default=None)


class ModelTypeInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    retrieval: RetrievalChoices = Field(alias="rt", default=RetrievalChoices.MIX)
    ranking: RankingChoices = Field(alias="rk", default=RankingChoices.MODEL)
    query_order: QueryOrderChoices = Field(
        alias="qo", default=QueryOrderChoices.ITEM_RANK
    )


class DiversificationParamsInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    diversication_type: DiversificationChoices = Field(
        alias="d", default=DiversificationChoices.ON
    )


class WarnModelTypeDefaultInput(ModelTypeInput):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    retrieval: RetrievalChoices = Field(alias="rt", default=RetrievalChoices.MIX)


class ColdStartModelTypeDefaultInput(ModelTypeInput):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    retrieval: RetrievalChoices = Field(alias="rt", default=RetrievalChoices.TOPS)
