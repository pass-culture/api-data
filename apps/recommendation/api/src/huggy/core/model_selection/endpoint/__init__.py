import enum

from huggy.utils.env_vars import ENV_SHORT_NAME, RANKING_VERSION_B_ENDPOINT_NAME


class RetrievalEndpointName(enum.Enum):
    recommendation_user_retrieval = f"recommendation_user_retrieval_{ENV_SHORT_NAME}"
    recommendation_user_retrieval_version_b = (
        f"recommendation_user_retrieval_version_b_{ENV_SHORT_NAME}"
    )
    recommendation_user_retrieval_version_c = (
        f"recommendation_user_retrieval_version_c_{ENV_SHORT_NAME}"
    )
    recommendation_semantic_retrieval = (
        f"recommendation_semantic_retrieval_{ENV_SHORT_NAME}"
    )
    recommendation_graph_retrieval = f"recommendation_graph_retrieval_{ENV_SHORT_NAME}"


class RankingEndpointName(enum.Enum):
    recommendation_user_ranking = f"recommendation_user_ranking_{ENV_SHORT_NAME}"
    recommendation_user_ranking_version_b = RANKING_VERSION_B_ENDPOINT_NAME
