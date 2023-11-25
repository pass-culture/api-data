import huggy.core.model_selection.endpoint.user_ranking as user_ranking
import huggy.core.model_selection.endpoint.user_retrieval as user_retrieval
from huggy.core.endpoint.ranking_endpoint import RankingEndpoint
from huggy.core.endpoint.retrieval_endpoint import RetrievalEndpoint
import typing as t
from huggy.core.model_selection.model_configuration.configuration import (
    ModelConfigurationInput,
)

from enum import Enum


class RecoRetrievalChoices(Enum):
    MIX = "mix"
    TOPS = "tops"
    RECOMMENDATION = "recommendation"
    RECOMMENDATION_VERSIONB = "recommendaton_version_b"
    MIX_VERSION_B = "mix_version_b"


class RecoModelConfigurationInput(ModelConfigurationInput):
    def get_retrieval(self, model_type) -> t.List[RetrievalEndpoint]:
        default = [
            user_retrieval.filter_retrieval_endpoint,
            user_retrieval.recommendation_retrieval_endpoint,
        ]
        return {
            RecoRetrievalChoices.MIX: default,
            RecoRetrievalChoices.RECOMMENDATION: [
                user_retrieval.recommendation_retrieval_endpoint,
            ],
            RecoRetrievalChoices.TOPS: [
                user_retrieval.filter_retrieval_endpoint,
            ],
            RecoRetrievalChoices.RECOMMENDATION_VERSIONB: [
                user_retrieval.recommendation_retrieval_version_b_endpoint,
            ],
            RecoRetrievalChoices.MIX_VERSION_B: [
                user_retrieval.filter_retrieval_version_b_endpoint,
                user_retrieval.recommendation_retrieval_version_b_endpoint,
            ],
        }.get(model_type, default)
