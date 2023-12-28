from huggy.core.endpoint.retrieval_endpoint import (
    OfferFilterRetrievalEndpoint,
    OfferRetrievalEndpoint,
    OfferSemanticRetrievalEndpoint,
)
from huggy.core.model_selection.endpoint import RetrievalEndpointName

offer_retrieval_endpoint = OfferRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval,
    size=150,
    fallback_endpoints=[
        RetrievalEndpointName.recommendation_semantic_retrieval,
    ],
    cached=True,
)


semantic_offer_retrieval_endpoint = OfferSemanticRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_semantic_retrieval,
    size=50,
    cached=True,
)


offer_filter_retrieval_endpoint = OfferFilterRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval,
    size=50,
    cached=True,
)
