from huggy.core.endpoint.retrieval_endpoint import (
    FilterRetrievalEndpoint,
    RecommendationRetrievalEndpoint,
    RawRecommendationRetrievalEndpoint,
)
from huggy.core.model_selection.endpoint import RetrievalEndpointName

RETRIEVAL_LIMIT = 500

filter_retrieval_endpoint = FilterRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval,
    size=RETRIEVAL_LIMIT,
    fallback_endpoints=[
        RetrievalEndpointName.recommendation_user_retrieval_version_b,
    ],
    cached=True,
)

recommendation_retrieval_endpoint = RecommendationRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval,
    size=RETRIEVAL_LIMIT,
    fallback_endpoints=[RetrievalEndpointName.recommendation_user_retrieval_version_b],
)

raw_recommendation_retrieval_endpoint = RawRecommendationRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval,
    size=RETRIEVAL_LIMIT,
    fallback_endpoints=[RetrievalEndpointName.recommendation_user_retrieval_version_b],
)


filter_retrieval_version_b_endpoint = FilterRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval_version_b,
    size=RETRIEVAL_LIMIT,
    fallback_endpoints=[
        RetrievalEndpointName.recommendation_user_retrieval,
    ],
    cached=True,
)

recommendation_retrieval_version_b_endpoint = RecommendationRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval_version_b,
    size=RETRIEVAL_LIMIT,
    fallback_endpoints=[RetrievalEndpointName.recommendation_user_retrieval],
)
