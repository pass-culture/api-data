import huggy.core.model_selection.endpoint.user_retrieval as user_retrieval
from huggy.core.endpoint.ranking_endpoint import RankingEndpoint
from huggy.core.endpoint.retrieval_endpoint import RetrievalEndpoint
from huggy.core.model_selection.endpoint import user_ranking
from huggy.core.model_selection.model_configuration.configuration import (
    ModelConfigurationInput,
)
from huggy.schemas.model_selection.model_configuration import RetrievalChoices


class RecoModelConfigurationInput(ModelConfigurationInput):
    def get_retrieval(self, model_type) -> list[RetrievalEndpoint]:
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
            RetrievalChoices.TOPS: [
                user_retrieval.filter_retrieval_endpoint,
            ],
        }.get(model_type, default)

    def get_ranking(self, model_type) -> RankingEndpoint:
        return user_ranking.user_ranking_endpoint
