import huggy.core.model_selection.endpoint.offer_retrieval as offer_retrieval
from huggy.core.endpoint.retrieval_endpoint import RetrievalEndpoint
from huggy.core.model_selection.model_configuration.configuration import (
    ModelConfigurationInput,
)
from huggy.schemas.model_selection.model_configuration import RetrievalChoices


class SimilarModelConfigurationInput(ModelConfigurationInput):
    def get_retrieval(self, model_type) -> list[RetrievalEndpoint]:
        default = [
            offer_retrieval.offer_retrieval_endpoint,
        ]
        return {
            RetrievalChoices.MIX: default,
            RetrievalChoices.MIX_VERSION_B: [
                default,
                offer_retrieval.offer_retrieval_endpoint_version_b,
            ],
            RetrievalChoices.MIX_VERSION_C: [
                offer_retrieval.offer_retrieval_endpoint_version_c
            ],
            RetrievalChoices.SEMANTIC: [
                offer_retrieval.semantic_offer_retrieval_endpoint,
            ],
            RetrievalChoices.GRAPH: [
                default,
                offer_retrieval.graph_offer_retrieval_endpoint,
            ],
        }.get(model_type, default)
