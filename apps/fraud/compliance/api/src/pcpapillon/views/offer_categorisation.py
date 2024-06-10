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
    "/model/offer_categorisation/scoring",
    response_model=OfferCategorisationOutput,
    dependencies=[Depends(setup_trace)],
)
@version(1, 0)
def model_compliance_scoring(input: OfferCategorisationInput):
    log_extra_data = {
        "model_version": "default_model",
        "offer_id": input.dict()["offer_id"],
        "scoring_input": input.dict(),
    }

    preprocessed_input = offer_categorisation_model.preprocess(input=input)

    probabilities = offer_categorisation_model.predict(
        preprocessed_input=preprocessed_input,
    )

    most_probable_categories = offer_categorisation_model.postprocess(
        probabilities=probabilities,
        n_top=NUM_OFFERS_TO_RETURN,
    )

    output_data = {
        "offer_id": input.offer_id,
        "most_probable_categories": most_probable_categories,
    }
    custom_logger.info(output_data, extra=log_extra_data)
    return output_data
