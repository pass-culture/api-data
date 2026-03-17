import typing as t

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from huggy.database.session import get_db
from huggy.views.common import check_token, get_call_id, setup_trace

artist_router = r = APIRouter(tags=["artists"])


async def __similar_artists(
    db: AsyncSession,
    artist_id: str,
    call_id: str,
):
    similar_artists = await Artist.get_similar_artist(db=db, artist_id=artist_id)

    return jsonable_encoder(
        {
            "similar_artists": similar_artists,
            "params": {
                "artist_id": artist_id,
                "call_id": call_id,
            },
        }
    )


@r.get(
    "/similar_artists/{artist_id}",
    dependencies=[Depends(setup_trace), Depends(check_token)],
)
async def get_similar_artists(
    artist_id: str,
    token: t.Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    call_id: str = Depends(get_call_id),
):
    return await __similar_artists(
        db,
        artist_id=artist_id,
        call_id=call_id,
    )
