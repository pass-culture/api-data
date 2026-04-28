from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Path
from fastapi import Query
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from controllers.pipeline_similar_offer import generate_similar_offers
from schemas.categories import CategoryEnum
from schemas.categories import SearchGroupNameEnum
from schemas.categories import SubcategoryEnum
from schemas.similar_offer import SimilarOfferResponse
from services.db import get_database_session
from utils.location_presets import PRESET_LOCATION_TO_GEOGRAPHIC_COORDINATES_MAPPING
from utils.location_presets import PresetLocation


router = APIRouter()


@router.get(
    "/similar_offers/{offer_id}",
    response_model=SimilarOfferResponse,
    summary="Generate similar offer recommendations",
)
async def get_similar_offers(  # noqa: PLR0913
    db: Annotated[AsyncSession, Depends(get_database_session)],
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
) -> SimilarOfferResponse:
    """
    Generates a playlist of similar offers for a specific offer.

    This endpoint acts as the main HTTP controller for similar offers. It maps incoming HTTP data to
    the internal pipeline engine.

    Data Routing:
    - `db`: Injected automatically by FastAPI, providing a safe, scoped database connection.
    - `offer_id`: Extracted directly from the URL path.
    - `user_id`: Extracted from the URL query string (optional). If provided, enables personalized
                 filtering (e.g., excluding already-booked items). If not provided, uses a generic
                 unauthenticated user context.
    - `latitude` / `longitude`: Extracted from the URL query string (optional).
                                Corresponds to the user's current location for spatial filtering or ranking.
                                If not provided, the offer's venue location is used as a fallback.
    - `preset_location`: [DEV/TEST] Overrides lat/lon for faster Swagger testing.
    - `categories` / `subcategories` / `search_group_names`: Extracted from the URL query string as lists (optional).
                                These filters narrow down the results to specific content categories.

    Args:
        db (AsyncSession): The active asynchronous database session.
        offer_id (str): The unique identifier of the offer to find similarities for.
        user_id (str | None): Optional user ID for personalized recommendations.
        categories (list[CategoryEnum] | None): Optional list of categories to filter the similar offers.
        subcategories (list[SubcategoryEnum] | None): Optional list of subcategories to filter the similar offers.
        search_group_names (list[SearchGroupNameEnum] | None): Optional list of search group names to filter
        the similar offers.
        latitude (float | None): The user's GPS latitude, if provided by the mobile app.
        longitude (float | None): The user's GPS longitude, if provided by the mobile app.
        preset_location (PresetLocation | None): [DEV/TEST] A preset location that overrides lat/lon for testing.

    Returns:
        SimilarOfferResponse: A structured payload containing the ordered list of offer IDs.
    """
    # Override coordinates if a test location is selected
    if preset_location:
        latitude, longitude = PRESET_LOCATION_TO_GEOGRAPHIC_COORDINATES_MAPPING[preset_location]

    # Delegate the heavy lifting to the core orchestration pipeline
    return await generate_similar_offers(
        db=db,
        offer_id=offer_id,
        user_id=user_id,
        categories=categories,
        subcategories=subcategories,
        search_group_names=search_group_names,
        latitude=latitude,
        longitude=longitude,
    )
