from huggy.core.endpoint.retrieval_endpoint import (
    BookingNumberRetrievalEndpoint,
    CreationTrendRetrievalEndpoint,
    RecommendationRetrievalEndpoint,
    ReleaseTrendRetrievalEndpoint,
)
from huggy.core.model_selection.endpoint import RetrievalEndpointName

filter_retrieval_endpoint = BookingNumberRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval,
    size=150,
    use_cache=True,
)

recommendation_retrieval_endpoint = RecommendationRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval,
    size=150,
    use_cache=True,
)

trend_release_date_retrieval_endpoint = ReleaseTrendRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval,
    size=150,
    use_cache=True,
)

trend_creation_date_retrieval_endpoint = CreationTrendRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval,
    size=150,
    use_cache=True,
)

# version B
filter_retrieval_endpoint_version_b = BookingNumberRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval_version_b,
    size=150,
    use_cache=True,
)

recommendation_retrieval_endpoint_version_b = RecommendationRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval_version_b,
    size=150,
    use_cache=True,
)

trend_release_date_retrieval_endpoint_version_b = ReleaseTrendRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval_version_b,
    size=150,
    use_cache=True,
)

trend_creation_date_retrieval_endpoint_version_b = CreationTrendRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval_version_b,
    size=150,
    use_cache=True,
)
