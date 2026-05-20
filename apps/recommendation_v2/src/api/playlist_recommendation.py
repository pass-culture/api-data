import uuid
from typing import Annotated

from fastapi import APIRouter
from fastapi import Body
from fastapi import Depends
from fastapi import Path
from fastapi import Query
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from connectors.redis_api import redis_api
from controllers.pipeline_playlist_recommendation import generate_playlist_recommendations
from schemas.playlist_recommendation import PlaylistRequestParams
from schemas.playlist_recommendation import RecommendationResponse
from services.db import get_database_session
from services.h3 import get_h3_index_from_coordinates
from utils.benchmark import log_execution_time
from utils.location_presets import PRESET_LOCATION_TO_GEOGRAPHIC_COORDINATES_MAPPING
from utils.location_presets import PresetLocation


router = APIRouter()


@router.post(
    "/playlist_recommendation/{user_id}",
    response_model=RecommendationResponse,
    summary="Generate a personalized recommendation playlist",
)
@log_execution_time
async def get_playlist(
    params: Annotated[PlaylistRequestParams, Body(...)],
    db: Annotated[AsyncSession, Depends(get_database_session)],
    user_id: Annotated[
        str,
        Path(
            description="The unique identifier of the user.",
            json_schema_extra={"example": settings.SWAGGER_UI_EXAMPLE_USER_ID},
        ),
    ],
    latitude: Annotated[
        float | None, Query(description="The user's GPS latitude, if provided by the mobile app.")
    ] = None,
    longitude: Annotated[
        float | None, Query(description="The user's GPS longitude, if provided by the mobile app.")
    ] = None,
    preset_location: Annotated[
        PresetLocation | None,
        Query(
            description="[DEV/TEST] Overrides latitude and longitude with a preset city based on population density."
        ),
    ] = None,
) -> RecommendationResponse:
    """
    Generates a diversified playlist of recommendable offers for a specific user.

    This endpoint acts as the main HTTP controller. It maps incoming HTTP data to
    the internal pipeline engine.

    Data Routing:
    - `user_id`: Extracted directly from the URL path.
    - `latitude` / `longitude`: Extracted from the URL query string (optional).
    - `preset_location`: [DEV/TEST] Overrides lat/lon for faster Swagger testing.
    - `params`: Extracted from the HTTP POST body (JSON payload), strictly validated by Pydantic.
    - `db`: Injected automatically by FastAPI, providing a safe, scoped database connection.

    Args:
        user_id (str): The unique identifier of the user.
        latitude (float | None): The user's GPS latitude, if provided by the mobile app.
        longitude (float | None): The user's GPS longitude, if provided by the mobile app.
        preset_location (PresetLocation | None): [DEV/TEST] A preset location that overrides lat/lon for testing.
        params (PlaylistRequestParams): The filtering constraints and business rules.
        db (AsyncSession): The active asynchronous database session.

    Returns:
        RecommendationResponse: A structured payload containing the ordered list of offer IDs.
    """
    # Override coordinates if a test location is selected
    if preset_location:
        latitude, longitude = PRESET_LOCATION_TO_GEOGRAPHIC_COORDINATES_MAPPING[preset_location]

    # Use a finer resolution for cache to avoid reusing the same cache if a user moves within a large resolution cell.
    cache_h3_resolution = settings.CACHE_H3_RESOLUTION
    h3_index = get_h3_index_from_coordinates(latitude, longitude, resolution=cache_h3_resolution)

    request_signature_data = {
        "user_id": user_id,
        "location_h3": h3_index,
        "h3_resolution": cache_h3_resolution,
        "params": params.model_dump(mode="json"),
    }

    # Handle Redis cache retrieval
    if settings.REDIS_CACHE_ENABLED:
        cached_playlist_result = await redis_api.fetch_cached_response(
            namespace_prefix="playlist_recommendation",
            request_signature_data=request_signature_data,
            response_model_class=RecommendationResponse,
        )
        if isinstance(cached_playlist_result, RecommendationResponse):
            cached_playlist_result.from_cache = True
            # Overwrite the call_id with a newly generated UUID.
            # This prevents massively linking multiple cache-hit offer displays
            # to the same original call_id, which could otherwise bias model retraining.
            cached_playlist_result.params.call_id = str(uuid.uuid4())
            return cached_playlist_result

    # Delegate the heavy lifting to the core orchestration pipeline
    result = await generate_playlist_recommendations(
        db=db, user_id=user_id, latitude=latitude, longitude=longitude, params=params
    )

    # Store the newly generated result in Cache
    if settings.REDIS_CACHE_ENABLED:
        await redis_api.store_endpoint_response(
            namespace_prefix="playlist_recommendation",
            request_signature_data=request_signature_data,
            response_model_instance=result,
        )

    return result
