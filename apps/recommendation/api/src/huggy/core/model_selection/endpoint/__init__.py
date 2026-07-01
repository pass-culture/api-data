import enum

from huggy.utils.env_vars import ENV_SHORT_NAME, RANKING_VERSION_B_ENDPOINT_NAME


class RetrievalEndpointName(enum.Enum):
    recommendation_user_retrieval = "recommendation_user_retrieval_stg"
    recommendation_user_retrieval_version_b = (
        "recommendation_user_retrieval_version_b_stg"
    )
    recommendation_user_retrieval_version_c = (
        "recommendation_user_retrieval_version_c_stg"
    )
    recommendation_semantic_retrieval = "recommendation_semantic_retrieval_stg"
    recommendation_graph_retrieval = "recommendation_graph_retrieval_stg"


class RankingEndpointName(enum.Enum):
    recommendation_user_ranking = "recommendation_user_ranking_stg"
    recommendation_user_ranking_version_b = RANKING_VERSION_B_ENDPOINT_NAME
