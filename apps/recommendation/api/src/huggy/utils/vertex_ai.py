import traceback
from dataclasses import dataclass
from typing import Dict, List, Union

import grpc
from aiocache import Cache, cached
from fastapi.encoders import jsonable_encoder
from google.api_core.exceptions import DeadlineExceeded
from google.cloud import aiplatform
from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value
from huggy.utils.cloud_logging import logger
from huggy.utils.env_vars import GCP_PROJECT


@dataclass
class PredictionResult:
    status: str
    predictions: List[str]
    model_version: str
    model_display_name: str


@cached(ttl=600, cache=Cache.MEMORY)
async def get_model(endpoint_name, location):
    return await __get_model(endpoint_name, location)


async def __get_model(endpoint_name, location):
    endpoint = aiplatform.Endpoint.list(
        filter=f"display_name={endpoint_name}", location=location, project=GCP_PROJECT
    )[0]
    endpoint_dict = endpoint.to_dict()
    return {
        "model_name": endpoint_dict["displayName"],
        "model_version_id": endpoint_dict["deployedModels"][0]["displayName"],
        "endpoint_path": endpoint_dict["name"],
    }


@cached(ttl=600, cache=Cache.MEMORY)
async def get_client(api_endpoint):
    client_options = {"api_endpoint": api_endpoint}
    return aiplatform.gapic.PredictionServiceClient(client_options=client_options)


async def endpoint_score(
    endpoint_name, instances, fallback_endpoints=[], cached=False
) -> PredictionResult:
    for endpoint in [endpoint_name] + fallback_endpoints:
        response = await predict_model(
            endpoint_name=endpoint,
            location="europe-west1",
            instances=instances,
        )
        prediction_result = PredictionResult(
            status=response["status"],
            predictions=response["predictions"],
            model_display_name=response["model_display_name"],
            model_version=response["model_version_id"],
        )
        # if we have results, return, else fallback_endpoints
        if (
            prediction_result.status == "success"
            and len(prediction_result.predictions) > 0
        ):
            return prediction_result
    # default
    return prediction_result


async def predict_model(
    endpoint_name: str,
    instances: Union[Dict, List[Dict]],
    location: str = "europe-west1",
    api_endpoint: str = "europe-west1-aiplatform.googleapis.com",
):
    return await __predict_model(endpoint_name, instances, location, api_endpoint)


async def __predict_model(
    endpoint_name: str,
    instances: Union[Dict, List[Dict]],
    location: str = "europe-west1",
    api_endpoint: str = "europe-west1-aiplatform.googleapis.com",
):
    """
    `instances` can be either single instance of type dict or a list
    of instances.
    """
    default_error = {
        "status": "success",
        "predictions": [],
        "model_version_id": "unknown",
        "model_display_name": "unknown",
    }
    try:
        client = await get_client(api_endpoint)

        try:
            model_params = await get_model(endpoint_name, location)

        except:
            model_params = await __get_model(endpoint_name, location)
            logger.warn(
                "__predict_endpoint : Could not get model",
                extra={
                    "event_name": "predict_model",
                    "endpoint_name": endpoint_name,
                },
            )
        instances = instances if type(instances) == list else [instances]

        logger.debug(
            "__predict_endpoint : predict",
            extra={
                "event_name": "predict_model",
                "endpoint_name": endpoint_name,
                "details": {"instances": jsonable_encoder(instances)},
            },
        )

        instances = [
            json_format.ParseDict(instance_dict, Value()) for instance_dict in instances
        ]
        parameters_dict = {}
        parameters = json_format.ParseDict(parameters_dict, Value())

        try:
            response = client.predict(
                endpoint=model_params["endpoint_path"],
                instances=instances,
                parameters=parameters,
                timeout=2,
            )
        except DeadlineExceeded:
            timeout_error = {
                "status": "error",
                "predictions": [],
                "model_version_id": model_params["model_version_id"],
                "model_display_name": model_params["model_name"],
            }
            logger.warn(
                "__predict_endpoint : Timeout",
                extra=dict(
                    {
                        "event_name": "predict_model",
                        "error": "timeout_error",
                        "endpoint_name": endpoint_name,
                    },
                    **timeout_error,
                ),
            )
            return {
                "status": "error",
                "predictions": [],
                "model_version_id": model_params["model_version_id"],
                "model_display_name": model_params["model_name"],
            }

        response_dict = {
            "status": "success",
            "predictions": response.predictions,
            "model_version_id": model_params["model_version_id"],
            "model_display_name": model_params["model_name"],
        }
        logger.debug(
            "__predict_endpoint : results",
            extra=dict(
                {
                    "event_name": "predict_model",
                    "endpoint_name": endpoint_name,
                },
            ),
        )
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
                        "content": {
                            "error": e.__class__.__name__,
                            "trace": tb,
                        }
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
                        "content": {
                            "error": e.__class__.__name__,
                            "trace": tb,
                        }
                    },
                },
                **default_error,
            ),
        )
        return default_error

    return response_dict
