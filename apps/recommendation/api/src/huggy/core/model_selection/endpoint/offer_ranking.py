from huggy.core.endpoint.ranking_endpoint import (
    ModelRankingEndpoint,
)
from huggy.utils.env_vars import SIMILAR_OFFER_RANKING_ENDPOINT_NAME

offer_ranking_endpoint = ModelRankingEndpoint(
    endpoint_name=SIMILAR_OFFER_RANKING_ENDPOINT_NAME,
    size=50,
    use_cache=False,
)
