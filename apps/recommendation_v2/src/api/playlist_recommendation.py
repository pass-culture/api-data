from typing import Annotated

from fastapi import APIRouter
from fastapi import Body
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.pipeline import generate_playlist_recommendations
from schemas.playlist_recommendation import PlaylistRequestParams
from schemas.playlist_recommendation import RecommendationResponse
from services.db import get_database_session


router = APIRouter()


@router.post(
    "/playlist_recommendation/{user_id}",
    response_model=RecommendationResponse,
    summary="Generate a personalized recommendation playlist",
)
async def get_playlist(
    params: Annotated[PlaylistRequestParams, Body(...)],
    db: Annotated[AsyncSession, Depends(get_database_session)],
    user_id: str,
    latitude: float | None = None,
    longitude: float | None = None,
) -> RecommendationResponse:
    """
    Generates a diversified playlist of recommendable offers for a specific user.

    This endpoint acts as the main HTTP controller. It maps incoming HTTP data to
    the internal pipeline engine.

    Data Routing:
    - `user_id`: Extracted directly from the URL path.
    - `latitude` / `longitude`: Extracted from the URL query string (optional).
    - `params`: Extracted from the HTTP POST body (JSON payload), strictly validated by Pydantic.
    - `db`: Injected automatically by FastAPI, providing a safe, scoped database connection.

    Args:
        user_id (str): The unique identifier of the user.
        latitude (float | None): The user's GPS latitude, if provided by the mobile app.
        longitude (float | None): The user's GPS longitude, if provided by the mobile app.
        params (PlaylistRequestParams): The filtering constraints and business rules.
        db (AsyncSession): The active asynchronous database session.

    Returns:
        RecommendationResponse: A structured payload containing the ordered list of offer IDs.
    """

    # Delegate the heavy lifting to the core orchestration pipeline
    return await generate_playlist_recommendations(
        db=db, user_id=user_id, latitude=latitude, longitude=longitude, params=params
    )
