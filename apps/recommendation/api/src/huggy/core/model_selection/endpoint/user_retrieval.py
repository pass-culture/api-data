from huggy.core.endpoint.retrieval_endpoint import (
    FilterRetrievalEndpoint,
    RecommendationRetrievalEndpoint,
)
from huggy.core.model_selection.endpoint import RetrievalEndpointName

RETRIEVAL_LIMIT = 250

filter_retrieval_endpoint = FilterRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval,
    size=RETRIEVAL_LIMIT,
    cached=True,
)

recommendation_retrieval_endpoint = RecommendationRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval,
    size=RETRIEVAL_LIMIT,
)
