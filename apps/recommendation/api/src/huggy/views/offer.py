import typing as t

import huggy.schemas.playlist_params as p
from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from huggy.core.model_engine.factory import ModelEngineFactory, ModelEngineOut
from huggy.crud.offer import Offer
from huggy.crud.user import UserContextDB
from huggy.database.session import get_db
from huggy.views.common import check_token, get_call_id, setup_trace
from sqlalchemy.ext.asyncio import AsyncSession

offer_router = r = APIRouter(tags=["offer"])


async def __similar_offers(
    db: AsyncSession,
    offer_id: str,
    playlist_params: p.PlaylistParams,
    latitude: t.Optional[float],
    longitude: t.Optional[float],
    call_id: str,
):
    # legacy: include main offer_id in the list of offers
    playlist_params.add_offer(offer_id)

    user = await UserContextDB().get_user_context(
        db, playlist_params.user_id, latitude, longitude
    )
    input_offers = await Offer().parse_offer_list(db, playlist_params.input_offers)

    model_engine_out: ModelEngineOut = await ModelEngineFactory.handle_prediction(
        db,
        user=user,
        params_in=playlist_params,
        call_id=call_id,
        context="similar_offer",
        input_offers=input_offers,
        use_fallback=True,
    )

    return jsonable_encoder(
        {
            "results": model_engine_out.results,
            "params": {
                "reco_origin": model_engine_out.model.reco_origin,
                "model_origin": model_engine_out.model.model_origin,
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
