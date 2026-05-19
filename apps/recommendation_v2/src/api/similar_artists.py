from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Path
from sqlalchemy.ext.asyncio import AsyncSession

from controllers.pipeline_similar_artists import get_similar_artists_from_db
from schemas.similar_artists import SimilarArtistsResponse
from services.db import get_database_session


router = APIRouter()


@router.get(
    "/similar_artists/{artist_id}",
    response_model=SimilarArtistsResponse,
    summary="Get similar artists for a given artist ID",
)
async def get_similar_artists(
    db: Annotated[AsyncSession, Depends(get_database_session)],
    artist_id: Annotated[
        str,
        Path(
            description="The unique identifier of the artist to find similar artists for.",
            json_schema_extra={"example": "a3a7c9f7-26f1-4bd3-bfc2-40a7abd398cf"},
        ),
    ],
) -> SimilarArtistsResponse:
    return await get_similar_artists_from_db(db=db, artist_id=artist_id)
