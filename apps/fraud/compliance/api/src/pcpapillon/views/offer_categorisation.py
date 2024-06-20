from fastapi import APIRouter, Depends
from fastapi_versioning import version
from main import custom_logger, setup_trace
from pcpapillon.core.offer_categorisation.offer_categorisation_model import (
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

    most_probable_subcategories = offer_categorisation_model.predict(
        input=input,
        num_offers_to_return=NUM_OFFERS_TO_RETURN,
    )

    output_data = {
        "offer_id": input.offer_id,
        "most_probable_subcategories": most_probable_subcategories,
    }
    custom_logger.info(output_data, extra=log_extra_data)
    return output_data
