from huggy.core.endpoint.retrieval_endpoint import (
    OfferRetrievalEndpoint,
    OfferSemanticRetrievalEndpoint,
)
from huggy.core.model_selection.endpoint import RetrievalEndpointName

offer_retrieval_endpoint = OfferRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_user_retrieval,
    size=100,
    use_cache=True,
)

semantic_offer_retrieval_endpoint = OfferSemanticRetrievalEndpoint(
    endpoint_name=RetrievalEndpointName.recommendation_semantic_retrieval,
    size=50,
    use_cache=True,
)
