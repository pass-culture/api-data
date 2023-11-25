import typing as t
import huggy.core.model_selection.endpoint.offer_retrieval as offer_retrieval

from huggy.core.endpoint.retrieval_endpoint import RetrievalEndpoint
from huggy.core.model_selection.model_configuration.configuration import (
    ModelConfigurationInput,
)
from enum import Enum


class SimOffersRetrievalChoices(Enum):
    MIX = "mix"
    MIX_TOPS = "mix_tops"
    TOPS = "tops"


class SimilarModelConfigurationInput(ModelConfigurationInput):
    def get_retrieval(self, model_type) -> t.List[RetrievalEndpoint]:
        default = [
            offer_retrieval.offer_retrieval_endpoint,
            offer_retrieval.semantic_offer_retrieval_endpoint,
        ]
        return {
            SimOffersRetrievalChoices.MIX: default,
            SimOffersRetrievalChoices.SEMANTIC: [
                offer_retrieval.semantic_offer_retrieval_endpoint,
            ],
            SimOffersRetrievalChoices.MIX_TOPS: [
                offer_retrieval.offer_retrieval_endpoint,
                offer_retrieval.offer_filter_retrieval_endpoint,
                offer_retrieval.semantic_offer_retrieval_endpoint,
            ],
        }.get(model_type, default)
