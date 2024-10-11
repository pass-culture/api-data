from typing import Optional

from fastapi.exceptions import HTTPException
from huggy.core.model_selection.model_configuration.configuration import (
    ForkOut,
    ModelEnpointInput,
)
from huggy.core.model_selection.model_configuration.recommendation import (
    RecoModelConfigurationInput,
)
from huggy.core.model_selection.model_configuration.similar_offer import (
    SimilarModelConfigurationInput,
)
from huggy.schemas.model_selection.model_configuration import (
    DiversificationChoices,
    DiversificationParamsInput,
    ForkParamsInput,
    ModelTypeInput,
    QueryOrderChoices,
    RankingChoices,
    RetrievalChoices,
)
from huggy.schemas.offer import Offer
from huggy.schemas.user import UserContext
from huggy.schemas.utils import parse_input
from huggy.utils.env_vars import (
    DEFAULT_RECO_MODEL_DESCRIPTION,
    DEFAULT_SIMILAR_OFFER_DESCRIPTION,
    RECO_MODEL_CONTEXT,
    SIMILAR_OFFER_MODEL_CONTEXT,
    VERSION_B_RECO_MODEL_DESCRIPTION,
    VERSION_B_SIMILAR_OFFER_DESCRIPTION,
)
from pydantic import ValidationError

RECOMMENDATION_ENDPOINTS = {
    # Default endpoint
    "default": RecoModelConfigurationInput(
        name="default",
        description=DEFAULT_RECO_MODEL_DESCRIPTION,
        diversification_params=DiversificationParamsInput(
            diversication_type=DiversificationChoices.ON,
        ),
        warn_model_type=ModelTypeInput(
            retrieval=RetrievalChoices.MIX,
            ranking=RankingChoices.MODEL,
            query_order=QueryOrderChoices.ITEM_RANK,
        ),
        cold_start_model_type=ModelTypeInput(
            retrieval=RetrievalChoices.TOPS,
            ranking=RankingChoices.MODEL,
            query_order=QueryOrderChoices.ITEM_RANK,
        ),
        fork_params=ForkParamsInput(
            bookings_count=2,
            clicks_count=25,
            favorites_count=None,
        ),
    ),
    "version_b": RecoModelConfigurationInput(
        name="version_b",
        description=VERSION_B_RECO_MODEL_DESCRIPTION,
        diversification_params=DiversificationParamsInput(
            diversication_type=DiversificationChoices.ON,
        ),
        warn_model_type=ModelTypeInput(
            retrieval=RetrievalChoices.MIX,
            ranking=RankingChoices.VERSION_B,
            query_order=QueryOrderChoices.ITEM_RANK,
        ),
        cold_start_model_type=ModelTypeInput(
            retrieval=RetrievalChoices.TOPS,
            ranking=RankingChoices.VERSION_B,
            query_order=QueryOrderChoices.ITEM_RANK,
        ),
        fork_params=ForkParamsInput(
            bookings_count=2,
            clicks_count=25,
            favorites_count=None,
        ),
    ),
    "user_distance": RecoModelConfigurationInput(
        name="user_distance",
        description="""Rank by offer distance.""",
        diversification_params=DiversificationParamsInput(
            diversication_type=DiversificationChoices.ON,
        ),
        warn_model_type=ModelTypeInput(
            retrieval=RetrievalChoices.MIX,
            ranking=RankingChoices.DISTANCE,
            query_order=QueryOrderChoices.ITEM_RANK,
        ),
        cold_start_model_type=ModelTypeInput(
            retrieval=RetrievalChoices.TOPS,
            ranking=RankingChoices.DISTANCE,
            query_order=QueryOrderChoices.ITEM_RANK,
        ),
        fork_params=ForkParamsInput(
            bookings_count=1,
            clicks_count=25,
            favorites_count=None,
        ),
    ),
    "top_offers": RecoModelConfigurationInput(
        name="top_offers",
        description="""Force top offers configuration.""",
        diversification_params=DiversificationParamsInput(
            diversication_type=DiversificationChoices.ON,
        ),
        warn_model_type=ModelTypeInput(
            retrieval=RetrievalChoices.TOPS,
            ranking=RankingChoices.MODEL,
            query_order=QueryOrderChoices.ITEM_RANK,
        ),
        cold_start_model_type=ModelTypeInput(
            retrieval=RetrievalChoices.TOPS,
            ranking=RankingChoices.MODEL,
            query_order=QueryOrderChoices.ITEM_RANK,
        ),
        fork_params=ForkParamsInput(
            bookings_count=None,
            clicks_count=None,
            favorites_count=None,
        ),
    ),
    "cold_start": RecoModelConfigurationInput(
        name="cold_start",
        description="""Force cold_start configuration.""",
        diversification_params=DiversificationParamsInput(
            diversication_type=DiversificationChoices.ON,
        ),
        warn_model_type=ModelTypeInput(
            retrieval=RetrievalChoices.TOPS,
            ranking=RankingChoices.MODEL,
            query_order=QueryOrderChoices.ITEM_RANK,
        ),
        cold_start_model_type=ModelTypeInput(
            retrieval=RetrievalChoices.TOPS,
            ranking=RankingChoices.MODEL,
            query_order=QueryOrderChoices.ITEM_RANK,
        ),
        fork_params=ForkParamsInput(
            bookings_count=None,
            clicks_count=None,
            favorites_count=None,
        ),
    ),
    "force_algo": RecoModelConfigurationInput(
        name="force_algo",
        description="""Force algo configuration.""",
        diversification_params=DiversificationParamsInput(
            diversication_type=DiversificationChoices.ON,
        ),
        warn_model_type=ModelTypeInput(
            retrieval=RetrievalChoices.RECOMMENDATION,
            ranking=RankingChoices.MODEL,
            query_order=QueryOrderChoices.ITEM_RANK,
        ),
        cold_start_model_type=ModelTypeInput(
            retrieval=RetrievalChoices.RECOMMENDATION,
            ranking=RankingChoices.MODEL,
            query_order=QueryOrderChoices.ITEM_RANK,
        ),
        fork_params=ForkParamsInput(
            bookings_count=0,
        ),
    ),
}


