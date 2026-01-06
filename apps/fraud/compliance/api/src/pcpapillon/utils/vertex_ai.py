from google.cloud import aiplatform
from utils.env_vars import GCP_PROJECT


def retrieve_vertex_ai_endpoint(
    project: str, location: str, endpoint_resource_name: str
):
    """
    Retrieves a Vertex AI endpoint using its full resource name.
    """
    # Initialize the SDK
    aiplatform.init(project=project, location=location)
    endpoints = aiplatform.Endpoint.list(
        filter=f'display_name="{endpoint_resource_name}"'
    )

    if not endpoints:
        raise ValueError(
            f"No endpoint found with display name: '{endpoint_resource_name}'"
        )
    # Warning: Display names are not unique. This script selects the first match.
    if len(endpoints) > 1:
        print(
            f"Warning: Multiple endpoints found with name '{endpoint_resource_name}'. Using the first one found."
        )

    target_endpoint = endpoints[0]

    print(f"Found Endpoint ID: {target_endpoint.name}")
    return target_endpoint


def run_vertex_ai_endpoint_prediction(endpoint_resource_name: str, instances: list):
    """
    Calls a Vertex AI endpoint using its full resource name.
    """

    # 2. Retrieve the endpoint
    target_endpoint = retrieve_vertex_ai_endpoint(
        GCP_PROJECT, "europe-west1", endpoint_resource_name
    )

    # 3. Make the prediction
    try:
        response = target_endpoint.predict(instances=instances)
        print(f"Prediction results: {response.predictions}")
        return response.predictions[0]
    except Exception as e:
        print(f"Prediction failed: {e}")
        return None
