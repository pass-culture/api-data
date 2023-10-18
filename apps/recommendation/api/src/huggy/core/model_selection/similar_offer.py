import huggy.core.model_selection.endpoint.offer_retrieval as offer_retrieval
import huggy.core.model_selection.endpoint.user_ranking as user_ranking
import huggy.core.scorer.offer as offer_scorer
from huggy.core.model_selection.model_configuration import (
    ModelConfiguration,
    diversification_off,
)

retrieval_offer = ModelConfiguration(
    name="similar_offer_model_v2",
    description="""""",
    scorer=offer_scorer.OfferScorer,
    diversification_params=diversification_off,
    retrieval_endpoints=[
        offer_retrieval.offer_retrieval_endpoint,
        offer_retrieval.semantic_offer_retrieval_endpoint,
        offer_retrieval.offer_filter_retrieval_endpoint,
    ],
    ranking_endpoint=user_ranking.user_ranking_endpoint,
)

retrieval_offer_version_b = ModelConfiguration(
    name="similar_offer_model_v2",
    description="""""",
    scorer=offer_scorer.OfferScorer,
    diversification_params=diversification_off,
    retrieval_endpoints=[
        offer_retrieval.offer_retrieval_version_b_endpoint,
        offer_retrieval.semantic_offer_retrieval_endpoint,
    ],
    ranking_endpoint=user_ranking.user_ranking_endpoint,
)


retrieval_cs_offer = ModelConfiguration(
    name="similar_cold_start_offer_model_v2",
    description="""""",
    scorer=offer_scorer.OfferScorer,
    diversification_params=diversification_off,
    retrieval_endpoints=[
        offer_retrieval.semantic_offer_retrieval_endpoint,
        offer_retrieval.offer_filter_retrieval_endpoint,
    ],
    ranking_endpoint=user_ranking.user_ranking_endpoint,
)

retrieval_filter = ModelConfiguration(
    name="similar_offer_filter_v2",
    description="""""",
    scorer=offer_scorer.OfferScorer,
    diversification_params=diversification_off,
    retrieval_endpoints=[
        offer_retrieval.offer_filter_retrieval_endpoint,
    ],
    ranking_endpoint=user_ranking.user_ranking_endpoint,
)
