from enum import Enum
from typing import Annotated

from fastapi import APIRouter
from fastapi import Body
from fastapi import Depends
from fastapi import Path
from fastapi import Query
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from core.pipeline import generate_playlist_recommendations
from schemas.playlist_recommendation import PlaylistRequestParams
from schemas.playlist_recommendation import RecommendationResponse
from services.db import get_database_session


router = APIRouter()


# --- TEST LOCATIONS CONFIGURATION ---
class PresetLocation(str, Enum):
    # Highly populated (Major metropolitan areas)
    HIGH_DENSITY_PARIS = "High Density - Paris"
    HIGH_DENSITY_LYON = "High Density - Lyon"
    HIGH_DENSITY_MARSEILLE = "High Density - Marseille"

    # Moderately populated (Medium-sized cities)
    MEDIUM_DENSITY_TOURS = "Medium Density - Tours"
    MEDIUM_DENSITY_ANNECY = "Medium Density - Annecy"
    MEDIUM_DENSITY_LA_ROCHELLE = "Medium Density - La Rochelle"

    # Sparsely populated (Rural areas)
    LOW_DENSITY_MENDE = "Low Density - Mende (Lozère)"
    LOW_DENSITY_GUERET = "Low Density - Guéret (Creuse)"
    LOW_DENSITY_FLORAC = "Low Density - Florac (Cévennes)"


# Exact coordinate mapping (Latitude, Longitude)
PRESET_LOCATION_TO_GEOGRAPHIC_COORDINATES_MAPPING = {
    PresetLocation.HIGH_DENSITY_PARIS: (48.8566, 2.3522),
    PresetLocation.HIGH_DENSITY_LYON: (45.7640, 4.8357),
    PresetLocation.HIGH_DENSITY_MARSEILLE: (43.2965, 5.3698),
    PresetLocation.MEDIUM_DENSITY_TOURS: (47.3941, 0.6848),
    PresetLocation.MEDIUM_DENSITY_ANNECY: (45.8992, 6.1294),
    PresetLocation.MEDIUM_DENSITY_LA_ROCHELLE: (46.1603, -1.1511),
    PresetLocation.LOW_DENSITY_MENDE: (44.5176, 3.5000),
    PresetLocation.LOW_DENSITY_GUERET: (46.1667, 1.8667),
    PresetLocation.LOW_DENSITY_FLORAC: (44.3239, 3.5971),
}


@router.post(
    "/playlist_recommendation/{user_id}",
    response_model=RecommendationResponse,
    summary="Generate a personalized recommendation playlist",
)
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

    # Delegate the heavy lifting to the core orchestration pipeline
    return await generate_playlist_recommendations(
        db=db, user_id=user_id, latitude=latitude, longitude=longitude, params=params
    )
