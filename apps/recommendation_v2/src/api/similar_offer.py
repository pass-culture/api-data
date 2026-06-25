import uuid
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Path
from fastapi import Query
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from connectors.redis_api import redis_api
from controllers.pipeline_similar_offer import generate_similar_offers
from schemas.categories import CategoryEnum
from schemas.categories import SearchGroupNameEnum
from schemas.categories import SubcategoryEnum
from schemas.location import LocationParams
from schemas.similar_offer import SimilarOfferModelChoices
from schemas.similar_offer import SimilarOfferResponse
from services.db import get_database_session
from services.h3 import get_h3_index_from_coordinates
from services.logger import logger
from utils.benchmark import log_execution_time
from utils.location_presets import PRESET_LOCATION_TO_GEOGRAPHIC_COORDINATES_MAPPING


router = APIRouter()


@router.get(
    "/similar_offers/{offer_id}",
    response_model=SimilarOfferResponse,
    summary="Generate similar offer recommendations",
)
@log_execution_time
async def get_similar_offers(  # noqa: PLR0913
    db: Annotated[AsyncSession, Depends(get_database_session)],
    location: Annotated[LocationParams, Depends()],
    offer_id: Annotated[
        str,
        Path(
            description="The unique identifier of the offer.",
            json_schema_extra={"example": settings.SWAGGER_UI_EXAMPLE_OFFER_ID},
        ),
    ],
    user_id: Annotated[
        str | None,
        Query(description="The user ID for personalized filtering. If not provided, uses default behavior."),
    ] = None,
    categories: Annotated[list[CategoryEnum] | None, Query(description="Filter by categories.")] = None,
    subcategories: Annotated[list[SubcategoryEnum] | None, Query(description="Filter by subcategories.")] = None,
    search_group_names: Annotated[
        list[SearchGroupNameEnum] | None, Query(description="Filter by search group names.")
    ] = None,
    retrieval_model: Annotated[
        SimilarOfferModelChoices,
        Query(
            description="""The retrieval model to use for generating similar offers.
            Options are 'graph' and 'coreservation'. Default is 'coreservation'."""
        ),
    ] = SimilarOfferModelChoices.coreservation,
) -> SimilarOfferResponse:
    """
    Generates a playlist of similar offers for a specific offer.

    ---

    **Path parameters**

    - `offer_id`: Unique identifier of the offer to find similarities for.

    **Query parameters**

    - `user_id` *(optional)*: User ID for personalized filtering (e.g., excludes already-booked items).
      If not provided, uses a generic unauthenticated user context.
    - **Location Context** *(optional, model in `src/schemas/location.py`)*:
      - `latitude`: The user's GPS latitude, as provided by the mobile app.
      - `longitude`: The user's GPS longitude, as provided by the mobile app.
        Both `latitude` and `longitude` must be provided together or not at all.
        If neither is provided, the offer's venue location is used as a fallback.
      - `preset_location` *(DEV/TEST)*: Overrides `latitude`/`longitude` with a preset city.
    - `categories` *(optional)*: Filter results by category.
    - `subcategories` *(optional)*: Filter results by subcategory.
    - `search_group_names` *(optional)*: Filter results by search group name.
    - `retrieval_model` *(optional)*: Model used to retrieve similar offers (`graph` or `coreservation`).
      Defaults to `coreservation`.
    """
    latitude, longitude = location.latitude, location.longitude

    # Override coordinates if a test location is selected
    if location.preset_location:  # pragma: no cover
        latitude, longitude = PRESET_LOCATION_TO_GEOGRAPHIC_COORDINATES_MAPPING[location.preset_location]

    logger.info(
        "📥 Incoming similar_offers request.",
        extra={
            "offer_id": offer_id,
            "user_id": user_id,
            "retrieval_model": retrieval_model,
            "latitude": latitude,
            "longitude": longitude,
            "has_filters": any([categories, subcategories, search_group_names]),
            "categories": [c.value for c in categories] if categories else None,
            "subcategories": [s.value for s in subcategories] if subcategories else None,
            "search_group_names": [s.value for s in search_group_names] if search_group_names else None,
        },
    )

    # Use a finer resolution for cache to avoid reusing the same cache if a user moves within a large resolution cell.
    cache_h3_resolution = settings.CACHE_H3_RESOLUTION
    h3_index = get_h3_index_from_coordinates(latitude, longitude, resolution=cache_h3_resolution)

    request_signature_data = {
        "offer_id": offer_id,
        "user_id": user_id,
        "location_h3": h3_index,
        "categories": sorted([c.value for c in categories]) if categories else None,
        "subcategories": sorted([s.value for s in subcategories]) if subcategories else None,
        "search_group_names": sorted([s.value for s in search_group_names]) if search_group_names else None,
        "retrieval_model": retrieval_model,
    }

    # Handle Redis cache retrieval
    if settings.REDIS_CACHE_ENABLED:
        cached_similar_offer_result = await redis_api.fetch_cached_response(
            namespace_prefix="similar_offer",
            request_signature_data=request_signature_data,
            response_model_class=SimilarOfferResponse,
        )
        if isinstance(cached_similar_offer_result, SimilarOfferResponse):
            cached_similar_offer_result.from_cache = True
            cached_similar_offer_result.params.unique_call_id = str(uuid.uuid4())
            # The original call_id is intentionally preserved.
            # Cache hits are not tracked (no new BigQuery rows), but the client
            # sends click/booking events referencing this call_id, which links them
            # back to the original display rows
            logger.info(
                "✅ Cache HIT — returning cached similar_offers.",
                extra={"offer_id": offer_id, "call_id": cached_similar_offer_result.params.call_id},
            )
            return cached_similar_offer_result

    logger.info(
        "🔍 Cache MISS — running full similar_offers pipeline.",
        extra={"offer_id": offer_id, "retrieval_model": retrieval_model},
    )

    # Delegate the heavy lifting to the core orchestration pipeline
    result = await generate_similar_offers(
        db=db,
        offer_id=offer_id,
        user_id=user_id,
        categories=categories,
        subcategories=subcategories,
        search_group_names=search_group_names,
        latitude=latitude,
        longitude=longitude,
        retrieval_model=retrieval_model,
    )

    # Store the newly generated result in Cache
    if settings.REDIS_CACHE_ENABLED:
        await redis_api.store_endpoint_response(
            namespace_prefix="similar_offer",
            request_signature_data=request_signature_data,
            response_model_instance=result,
        )

    logger.info(
        "✅ similar_offers pipeline completed.",
        extra={
            "offer_id": offer_id,
            "call_id": result.params.call_id,
            "reco_origin": result.params.reco_origin,
            "results_count": len(result.results),
        },
    )

    return result
