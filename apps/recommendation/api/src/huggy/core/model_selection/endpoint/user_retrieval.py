from huggy.core.endpoint.retrieval_endpoint import (
    BookingNumberRetrievalEndpoint,
    CreationTrendRetrievalEndpoint,
    RecommendationRetrievalEndpoint,
    ReleaseTrendRetrievalEndpoint,
)
from huggy.utils.env_vars import RECO_RETRIEVAL_ENDPOINT_NAME

filter_retrieval_endpoint = BookingNumberRetrievalEndpoint(
    endpoint_name=RECO_RETRIEVAL_ENDPOINT_NAME,
    size=150,
    use_cache=True,
)

recommendation_retrieval_endpoint = RecommendationRetrievalEndpoint(
    endpoint_name=RECO_RETRIEVAL_ENDPOINT_NAME,
    size=150,
    use_cache=True,
)

trend_release_date_retrieval_endpoint = ReleaseTrendRetrievalEndpoint(
    endpoint_name=RECO_RETRIEVAL_ENDPOINT_NAME,
    size=150,
    use_cache=True,
)

trend_creation_date_retrieval_endpoint = CreationTrendRetrievalEndpoint(
    endpoint_name=RECO_RETRIEVAL_ENDPOINT_NAME,
    size=150,
    use_cache=True,
)
