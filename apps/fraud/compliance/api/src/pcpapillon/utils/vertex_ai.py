from google.cloud import aiplatform


def predict_using_endpoint_name(
    project: str, location: str, endpoint_resource_name: str, instances: list
):
    """
    Calls a Vertex AI endpoint using its full resource name.
    """
    # Initialize the SDK
    aiplatform.init(project=project, location=location)

    # 2. Search for the endpoint using a filter
    # We use the filter string to query exactly for the display name
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

    # 3. Make the prediction
    try:
        response = target_endpoint.predict(instances=instances)
        print(f"Prediction results: {response.predictions}")
        return response.predictions[0]
    except Exception as e:
        print(f"Prediction failed: {e}")
        return None
