from huggy.core.endpoint.ranking_endpoint import (
    ModelRankingEndpoint,
)
from huggy.core.model_selection.endpoint import RankingEndpointName

user_ranking_endpoint = ModelRankingEndpoint(
    endpoint_name=RankingEndpointName.recommendation_user_ranking,
    size=50,
    use_cache=False,
)

user_ranking_endpoint_version_b = ModelRankingEndpoint(
    endpoint_name=RankingEndpointName.recommendation_user_ranking_version_b,
    size=50,
    use_cache=False,
)
