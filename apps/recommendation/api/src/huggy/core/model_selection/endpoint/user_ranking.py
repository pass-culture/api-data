from huggy.core.endpoint.ranking_endpoint import (
    ModelRankingEndpoint,
)
from huggy.utils.env_vars import RECO_RANKING_ENDPOINT_NAME

user_ranking_endpoint = ModelRankingEndpoint(
    endpoint_name=RECO_RANKING_ENDPOINT_NAME,
    size=50,
    use_cache=False,
)
