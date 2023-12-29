from huggy.core.endpoint.retrieval_endpoint import (
    FilterRetrievalEndpoint,
    RecommendationRetrievalEndpoint,
)
from huggy.core.model_selection.endpoint import RetrievalEndpointName

filter_retrieval_endpoint = FilterRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval,
    size=100,
    cached=True,
)

recommendation_retrieval_endpoint = RecommendationRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval,
    size=100,
)
