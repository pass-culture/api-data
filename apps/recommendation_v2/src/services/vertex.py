import traceback
from typing import Any

from aiocache import Cache
from aiocache import cached
from google.api_core.client_options import ClientOptions
from google.cloud import aiplatform_v1
from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value
from pydantic import BaseModel

from config import settings
from schemas.vertex_prediction_item import RecommendableItem
from services.logger import logger


class VertexPredictionResult(BaseModel):
    """Encapsulates the raw response from the Retrieval Vertex Model."""

    status: str
    predictions: list[RecommendableItem] = []
    model_version: str = "unknown"
    model_display_name: str = "unknown"


class RankingPrediction(BaseModel):
    """Encapsulates a single scored offer returned by the Ranking Vertex Model."""

    offer_id: str
    score: float


class VertexService:
    """
    Service responsible for communicating with Google Cloud Vertex AI endpoints.

    It relies on async gRPC clients (aiplatform_v1) for high-performance network
    calls. Client instances are cached in memory to avoid the heavy overhead of
    re-establishing TLS handshakes and gRPC channels on every single API request.
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
            logger.error(f"Failed to resolve endpoint {display_name}: {error!s}")
            raise error

    async def _execute_grpc_prediction(self, feature_payloads: list[dict]) -> Any:
        """
        Internal method: Transforms native Python dicts to Protobuf and executes the gRPC call.

        Args:
            feature_payloads (list[dict]): The flat dictionary instances to predict on.

        Returns:
            Any: The raw Protobuf response wrapper from the Vertex AI Prediction API.
        """
        client = await self._get_cached_prediction_client()
        endpoint_resource_path = await self._resolve_endpoint_resource_path(self.endpoint_name)

        # Convert standard Python dictionaries into Protobuf 'Value' objects required by gRPC
        protobuf_instances = [json_format.ParseDict(payload, Value()) for payload in feature_payloads]

        # 2.0 seconds timeout is strict to prevent the API from hanging during traffic spikes
        return await client.predict(endpoint=endpoint_resource_path, instances=protobuf_instances, timeout=2.0)

    async def fetch_retrieval_predictions(self, feature_payloads: list[dict]) -> VertexPredictionResult:
        """
        Calls the Retrieval model to get a massive list of candidate items.

        This endpoint returns a rich dictionary for each predicted item, which is
        parsed into strictly typed Pydantic models (RecommendableItem) for downstream safety.

        Args:
            feature_payloads (list[dict]): The search context and user constraints.

        Returns:
            VertexPredictionResult: The standardized wrapper containing the list of items.
        """
        try:
            # --- 1. Execute Network Call ---
            response = await self._execute_grpc_prediction(feature_payloads)

            # --- 2. Parse Protobuf Response ---
            parsed_predictions = []
            for raw_prediction in response.predictions:
                parsed_predictions.append(
                    RecommendableItem(
                        item_id=raw_prediction["item_id"],
                        item_rank=raw_prediction["idx"],
                        item_score=raw_prediction.get("_distance", None),
                        item_origin="user_based",
                        item_cluster_id=raw_prediction.get("cluster_id", None),
                        item_topic_id=raw_prediction.get("topic_id", None),
                        semantic_emb_mean=raw_prediction.get("semantic_emb_mean", None),
                        is_geolocated=bool(raw_prediction["is_geolocated"]),
                        booking_number=raw_prediction["booking_number"],
                        booking_number_last_7_days=raw_prediction["booking_number_last_7_days"],
                        booking_number_last_14_days=raw_prediction["booking_number_last_14_days"],
                        booking_number_last_28_days=raw_prediction["booking_number_last_28_days"],
                        stock_price=raw_prediction["stock_price"],
                        category=raw_prediction["category"],
                        subcategory_id=raw_prediction["subcategory_id"],
                        search_group_name=raw_prediction["search_group_name"],
                        offer_creation_date=raw_prediction["offer_creation_date"],
                        stock_beginning_date=raw_prediction["stock_beginning_date"],
                        gtl_id=raw_prediction["gtl_id"],
                        gtl_l3=raw_prediction["gtl_l3"],
                        gtl_l4=raw_prediction["gtl_l4"],
                        total_offers=raw_prediction["total_offers"],
                        example_offer_id=raw_prediction.get("example_offer_id", None),
                        example_venue_latitude=raw_prediction.get("example_venue_latitude", None),
                        example_venue_longitude=raw_prediction.get("example_venue_longitude", None),
                    )
                )

            return VertexPredictionResult(
                status="success",
                model_version=response.deployed_model_id,
                predictions=parsed_predictions,
            )

        except Exception as error:
            logger.error(
                f"Vertex Retrieval Prediction failed for {self.endpoint_name}",
                extra_data={"error": str(error), "traceback": traceback.format_exc()},
            )
            # Fail gracefully by returning an empty list rather than crashing the API
            return VertexPredictionResult(status="error", model_display_name=self.endpoint_name, predictions=[])

    async def fetch_ranking_predictions(self, feature_payloads: list[dict]) -> list[RankingPrediction]:
        """
        Calls the Ranking model to score a specific list of resolved offers.

        Unlike Retrieval, this endpoint expects a list of specific offer contexts
        and returns a float score for each.

        Args:
            feature_payloads (list[dict]): The enriched features for the user and each offer.

        Returns:
            list[RankingPrediction]: The validated offer IDs mapped to their ML score.
        """
        try:
            # --- 1. Execute Network Call ---
            response = await self._execute_grpc_prediction(feature_payloads)

            # --- 2. Parse & Validate Response ---
            parsed_results = []
            for raw_prediction in response.predictions:
                try:
                    ranked_item = RankingPrediction(
                        offer_id=str(raw_prediction["offer_id"]), score=float(raw_prediction["score"])
                    )
                    parsed_results.append(ranked_item)

                except (KeyError, ValueError) as format_error:
                    logger.warning(
                        f"Invalid ranking prediction format received: {raw_prediction}",
                        extra_data={"error": str(format_error)},
                    )
                    continue

            return parsed_results

        except Exception as error:
            logger.error(
                f"Vertex Ranking Prediction failed for {self.endpoint_name}",
                extra_data={"error": str(error), "traceback": traceback.format_exc()},
            )
            # Fail gracefully, the caller will fallback to standard ranking
            return []
