from fastapi import APIRouter, Depends
from fastapi_versioning import version
from main import custom_logger, setup_trace
from pcpapillon.core.offer_categorisation_model import (
    OfferCategorisationModel,
)
from pcpapillon.utils.data_model import (
    OfferCategorisationInput,
    OfferCategorisationOutput,
)

offer_categorisation_router = APIRouter(tags=["offer_categorisation"])


# Load Model
offer_categorisation_model = OfferCategorisationModel()
NUM_OFFERS_TO_RETURN = 3


@offer_categorisation_router.post(
    "/model/categorisation",
    response_model=OfferCategorisationOutput,
    dependencies=[Depends(setup_trace)],
)
@version(1, 0)
def model_categorisation(input: OfferCategorisationInput):
    log_extra_data = {
        "model_version": "default_model",
        "scoring_input": input.dict(),
    }

    formatted_predictions = offer_categorisation_model.predict(
        input=input,
    )

    custom_logger.info(formatted_predictions.dict(), extra=log_extra_data)
    return formatted_predictions
