from typing import Optional

import huggy.schemas.playlist_params as p
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from huggy.core.model_engine.factory import ModelEngineFactory, ModelEngineOut
from huggy.crud.offer import Offer
from huggy.crud.user import UserContextDB
from huggy.database.session import get_db
from huggy.views.common import check_token, get_call_id, setup_trace
from sqlalchemy.ext.asyncio import AsyncSession

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
    # legacy: force modelEndpoint input
    playlist_params.add_model_endpoint(modelEndpoint)

    user = await UserContextDB().get_user_context(db, user_id, latitude, longitude)
    input_offers = await Offer.parse_offer_list(db, playlist_params.input_offers)

    model_engine_out: ModelEngineOut = await ModelEngineFactory.handle_prediction(
        db,
        user=user,
        playlist_params=playlist_params,
        call_id=call_id,
        context="recommendation",
        input_offers=input_offers,
        use_fallback=True,
    )

    return jsonable_encoder(
        {
            "playlist_recommended_offers": model_engine_out.results,
            "params": {
                "reco_origin": model_engine_out.model.reco_origin,
                "model_origin": model_engine_out.model.model_origin,
                "call_id": call_id,
            },
        }
    )
