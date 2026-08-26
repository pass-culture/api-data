import uuid
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Path
from fastapi import Query

from config import settings
from connectors.redis_api import redis_api
from controllers.pipeline_offer_page_playlists import generate_offer_page_playlists
from schemas.categories import SearchGroupNameEnum
from schemas.location import LocationParams
from schemas.offer_page_playlists import OfferPagePlaylistsResponse
from services.h3 import get_h3_index_from_coordinates
from services.logger import logger
from utils.benchmark import log_execution_time
from utils.location_presets import PRESET_LOCATION_TO_GEOGRAPHIC_COORDINATES_MAPPING


router = APIRouter()


@router.get(
    "/offer_page_playlists/{offer_id}",
    response_model=OfferPagePlaylistsResponse,
    summary="Generate all recommendation playlists for an offer page",
)
@log_execution_time
async def get_offer_page_playlists(
    location: Annotated[LocationParams, Depends()],
    offer_id: Annotated[
        str,
        Path(
            description="The unique identifier of the displayed offer.",
            json_schema_extra={"example": settings.SWAGGER_UI_EXAMPLE_OFFER_ID},
        ),
    ],
    search_group_name: Annotated[
        SearchGroupNameEnum,
        Query(
            description=("The `search_group_name` (category) of the reference offer. Must be supplied by the client."),
            json_schema_extra={"example": SearchGroupNameEnum.LIVRES},
        ),
    ],
    user_id: Annotated[
        str | None,
        Query(description="The user ID for personalised filtering (e.g. excludes already-booked items)."),
    ] = None,
) -> OfferPagePlaylistsResponse:
    """
    Returns all recommendation playlists to display on an offer detail page in a single round-trip.

    ---

    The API decides autonomously which playlists to include (number, title, filters, model)
    based on the offer's ``search_group_name`` supplied as a query parameter.
    The client must render playlists in the order provided.

    **Path parameters**

    - `offer_id`: Unique identifier of the offer currently displayed.

    **Query parameters**

    - `search_group_name` *(required)*: Category of the reference offer.
    - `user_id` *(optional)*: User ID used for personalised filtering.
    - **Location context** *(optional)*:
      - `latitude` / `longitude`: GPS coordinates of the user.
        Must be provided together or not at all.
      - `preset_location` *(DEV/TEST)*: Overrides `latitude`/`longitude` with a preset city.
    """
    latitude, longitude = location.latitude, location.longitude

    # Override coordinates if a test preset location is selected.
    if location.preset_location:  # pragma: no cover
        latitude, longitude = PRESET_LOCATION_TO_GEOGRAPHIC_COORDINATES_MAPPING[location.preset_location]

    logger.info(
        "📥 Incoming offer_page_playlists request.",
        extra={
            "offer_id": offer_id,
            "user_id": user_id,
            "search_group_name": search_group_name,
            "latitude": latitude,
            "longitude": longitude,
        },
    )

    # Use a fine H3 resolution for cache to avoid reusing the same cache if a user moves
    # within a large resolution cell.
    cache_h3_resolution = settings.ENDPOINT_RESPONSE_CACHE_H3_RESOLUTION
    h3_index = get_h3_index_from_coordinates(latitude, longitude, resolution=cache_h3_resolution)

    # Build the request signature used to derive the Redis cache key.
    # search_group_name is now client-supplied (not resolved from the offer_id),
    # so it must be part of the cache key.
    request_signature_data = {
        "offer_id": offer_id,
        "user_id": user_id,
        "search_group_name": search_group_name,
        "location_h3": h3_index,
    }

    # --- Redis cache check ---
    if settings.ENDPOINT_RESPONSE_CACHE_ENABLED:
        cached_result = await redis_api.fetch_cached_response(
            namespace_prefix="offer_page_playlists",
            request_signature_data=request_signature_data,
            response_model_class=OfferPagePlaylistsResponse,
        )
        if isinstance(cached_result, OfferPagePlaylistsResponse):
            cached_result.from_cache = True
            # Assign fresh unique_call_ids to each playlist so click events can be
            # attributed to this specific page load while preserving the original
            # call_ids that link back to the BigQuery tracking rows.
            for playlist in cached_result.playlists:
                playlist.params.unique_call_id = str(uuid.uuid4())
            logger.info(
                "✅ [HTTP Request Cache] Cache HIT — returning cached offer_page_playlists.",
                extra={"offer_id": offer_id},
            )
            return cached_result

    logger.info(
        "🔍 [HTTP Request Cache] Cache MISS — running full offer_page_playlists pipeline.",
        extra={"offer_id": offer_id},
    )

    # --- Core pipeline ---
    result = await generate_offer_page_playlists(
        offer_id=offer_id,
        search_group_name=search_group_name,
        user_id=user_id,
        latitude=latitude,
        longitude=longitude,
    )

    # --- Store result in cache ---
    if settings.ENDPOINT_RESPONSE_CACHE_ENABLED:
        await redis_api.store_endpoint_response(
            namespace_prefix="offer_page_playlists",
            request_signature_data=request_signature_data,
            response_model_instance=result,
        )

    logger.info(
        "✅ offer_page_playlists endpoint completed.",
        extra={
            "offer_id": offer_id,
            "playlists_count": len(result.playlists),
            "playlists": [
                {"title": playlist.title, "type": playlist.playlist_type, "count": len(playlist.results)}
                for playlist in result.playlists
            ],
        },
    )

    return result
