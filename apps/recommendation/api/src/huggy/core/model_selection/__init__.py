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
    RECO_MODEL_CONTEXT,
    RECO_MODEL_DESCRIPTION,
    SIMILAR_OFFER_DESCRIPTION,
    SIMILAR_OFFER_MODEL_CONTEXT,
)
from pydantic import ValidationError

RECOMMENDATION_CONFIG = RecoModelConfigurationInput(
    name=RECO_MODEL_CONTEXT,
    description=RECO_MODEL_DESCRIPTION,
    diversification_params=DiversificationParamsInput(
        diversication_type=DiversificationChoices.ON,
    ),
    warn_model_type=ModelTypeInput(
        retrieval=RetrievalChoices.MIX,
        ranking=RankingChoices.MODEL,
        query_order=QueryOrderChoices.ITEM_RANK,
    ),
    cold_start_model_type=ModelTypeInput(
        retrieval=RetrievalChoices.MIX_TOPS,
        ranking=RankingChoices.MODEL,
        query_order=QueryOrderChoices.ITEM_RANK,
    ),
    fork_params=ForkParamsInput(
        bookings_count=2,
        clicks_count=25,
        favorites_count=None,
    ),
)

SIMILAR_OFFER_CONFIG = SimilarModelConfigurationInput(
    name=SIMILAR_OFFER_MODEL_CONTEXT,
    description=SIMILAR_OFFER_DESCRIPTION,
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
)


def select_reco_model_params(model_endpoint: str, user: UserContext) -> ForkOut:
    """
    Choose the model to apply Recommendation based on user interaction.

    """
    model_fork = RECOMMENDATION_CONFIG.generate()
    return model_fork.get_user_status(user=user, model_origin=RECO_MODEL_CONTEXT)


def select_sim_model_params(
    model_endpoint: str, input_offers: Optional[list[Offer]]
) -> ForkOut:
    """
    Choose the model to apply for Similar Offers based on offer interaction.

    """
    model_fork = SIMILAR_OFFER_CONFIG.generate()
    return model_fork.get_offer_status(
        input_offers=input_offers, model_origin=SIMILAR_OFFER_MODEL_CONTEXT
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
