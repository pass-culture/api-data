from huggy.core.endpoint.retrieval_endpoint import (
    OfferRetrievalEndpoint,
    OfferSemanticRetrievalEndpoint,
)
from huggy.utils.env_vars import SIMILAR_OFFER_RETRIEVAL_ENDPOINT_NAME

offer_retrieval_endpoint = OfferRetrievalEndpoint(
    endpoint_name=SIMILAR_OFFER_RETRIEVAL_ENDPOINT_NAME,
    size=100,
    use_cache=True,
)

semantic_offer_retrieval_endpoint = OfferSemanticRetrievalEndpoint(
    endpoint_name=SIMILAR_OFFER_RETRIEVAL_ENDPOINT_NAME,
    size=50,
    use_cache=True,
)
