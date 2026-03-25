import typing as t

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from huggy.crud.artist import get_similar_artists_from_db
from huggy.database.session import get_db
from huggy.schemas.artist import SimilarArtistsResponse
from huggy.views.common import check_token, get_call_id, setup_trace

artist_router = APIRouter(tags=["artists"])


@artist_router.get(
    "/similar_artists/{artist_id}",
    dependencies=[Depends(setup_trace), Depends(check_token)],
    response_model=SimilarArtistsResponse,
)
async def similar_artists(
    artist_id: str,
    token: t.Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    call_id: str = Depends(get_call_id),
):
    similar_artists = await get_similar_artists_from_db(db=db, artist_id=artist_id)

    return {
        "similar_artists": similar_artists,
        "params": {
            "artist_id": artist_id,
            "call_id": call_id,
        },
    }
