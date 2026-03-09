import typing as t

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

import huggy.schemas.playlist_params as p
from huggy.database.session import get_db
from huggy.views.common import check_token, get_call_id, setup_trace

offer_router = r = APIRouter(tags=["offer"])


async def __similar_offers(
    db: AsyncSession,
    offer_id: str,
    playlist_params: p.PlaylistParams,
    latitude: t.Optional[float],
    longitude: t.Optional[float],
    call_id: str,
):
    return jsonable_encoder(
        {
            "results": [],
            "params": {
                "reco_origin": None,
                "model_origin": None,
                "call_id": call_id,
            },
        }
    )


@r.get(
    "/similar_offers/{offer_id}",
    dependencies=[Depends(setup_trace), Depends(check_token)],
)
async def get_similar_offers(
    offer_id: str,
    token: t.Optional[str] = None,
    latitude: t.Optional[float] = None,
    longitude: t.Optional[float] = None,
    user_id: t.Optional[str] = None,
    categories: t.Optional[list[str]] = Query(None),
    subcategories: t.Optional[list[str]] = Query(None),
    search_group_names: t.Optional[list[str]] = Query(None),
    db: AsyncSession = Depends(get_db),
    call_id: str = Depends(get_call_id),
):
    playlist_params = p.GetSimilarOfferPlaylistParams(
        user_id=user_id,
        categories=categories,
        subcategories=subcategories,
        search_group_names=search_group_names,
    )

    return await __similar_offers(
        db,
        offer_id=offer_id,
        playlist_params=playlist_params,
        latitude=latitude,
        longitude=longitude,
        call_id=call_id,
    )
