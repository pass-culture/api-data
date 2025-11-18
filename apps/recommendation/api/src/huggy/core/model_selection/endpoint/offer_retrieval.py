from huggy.core.endpoint.retrieval_endpoint import (
    OfferBookingNumberRetrievalEndpoint,
    OfferRetrievalEndpoint,
    OfferSemanticRetrievalEndpoint,
)
from huggy.core.model_selection.endpoint import RetrievalEndpointName

offer_retrieval_endpoint = OfferRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval.value,
    size=100,
    use_cache=True,
)

offer_retrieval_endpoint_version_b = OfferRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval_version_b.value,
    size=100,
    use_cache=True,
)

offer_retrieval_endpoint_version_c = OfferRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval_version_c.value,
    size=100,
    use_cache=True,
)

semantic_offer_retrieval_endpoint = OfferSemanticRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_semantic_retrieval.value,
    size=50,
    use_cache=True,
)


offer_filter_retrieval_endpoint = OfferBookingNumberRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval.value,
    size=50,
    use_cache=True,
)
