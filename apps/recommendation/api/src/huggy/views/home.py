from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

import huggy.schemas.playlist_params as p
from huggy.database.session import get_db
from huggy.views.common import check_token, get_call_id, setup_trace

home_router = r = APIRouter(tags=["home"])


@r.post(
    "/playlist_recommendation/{user_id}",
    dependencies=[Depends(setup_trace), Depends(check_token)],
)
async def playlist_recommendation(
    user_id: str,
    playlist_params: p.PlaylistParams,
    token: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    modelEndpoint: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    call_id: str = Depends(get_call_id),
):
    return jsonable_encoder(
        {
            "playlist_recommended_offers": [],
            "params": {
                "reco_origin": None,
                "model_origin": None,
                "call_id": call_id,
            },
        }
    )
