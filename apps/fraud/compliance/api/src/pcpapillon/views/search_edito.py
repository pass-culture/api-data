import traceback

from fastapi import APIRouter, Depends
from fastapi_versioning import version
from pcpapillon.utils.logging.trace import custom_logger, get_call_id, setup_trace
from pcpapillon.utils.data_model import SearchEditoInput, SearchEditoOutput
from pcpapillon.utils.vertex_ai import predict_using_endpoint_name
from pcpapillon.utils.env_vars import (
    GCP_PROJECT,
    ENV_SHORT_NAME,
    SEARCH_EDITO_MODEL_ENDPOINT_NAME,
)

search_edito_router = APIRouter(tags=["search_edito"])


@search_edito_router.post(
    "/search_edito/search",
    response_model=SearchEditoOutput,
    dependencies=[Depends(get_call_id), Depends(setup_trace)],
)
@version(1, 0)
def search_edito(search_input: SearchEditoInput):
    log_extra_data = {
        "endpoint_name": SEARCH_EDITO_MODEL_ENDPOINT_NAME,
        "search_input": search_input.dict(),
    }

    search_input_instance = SearchEditoInput(**search_input.dict())
    custom_logger.info(
        f"search_input_instance:{search_input_instance}", extra=log_extra_data
    )
    instance = {
        "instances": [
            {
                "search_query": search_input_instance.query,
                "filters_list": search_input_instance.filters,
            }
        ]
    }
    custom_logger.info(f"instance:{instance}", extra=log_extra_data)
    # offers = predict_custom_trained_model_sample(
    #     project_id=GCP_PROJECT,
    #     endpoint_id=SEARCH_EDITO_MODEL_ENDPOINT_NAME,
    #     instances=instance,
    #     location="europe-west1",
    # )
    # predict_using_endpoint_name(
    #     project=GCP_PROJECT,
    #     location="europe-west1",
    #     endpoint_resource_name=SEARCH_EDITO_MODEL_ENDPOINT_NAME,
    #     instances=instance
    # )
    offers = [
        {"id": "offer-123", "explanation": "Explication de l'offre 1"},
        {"id": "offer-124", "explanation": "Explication de l'offre 2"},
        {"id": "offer-125", "explanation": "Explication de l'offre 3"},
    ]
    custom_logger.info(
        f"offers:{SearchEditoOutput(offers=offers)}", extra=log_extra_data
    )

    return SearchEditoOutput(offers=offers)
