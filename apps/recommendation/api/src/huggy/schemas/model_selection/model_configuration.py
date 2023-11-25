from pydantic import BaseModel
import typing as t
from dataclasses import dataclass


@dataclass
class DiversificationParams(BaseModel):
    is_active: bool
    is_reco_shuffled: bool
    mixing_features: str
    order_column: str
    order_ascending: bool
    submixing_feature_dict: dict

    async def to_dict(self):
        return {
            "is_active": self.is_active,
            "is_reco_shuffled": self.is_reco_shuffled,
            "mixing_features": self.mixing_features,
            "order_column": self.order_column,
            "order_ascending": self.order_ascending,
        }


class ForkParamsInput(BaseModel):
    bookings_count: int = None
    clicks_count: int = None
    favorites_count: int = None


class ModelTypeInput(BaseModel):
    retrieval: str = "default"
    ranking: str = "default"
    query_order: str = "item_rank"


class WarnModelTypeDefaultInput(ModelTypeInput):
    retrieval: str = "mix"
    ranking: str = "default"
    query_order: str = "item_rank"


class ColdStartModelTypeDefaultInput(ModelTypeInput):
    retrieval: str = "tops"
    ranking: str = "default"
    query_order: str = "item_rank"
