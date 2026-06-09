import traceback
from dataclasses import dataclass
from typing import Union

import grpc
from aiocache import Cache, cached
from fastapi.encoders import jsonable_encoder
from google.api_core.client_options import ClientOptions as _ClientOptions
from google.api_core.exceptions import DeadlineExceeded
from google.cloud import aiplatform_v1
from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value

from huggy.utils.cloud_logging import logger
from huggy.utils.env_vars import GCP_PROJECT

_LOCATION = "europe-west1"
_API_ENDPOINT = f"{_LOCATION}-aiplatform.googleapis.com"


@dataclass
class PredictionResult:
    status: str
    predictions: list[str]
    model_version: str
    model_display_name: str


# ---------------------------------------------------------------------------
# gRPC client singletons
#
# Module-level variables are used instead of @cached to avoid a race condition:
# asyncio.gather() can call these functions concurrently before the cache is
# populated, causing N clients to be instantiated simultaneously (one per
# coroutine). Since the constructors are synchronous (no await), the
# if-None check + assignment is atomic within the asyncio event loop.
# ---------------------------------------------------------------------------

_prediction_client: aiplatform_v1.PredictionServiceAsyncClient | None = None
_endpoint_service_client: aiplatform_v1.EndpointServiceAsyncClient | None = None


async def _get_prediction_client() -> aiplatform_v1.PredictionServiceAsyncClient:
    global _prediction_client
    if _prediction_client is None:
        _prediction_client = aiplatform_v1.PredictionServiceAsyncClient(
            client_options=_ClientOptions(api_endpoint=_API_ENDPOINT)
        )
    return _prediction_client


async def _get_endpoint_service_client() -> aiplatform_v1.EndpointServiceAsyncClient:
    global _endpoint_service_client
    if _endpoint_service_client is None:
        _endpoint_service_client = aiplatform_v1.EndpointServiceAsyncClient(
            client_options=_ClientOptions(api_endpoint=_API_ENDPOINT)
        )
    return _endpoint_service_client


# ---------------------------------------------------------------------------
# Endpoint resolution  (fully async — no asyncio.to_thread needed)
# ---------------------------------------------------------------------------


@cached(ttl=600, cache=Cache.MEMORY)
async def get_model(endpoint_name: str, location: str = _LOCATION) -> dict:
    """Returns cached model metadata for the given endpoint display name."""
    return await __get_model(endpoint_name, location)


async def __get_model(endpoint_name: str, location: str = _LOCATION) -> dict:
    """
    Resolves endpoint display_name → GCP resource path + model metadata.
    Uses aiplatform_v1.EndpointServiceAsyncClient (same as V2).
    """
    client = await _get_endpoint_service_client()
    parent = f"projects/{GCP_PROJECT}/locations/{location}"

    request = aiplatform_v1.ListEndpointsRequest(
        parent=parent,
        filter=f'display_name="{endpoint_name}"',
        order_by="create_time desc",
    )

    # list_endpoints returns an AsyncListEndpointsPager — iterate to get the first result.
    endpoint = None
    async for ep in await client.list_endpoints(request=request):
        endpoint = ep
        break

    if endpoint is None:
        raise ValueError(
            f"No Vertex endpoint found with display_name='{endpoint_name}'"
        )

    return {
        "model_name": endpoint.display_name,
        "model_version_id": endpoint.deployed_models[0].display_name
        if endpoint.deployed_models
        else "unknown",
        "endpoint_path": endpoint.name,
    }


# ---------------------------------------------------------------------------
# Prediction helpers
# ---------------------------------------------------------------------------


async def endpoint_score(
    endpoint_name: str,
    instances: Union[dict, list[dict]],
    fallback_endpoints: list[str] = None,
) -> PredictionResult:
    if fallback_endpoints is None:
        fallback_endpoints = []

    for name in [endpoint_name, *fallback_endpoints]:
        response = await predict_model(endpoint_name=name, instances=instances)
        prediction_result = PredictionResult(
            status=response["status"],
            predictions=response["predictions"],
            model_display_name=response["model_display_name"],
            model_version=response["model_version_id"],
        )
        if (
            prediction_result.status == "success"
            and len(prediction_result.predictions) > 0
        ):
            return prediction_result

    return prediction_result  # last result (empty) as default


async def predict_model(
    endpoint_name: str,
    instances: Union[dict, list[dict]],
    location: str = _LOCATION,
) -> dict:
    return await __predict_model(endpoint_name, instances, location)


async def __predict_model(
    endpoint_name: str,
    instances: Union[dict, list[dict]],
    location: str = _LOCATION,
) -> dict:
    """
    Calls Vertex AI asynchronously using aiplatform_v1.PredictionServiceAsyncClient.
    `await client.predict()` releases the event loop during the network call,
    allowing asyncio.gather() to run multiple predictions truly in parallel.
    """
    default_error = {
        "status": "success",
        "predictions": [],
        "model_version_id": "unknown",
        "model_display_name": "unknown",
    }

    try:
        client = await _get_prediction_client()

        try:
            model_params = await get_model(endpoint_name, location)
        except Exception:
            model_params = await __get_model(endpoint_name, location)
            logger.warn(
                "__predict_endpoint : Could not get model",
                extra={"event_name": "predict_model", "endpoint_name": endpoint_name},
            )

        instances = instances if isinstance(instances, list) else [instances]

        logger.debug(
            "__predict_endpoint : predict",
            extra={
                "event_name": "predict_model",
                "endpoint_name": endpoint_name,
                "details": {"instances": jsonable_encoder(instances)},
            },
        )

        protobuf_instances = [
            json_format.ParseDict(instance_dict, Value()) for instance_dict in instances
        ]

        try:
            response = await client.predict(
                endpoint=model_params["endpoint_path"],
                instances=protobuf_instances,
                timeout=2,
            )
        except DeadlineExceeded:
            logger.warn(
                "__predict_endpoint : Timeout",
                extra={
                    "event_name": "predict_model",
                    "error": "timeout_error",
                    "endpoint_name": endpoint_name,
                    "model_version_id": model_params["model_version_id"],
                    "model_display_name": model_params["model_name"],
                },
            )
            return {
                "status": "error",
                "predictions": [],
                "model_version_id": model_params["model_version_id"],
                "model_display_name": model_params["model_name"],
            }

        logger.debug(
            "__predict_endpoint : results",
            extra={"event_name": "predict_model", "endpoint_name": endpoint_name},
        )

        return {
            "status": "success",
            "predictions": response.predictions,
            "model_version_id": model_params["model_version_id"],
            "model_display_name": model_params["model_name"],
        }

    except grpc._channel._InactiveRpcError as e:
        tb = traceback.format_exc()
        logger.warn(
            "__predict_endpoint : error",
            extra=dict(
                {
                    "event_name": "predict_model",
                    "error": "default_error",
                    "endpoint_name": endpoint_name,
                    "details": {
                        "content": {"error": e.__class__.__name__, "trace": tb}
                    },
                },
                **default_error,
            ),
        )
        return default_error

    except Exception as e:
        tb = traceback.format_exc()
        logger.warn(
            "__predict_endpoint : error",
            extra=dict(
                {
                    "event_name": "predict_model",
                    "error": "default_error",
                    "endpoint_name": endpoint_name,
                    "details": {
                        "content": {"error": e.__class__.__name__, "trace": tb}
                    },
                },
                **default_error,
            ),
        )
        return default_error
