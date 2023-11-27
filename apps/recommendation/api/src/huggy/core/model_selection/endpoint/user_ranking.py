from huggy.core.endpoint.ranking_endpoint import (
    ModelRankingEndpoint,
    DistanceRankingEndpoint,
    NoPopularModelRankingEndpoint,
    ItemRankRankingEndpoint,
)
from huggy.core.model_selection.endpoint import RankingEndpointName


user_ranking_endpoint = ModelRankingEndpoint(
    endpoint_name=RankingEndpointName.recommendation_user_ranking,
    size=50,
)

user_distance_ranking_endpoint = DistanceRankingEndpoint(
    endpoint_name=RankingEndpointName.recommendation_user_ranking,
    size=50,
)

no_popular_ranking_endpoint = NoPopularModelRankingEndpoint(
    endpoint_name=RankingEndpointName.recommendation_user_ranking,
    size=50,
)

off_ranking_endpoint = ItemRankRankingEndpoint(
    endpoint_name=RankingEndpointName.recommendation_user_ranking,
    size=50,
)
