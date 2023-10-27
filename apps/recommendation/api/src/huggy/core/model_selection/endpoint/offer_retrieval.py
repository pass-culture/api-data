from huggy.core.endpoint.retrieval_endpoint import (
    OfferFilterRetrievalEndpoint,
    OfferRetrievalEndpoint,
    OfferSemanticRetrievalEndpoint,
)
from huggy.core.model_selection.endpoint import RetrievalEndpointName

RETRIEVAL_LIMIT = 150


offer_retrieval_endpoint = OfferRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval,
    size=RETRIEVAL_LIMIT,
    fallback_endpoints=[
        RetrievalEndpointName.recommendation_user_retrieval_version_b,
    ],
    cached=True,
)

offer_filter_retrieval_endpoint = OfferFilterRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval,
    size=RETRIEVAL_LIMIT,
    fallback_endpoints=[RetrievalEndpointName.recommendation_user_retrieval_version_b],
    cached=True,
)

semantic_offer_retrieval_endpoint = OfferSemanticRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_semantic_retrieval,
    size=RETRIEVAL_LIMIT,
    cached=True,
)

offer_retrieval_version_b_endpoint = OfferRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval_version_b,
    size=RETRIEVAL_LIMIT,
    fallback_endpoints=[
        RetrievalEndpointName.recommendation_user_retrieval,
    ],
)