SIMILAR_OFFER_ENDPOINTS = {
    "default": SimilarModelConfigurationInput(
        name="default",
        description=DEFAULT_SIMILAR_OFFER_DESCRIPTION,
        diversification_params=DiversificationParamsInput(
            diversication_type=DiversificationChoices.OFF,
        ),
        warn_model_type=ModelTypeInput(
            retrieval=RetrievalChoices.MIX,
            ranking=RankingChoices.MODEL,
            query_order=QueryOrderChoices.ITEM_RANK,
        ),
        cold_start_model_type=ModelTypeInput(
            retrieval=RetrievalChoices.MIX,
            ranking=RankingChoices.MODEL,
            query_order=QueryOrderChoices.ITEM_RANK,
        ),
        fork_params=ForkParamsInput(
            bookings_count=0,
        ),
    ),
    "version_b": SimilarModelConfigurationInput(
        name="version_b",
        description=VERSION_B_SIMILAR_OFFER_DESCRIPTION,
        diversification_params=DiversificationParamsInput(
            diversication_type=DiversificationChoices.OFF,
        ),
        warn_model_type=ModelTypeInput(
            retrieval=RetrievalChoices.MIX,
            ranking=RankingChoices.VERSION_B,
            query_order=QueryOrderChoices.ITEM_RANK,
        ),
        cold_start_model_type=ModelTypeInput(
            retrieval=RetrievalChoices.MIX,
            ranking=RankingChoices.VERSION_B,
            query_order=QueryOrderChoices.ITEM_RANK,
        ),
        fork_params=ForkParamsInput(
            bookings_count=0,
        ),
    ),
    "user_distance": SimilarModelConfigurationInput(
        name="user_distance",
        description="""Similar offers based on distance ranking.""",
        diversification_params=DiversificationParamsInput(
            diversication_type=DiversificationChoices.OFF,
        ),
        warn_model_type=ModelTypeInput(
            retrieval=RetrievalChoices.MIX,
            ranking=RankingChoices.DISTANCE,
            query_order=QueryOrderChoices.ITEM_RANK,
        ),
        cold_start_model_type=ModelTypeInput(
            retrieval=RetrievalChoices.MIX,
            ranking=RankingChoices.DISTANCE,
            query_order=QueryOrderChoices.ITEM_RANK,
        ),
        fork_params=ForkParamsInput(
            bookings_count=0,
        ),
    ),
}


def select_reco_model_params(model_endpoint: str, user: UserContext) -> ForkOut:
    """
    Choose the model to apply Recommendation based on user interaction.

    """

    model_endpoint = parse_model_enpoint(model_endpoint, model_type="recommendation")
    model_name = model_endpoint.model_name
    if model_endpoint.custom_configuration is not None:
        model_fork = model_endpoint.custom_configuration.generate()
    else:
        if model_name not in list(RECOMMENDATION_ENDPOINTS.keys()):
            model_name = RECO_MODEL_CONTEXT
        model_fork = RECOMMENDATION_ENDPOINTS[model_name].generate()
    return model_fork.get_user_status(user=user, model_origin=model_name)


def select_sim_model_params(
    model_endpoint: str, input_offers: Optional[list[Offer]]
) -> ForkOut:
    """
    Choose the model to apply for Similar Offers based on offer interaction.

    """

    model_endpoint = parse_model_enpoint(model_endpoint, model_type="similar_offer")
    model_name = model_endpoint.model_name
    if model_endpoint.custom_configuration is not None:
        model_fork = model_endpoint.custom_configuration.generate()
    else:
        if model_name not in list(SIMILAR_OFFER_ENDPOINTS.keys()):
            model_name = SIMILAR_OFFER_MODEL_CONTEXT
        model_fork = SIMILAR_OFFER_ENDPOINTS[model_name].generate()
    return model_fork.get_offer_status(
        input_offers=input_offers, model_origin=model_name
    )


def parse_model_enpoint(model_endpoint: str, model_type: str) -> ModelEnpointInput:
    """
    Returns a custom generated modelEndpoint or the defaults.
    model_endpoint can be a utf-8 encode hex json. or a json string.

    """
    model_name = model_endpoint
    custom_configuration = None
    if model_endpoint is not None:
        try:
            json = parse_input(model_endpoint)
            if isinstance(json, dict):
                custom_configuration = {
                    "similar_offer": SimilarModelConfigurationInput.parse_obj(json),
                    "recommendation": RecoModelConfigurationInput.parse_obj(json),
                }[model_type]
                return ModelEnpointInput(
                    model_name=custom_configuration.name,
                    custom_configuration=custom_configuration,
                )
        except ValidationError as exc:
            raise HTTPException(422, detail=f"Model Validation Error {exc.errors()}")
    return ModelEnpointInput(model_name=model_name, custom_configuration=None)
