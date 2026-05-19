from typing import Any

from aiocache import Cache
from aiocache import cached
from fastapi import HTTPException
from google.api_core import exceptions as gcp_exceptions
from google.api_core.client_options import ClientOptions
from google.cloud import aiplatform_v1
from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value

from config import settings
from services.logger import logger
from utils.benchmark import log_execution_time


class VertexService:
    """
    Infrastructure service responsible for communicating with Google Cloud Vertex AI endpoints.

    This service handles strictly the network layer: TLS handshakes, gRPC channel
    caching, Protobuf instantiation, and GCP authentication errors.
    """

    def __init__(self, endpoint_name: str, location: str = "europe-west1"):
        self.project_id = settings.GCP_PROJECT
        self.endpoint_name = endpoint_name
        self.location = location
        self.api_endpoint = f"{location}-aiplatform.googleapis.com"
        self.client_options = ClientOptions(api_endpoint=self.api_endpoint)

    @cached(ttl=600, cache=Cache.MEMORY)
    async def _get_cached_prediction_client(self) -> aiplatform_v1.PredictionServiceAsyncClient:
        """Instantiates and caches the gRPC prediction client."""
        return aiplatform_v1.PredictionServiceAsyncClient(client_options=self.client_options)

    @cached(ttl=600, cache=Cache.MEMORY)
    async def _get_cached_endpoint_service_client(self) -> aiplatform_v1.EndpointServiceAsyncClient:
        """Instantiates and caches the gRPC endpoint management client."""
        return aiplatform_v1.EndpointServiceAsyncClient(client_options=self.client_options)

    @cached(ttl=600, cache=Cache.MEMORY)
    async def _resolve_endpoint_resource_path(self, display_name: str) -> str:
        """
        Dynamically finds the fully qualified GCP resource name for an endpoint.

        Vertex AI requires the exact numeric ID path (e.g., 'projects/123/locations/.../endpoints/456').
        This function looks it up using the human-readable 'display_name' and caches the result.

        Args:
            display_name (str): The human-readable name of the endpoint in the GCP Console.

        Returns:
            str: The fully qualified GCP resource path.

        Raises:
            ValueError: If no endpoint matches the given display name.
        """
        try:
            client = await self._get_cached_endpoint_service_client()
            parent_resource = f"projects/{self.project_id}/locations/{self.location}"

            request = aiplatform_v1.ListEndpointsRequest(
                parent=parent_resource, filter=f'display_name="{display_name}"', order_by="create_time desc"
            )

            response = await client.list_endpoints(request=request)

            if not response.endpoints:
                raise ValueError(f"No Vertex Endpoint found with display_name='{display_name}'")

            return response.endpoints[0].name

        except Exception as error:
            logger.error(f"🔌 Failed to resolve endpoint {display_name}: {error!s}")
            raise error

    @log_execution_time
    async def execute_grpc_prediction(self, feature_payloads: list[dict]) -> Any:
        """
        Transforms native Python dicts to Protobuf and executes the gRPC call.

        Args:
            feature_payloads (list[dict]): The flat dictionary instances to predict on.

        Returns:
            Any: The raw Protobuf response wrapper from the Vertex AI Prediction API.
        """
        try:
            client = await self._get_cached_prediction_client()
            endpoint_resource_path = await self._resolve_endpoint_resource_path(self.endpoint_name)

            # Convert standard Python dictionaries into Protobuf 'Value' objects required by gRPC
            protobuf_instances = [json_format.ParseDict(payload, Value()) for payload in feature_payloads]

            return await client.predict(
                endpoint=endpoint_resource_path,
                instances=protobuf_instances,
                timeout=settings.VERTEX_PREDICTION_TIMEOUT,
            )

        except gcp_exceptions.ServiceUnavailable as gcp_error:
            error_msg = str(gcp_error)
            if "Reauthentication is needed" in error_msg or "gcloud auth" in error_msg:
                logger.error(f"🔐 Vertex Auth Error for {self.endpoint_name}", extra={"error": error_msg})
                raise HTTPException(
                    status_code=401,
                    detail={
                        "message": "Google Cloud authentication error. Your local token has expired.",
                        "action_required": "Open your terminal and run: gcloud auth application-default login",
                    },
                ) from gcp_error
            raise gcp_error
