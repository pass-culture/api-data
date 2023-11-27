from pydantic import BaseModel, Field
import typing as t

from enum import Enum


class RetrievalChoices(Enum):
    MIX = "mix"
    TOPS = "tops"
    MIX_TOPS = "m&t"
    RECOMMENDATION = "reco"
    RECOMMENDATION_VERSIONB = "reco_b"
    MIX_VERSION_B = "mix_b"
    SEMANTIC = "sm"


class RankingChoices(Enum):
    MODEL = "model"
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
    bookings_count: t.Optional[int] = Field(alias="b", default=0)
    clicks_count: t.Optional[int] = Field(alias="c", default=0)
    favorites_count: t.Optional[int] = Field(alias="f", default=0)

    class Config:
        allow_population_by_field_name = True


class ModelTypeInput(BaseModel):
    retrieval: RetrievalChoices = Field(alias="rt", default=RetrievalChoices.MIX)
    ranking: RankingChoices = Field(alias="rk", default=RankingChoices.MODEL)
    query_order: QueryOrderChoices = Field(
        alias="qo", default=QueryOrderChoices.ITEM_RANK
    )

    class Config:
        allow_population_by_field_name = True


class DiversificationParamsInput(BaseModel):
    diversication_type: DiversificationChoices = Field(
        alias="d", default=DiversificationChoices.ON
    )

    class Config:
        allow_population_by_field_name = True


class WarnModelTypeDefaultInput(ModelTypeInput):
    retrieval: RetrievalChoices = Field(alias="rt", default=RetrievalChoices.MIX)


class ColdStartModelTypeDefaultInput(ModelTypeInput):
    retrieval: RetrievalChoices = Field(alias="rt", default=RetrievalChoices.TOPS)
