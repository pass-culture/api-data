import huggy.core.model_selection.endpoint.offer_retrieval as offer_retrieval
from huggy.core.endpoint.ranking_endpoint import RankingEndpoint
from huggy.core.endpoint.retrieval_endpoint import RetrievalEndpoint
from huggy.core.model_selection.endpoint import offer_ranking
from huggy.core.model_selection.model_configuration.configuration import (
    ModelConfigurationInput,
)


class SimilarModelConfigurationInput(ModelConfigurationInput):
    def get_retrieval(self, model_type) -> list[RetrievalEndpoint]:
        return [
            offer_retrieval.offer_retrieval_endpoint,
        ]

    def get_ranking(self, model_type) -> RankingEndpoint:
        return offer_ranking.offer_ranking_endpoint
