from huggy.core.endpoint.ranking_endpoint import (
    DistanceRankingEndpoint,
    ItemRankRankingEndpoint,
    ModelRankingEndpoint,
    NoPopularModelRankingEndpoint,
)
from huggy.core.model_selection.endpoint import RankingEndpointName

user_ranking_endpoint = ModelRankingEndpoint(
    endpoint_name=RankingEndpointName.recommendation_user_ranking, size=50, cached=False
)

user_distance_ranking_endpoint = DistanceRankingEndpoint(
    endpoint_name=RankingEndpointName.recommendation_user_ranking, size=50, cached=False
)

no_popular_ranking_endpoint = NoPopularModelRankingEndpoint(
    endpoint_name=RankingEndpointName.recommendation_user_ranking, size=50, cached=False
)

off_ranking_endpoint = ItemRankRankingEndpoint(
    endpoint_name=RankingEndpointName.recommendation_user_ranking, size=50, cached=False
)
