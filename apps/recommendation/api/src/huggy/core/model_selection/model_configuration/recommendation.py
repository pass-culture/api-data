import typing as t

import huggy.core.model_selection.endpoint.user_retrieval as user_retrieval
from huggy.core.endpoint.retrieval_endpoint import RetrievalEndpoint
from huggy.core.model_selection.model_configuration.configuration import (
    ModelConfigurationInput,
)
from huggy.schemas.model_selection.model_configuration import RetrievalChoices


class RecoModelConfigurationInput(ModelConfigurationInput):
    def get_retrieval(self, model_type) -> t.List[RetrievalEndpoint]:
        default = [
            user_retrieval.filter_retrieval_endpoint,
            user_retrieval.recommendation_retrieval_endpoint,
            user_retrieval.trend_release_date_retrieval_endpoint,
            user_retrieval.trend_creation_date_retrieval_endpoint,
        ]
        return {
            RetrievalChoices.MIX: default,
            RetrievalChoices.MIX_TOPS: [
                user_retrieval.filter_retrieval_endpoint,
                user_retrieval.trend_release_date_retrieval_endpoint,
                user_retrieval.trend_creation_date_retrieval_endpoint,
            ],
            RetrievalChoices.MIX_RECOMMENDATION: [
                user_retrieval.recommendation_retrieval_endpoint,
                user_retrieval.filter_retrieval_endpoint,
            ],
            RetrievalChoices.RECOMMENDATION: [
                user_retrieval.recommendation_retrieval_endpoint,
            ],
            RetrievalChoices.RAW_RECOMMENDATION: [
                user_retrieval.recommendation_retrieval_endpoint
            ],
            RetrievalChoices.TOPS: [
                user_retrieval.filter_retrieval_endpoint,
            ],
        }.get(model_type, default)
