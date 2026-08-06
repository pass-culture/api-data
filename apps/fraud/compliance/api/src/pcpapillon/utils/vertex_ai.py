from google.cloud import aiplatform
from loguru import logger

from pcpapillon.utils.constants import GCP_PROJECT
from pcpapillon.utils.env_vars import GCP_LOCATION


def retrieve_vertex_ai_endpoint(
    project: str, location: str, endpoint_resource_name: str
) -> aiplatform.Endpoint:
    aiplatform.init(project=project, location=location)
    endpoints = aiplatform.Endpoint.list(
        filter=f'display_name="{endpoint_resource_name}"'
    )

    if not endpoints:
        raise ValueError(
            f"No endpoint found with display name: '{endpoint_resource_name}'"
        )
    if len(endpoints) > 1:
        logger.warning(
            f"Multiple endpoints found with name '{endpoint_resource_name}'. Using the first one."
        )

    logger.info(f"Found Endpoint ID: {endpoints[0].name}")
    return endpoints[0]


def run_vertex_ai_endpoint_prediction(
    endpoint_resource_name: str, instances: list
) -> list:
    target_endpoint = retrieve_vertex_ai_endpoint(
        GCP_PROJECT, GCP_LOCATION, endpoint_resource_name
    )
    response = target_endpoint.predict(instances=instances)
    logger.info(f"Prediction results: {response.predictions}")
    return response.predictions[0]
