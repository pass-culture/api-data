from fastapi import APIRouter, Depends
from fastapi_versioning import version
from pcpapillon.core.offer_categorisation_model import (
    OfferCategorisationModel,
)
from pcpapillon.utils.data_model import (
    OfferCategorisationInput,
    OfferCategorisationOutput,
)
from pcpapillon.utils.logging.trace import get_call_id, setup_trace

offer_categorisation_router = APIRouter(tags=["offer_categorisation"])


# Load Model
offer_categorisation_model = OfferCategorisationModel()
NUM_OFFERS_TO_RETURN = 3


@offer_categorisation_router.post(
    "/model/categorisation",
    response_model=OfferCategorisationOutput,
    dependencies=[Depends(get_call_id), Depends(setup_trace)],
)
@version(1, 0)
def model_categorisation(
    input: OfferCategorisationInput, call_id: str = Depends(get_call_id)
) -> OfferCategorisationOutput:
    formatted_predictions = offer_categorisation_model.predict(
        data=input, num_offers_to_return=NUM_OFFERS_TO_RETURN
    )

    return OfferCategorisationOutput(
        most_probable_subcategories=formatted_predictions, call_id=call_id
    )
