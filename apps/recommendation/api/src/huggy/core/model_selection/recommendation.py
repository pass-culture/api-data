import huggy.core.model_selection.endpoint.user_ranking as user_ranking
import huggy.core.model_selection.endpoint.user_retrieval as user_retrieval
import huggy.core.scorer.offer as offer_scorer
from huggy.core.model_selection.model_configuration import (
    ModelConfiguration,
    diversification_on,
    DiversificationParams,
)

retrieval_filter = ModelConfiguration(
    name="recommendation_filter",
    description="""""",
    scorer=offer_scorer.OfferScorer,
    diversification_params=diversification_on,
    retrieval_endpoints=[user_retrieval.filter_retrieval_endpoint],
    ranking_endpoint=user_ranking.user_ranking_endpoint,
)


gtl_filter = ModelConfiguration(
    name="recommendation_filter",
    description="""""",
    scorer=offer_scorer.OfferScorer,
    diversification_params=DiversificationParams(
        is_active=True,
        is_reco_shuffled=True,
        mixing_features="search_group_name",
        order_column="offer_score",
        order_ascending=False,
        submixing_feature_dict={"LIVRES": "gtl_id"},
    ),
    retrieval_endpoints=[user_retrieval.filter_retrieval_endpoint],
    ranking_endpoint=user_ranking.user_ranking_endpoint,
)

gtl_reco = ModelConfiguration(
    name="recommendation_user",
    description="""""",
    scorer=offer_scorer.OfferScorer,
    diversification_params=DiversificationParams(
        is_active=True,
        is_reco_shuffled=True,
        mixing_features="search_group_name",
        order_column="offer_score",
        order_ascending=False,
        submixing_feature_dict={"LIVRES": "gtl_id"},
    ),
    retrieval_endpoints=[
        user_retrieval.filter_retrieval_endpoint,
        user_retrieval.recommendation_retrieval_endpoint,
    ],
    ranking_endpoint=user_ranking.user_ranking_endpoint,
)


retrieval_reco = ModelConfiguration(
    name="recommendation_user",
    description="""""",
    scorer=offer_scorer.OfferScorer,
    diversification_params=diversification_on,
    retrieval_endpoints=[
        user_retrieval.filter_retrieval_endpoint,
        user_retrieval.recommendation_retrieval_endpoint,
    ],
    ranking_endpoint=user_ranking.user_ranking_endpoint,
)


retrieval_filter_version_b = ModelConfiguration(
    name="recommendation_filter",
    description="""""",
    scorer=offer_scorer.OfferScorer,
    diversification_params=diversification_on,
    retrieval_endpoints=[user_retrieval.filter_retrieval_version_b_endpoint],
    ranking_endpoint=user_ranking.user_ranking_endpoint,
)

retrieval_reco_version_b = ModelConfiguration(
    name="recommendation_user",
    description="""""",
    scorer=offer_scorer.OfferScorer,
    diversification_params=diversification_on,
    retrieval_endpoints=[
        user_retrieval.filter_retrieval_version_b_endpoint,
        user_retrieval.recommendation_retrieval_version_b_endpoint,
    ],
    ranking_endpoint=user_ranking.user_ranking_endpoint,
)
