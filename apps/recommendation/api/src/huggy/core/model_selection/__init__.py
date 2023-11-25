from huggy.core.model_selection.model_configuration.configuration import (
    ModelEnpointInput,
    ModelConfigurationInput,
    ModelConfiguration,
    RankingChoices,
    DiversificationChoices,
)
from huggy.core.model_selection.model_configuration.similar_offer import (
    SimilarModelConfigurationInput,
    SimOffersRetrievalChoices,
)
from huggy.core.model_selection.model_configuration.recommendation import (
    RecoModelConfigurationInput,
    RecoRetrievalChoices,
)
from huggy.core.model_selection.model_configuration.configuration import ForkOut
from huggy.schemas.offer import Offer
from huggy.schemas.user import UserContext
from huggy.schemas.model_selection.model_configuration import (
    ModelTypeInput,
    ForkParamsInput,
)
from huggy.utils.env_vars import DEFAULT_RECO_MODEL, DEFAULT_SIMILAR_OFFER_MODEL
import typing as t


RECOMMENDATION_ENDPOINTS = {
    # Default endpoint
    "default": RecoModelConfigurationInput(
        name="default",
        description="""Default Configuration""",
        diversification_params=DiversificationChoices.ON,
        warn_model_type=ModelTypeInput(
            retrieval=RecoRetrievalChoices.MIX,
            ranking=RankingChoices.DEFAULT,
            query_order="item_rank",
        ),
        cold_start_model_type=ModelTypeInput(
            retrieval=RecoRetrievalChoices.TOPS,
            ranking=RankingChoices.DEFAULT,
            query_order="item_rank",
        ),
        fork_params=ForkParamsInput(
            bookings_count=1,
            clicks_count=25,
            favorites_count=None,
        ),
    ),
    "top_offers": RecoModelConfigurationInput(
        name="top_offers",
        description="""Force top offers configuration""",
        diversification_params=DiversificationChoices.ON,
        warn_model_type=ModelTypeInput(
            retrieval=RecoRetrievalChoices.TOPS,
            ranking=RankingChoices.DEFAULT,
            query_order="item_rank",
        ),
        cold_start_model_type=ModelTypeInput(
            retrieval=RecoRetrievalChoices.TOPS,
            ranking=RankingChoices.DEFAULT,
            query_order="item_rank",
        ),
        fork_params=ForkParamsInput(
            bookings_count=None,
            clicks_count=None,
            favorites_count=None,
        ),
    ),
    "cold_start": RecoModelConfigurationInput(
        name="cold_start",
        description="""Force cold_start configuration""",
        diversification_params=DiversificationChoices.ON,
        warn_model_type=ModelTypeInput(
            retrieval=RecoRetrievalChoices.TOPS,
            ranking=RankingChoices.DEFAULT,
            query_order="item_rank",
        ),
        cold_start_model_type=ModelTypeInput(
            retrieval=RecoRetrievalChoices.TOPS,
            ranking=RankingChoices.DEFAULT,
            query_order="item_rank",
        ),
        fork_params=ForkParamsInput(
            bookings_count=None,
            clicks_count=None,
            favorites_count=None,
        ),
    ),
    "force_algo": RecoModelConfigurationInput(
        name="default_algo",
        description="""Force algo configuration""",
        diversification_params=DiversificationChoices.ON,
        warn_model_type=ModelTypeInput(
            retrieval=RecoRetrievalChoices.RECOMMENDATION,
            ranking=RankingChoices.DEFAULT,
            query_order="item_rank",
        ),
        cold_start_model_type=ModelTypeInput(
            retrieval=RecoRetrievalChoices.RECOMMENDATION,
            ranking=RankingChoices.DEFAULT,
            query_order="item_rank",
        ),
        fork_params=ForkParamsInput(
            bookings_count=0,
            clicks_count=0,
            favorites_count=0,
        ),
    ),
}


SIMILAR_OFFER_ENDPOINTS = {
    "default": SimilarModelConfigurationInput(
        name="default",
        description="""Default similar offer configuration""",
        diversification_params="off",
        warn_model_type=ModelTypeInput(
            retrieval=SimOffersRetrievalChoices.MIX,
            ranking=RankingChoices.DEFAULT,
            query_order="item_rank",
        ),
        cold_start_model_type=ModelTypeInput(
            retrieval=SimOffersRetrievalChoices.MIX,
            ranking=RankingChoices.DEFAULT,
            query_order="item_rank",
        ),
        fork_params=ForkParamsInput(
            bookings_count=0,
        ),
    )
}


def select_reco_model_params(
    model_endpoint: ModelEnpointInput, user: UserContext
) -> ForkOut:
    """Choose the model to apply Recommendation based on user interaction"""
    if model_endpoint.custom_configuration is not None:
        origin = "custom"
        model_fork = model_endpoint.custom_configuration.generate()
    else:
        origin = "default"
        if model_endpoint not in list(RECOMMENDATION_ENDPOINTS.keys()):
            model_endpoint = DEFAULT_RECO_MODEL
        model_fork = RECOMMENDATION_ENDPOINTS[model_endpoint].generate()

    return model_fork.get_user_status(user=user, model_origin=origin)


def select_sim_model_params(model_endpoint: ModelEnpointInput, offer: Offer) -> ForkOut:
    """Choose the model to apply for Similar Offers based on offer interaction"""
    if model_endpoint.custom_configuration is not None:
        origin = "custom"
        model_fork = model_endpoint.custom_configuration.generate()
    else:
        origin = "default"
        if model_endpoint not in list(SIMILAR_OFFER_ENDPOINTS.keys()):
            model_endpoint = DEFAULT_SIMILAR_OFFER_MODEL
        model_fork = SIMILAR_OFFER_ENDPOINTS[model_endpoint].generate()
    return model_fork.get_offer_status(offer=offer, model_origin=origin)
