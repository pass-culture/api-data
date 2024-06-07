from fastapi import APIRouter, Depends
from fastapi_versioning import version
from main import custom_logger, setup_trace
from pcpapillon.utils.data_model import (
    OfferCategorisationInput,
    OfferCategorisationOutput,
)

offer_categorisation_router = APIRouter(tags=["offer_categorisation"])


@offer_categorisation_router.post(
    "/model/offer_categorisation/scoring",
    response_model=OfferCategorisationOutput,
    dependencies=[Depends(setup_trace)],
)
@version(1, 0)
def model_compliance_scoring(item: OfferCategorisationInput):
    log_extra_data = {
        "model_version": "default_model",
        "offer_id": item.dict()["offer_id"],
        "scoring_input": item.dict(),
    }

    mocked_data = {
        "offer_id": "mocked_offer_id",
        "most_probable_categories": ["mocked_category_1", "mocked_category_2"],
    }
    custom_logger.info(mocked_data, extra=log_extra_data)
    return mocked_data
