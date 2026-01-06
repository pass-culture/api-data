from fastapi import APIRouter, Body, Depends
from fastapi_versioning import version

from pcpapillon.utils.data_model import SearchEditoInput, SearchEditoOutput
from pcpapillon.utils.env_vars import (
    GCP_PROJECT,
    SEARCH_EDITO_MODEL_ENDPOINT_NAME,
)
from pcpapillon.utils.logging.trace import custom_logger, get_call_id, setup_trace
from pcpapillon.utils.vertex_ai import predict_using_endpoint_name

search_edito_router = APIRouter(tags=["search_edito"])


@search_edito_router.post(
    "/search_edito/search",
    response_model=SearchEditoOutput,
    dependencies=[Depends(get_call_id), Depends(setup_trace)],
)
@version(1, 0)
def search_edito(
    search_input: SearchEditoInput = Body(
        ...,
        example={
            "query": "nature et bien être",
            "filters": [
                {"column": "last_stock_price", "operator": "in", "value": [10, 50]}
            ],
        },
        description="Input parameters for the edito search",
    ),
):
    """
    Semantic search in passculture catalog offers with editorial filtering

    - **query**: The search query string.
    - **filters**: Optional list of filters to refine the search.
    """
    log_extra_data = {
        "endpoint_name": SEARCH_EDITO_MODEL_ENDPOINT_NAME,
        "search_input": search_input,
    }
    payload = {"search_query": search_input.query}
    if search_input.filters:
        payload["filters_list"] = [
            {
                "column": f.column.value if hasattr(f.column, "value") else f.column,
                "operator": f.operator,
                "value": f.value,
            }
            for f in search_input.filters
        ]
    custom_logger.info(f"parsed payload:{payload}", extra=log_extra_data)
    predictions = predict_using_endpoint_name(
        project=GCP_PROJECT,
        location="europe-west1",
        endpoint_resource_name=SEARCH_EDITO_MODEL_ENDPOINT_NAME,
        instances=[payload],
    )
    return SearchEditoOutput(results=predictions)
