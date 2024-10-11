from huggy.core.endpoint.retrieval_endpoint import (
    OfferBookingNumberRetrievalEndpoint,
    OfferRetrievalEndpoint,
    OfferSemanticRetrievalEndpoint,
)
from huggy.core.model_selection.endpoint import RetrievalEndpointName

offer_retrieval_endpoint = OfferRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval,
    size=100,
    fallback_endpoints=[
        RetrievalEndpointName.recommendation_semantic_retrieval,
    ],
    use_cache=True,
)


semantic_offer_retrieval_endpoint = OfferSemanticRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_semantic_retrieval,
    size=50,
    use_cache=True,
)


offer_filter_retrieval_endpoint = OfferBookingNumberRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval,
    size=50,
    use_cache=True,
)
