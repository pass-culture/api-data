from google.cloud import aiplatform
from pcpapillon.utils.env_vars import GCP_PROJECT, ENV_SHORT_NAME


def predict_using_endpoint_name(
    project: str, location: str, endpoint_resource_name: str, instances: list
):
    """
    Calls a Vertex AI endpoint using its full resource name.
    """
    # Initialize the SDK
    aiplatform.init(project=project, location=location)

    # You can pass the full 'projects/.../endpoints/...' string
    # directly into the endpoint_name parameter.
    endpoint = aiplatform.Endpoint(endpoint_name=endpoint_resource_name)

    # Call the prediction
    try:
        response = endpoint.predict(instances=instances)

        print(f"Prediction result: {response.predictions}")
        return response
    except Exception as e:
        print(f"An error occurred: {e}")
