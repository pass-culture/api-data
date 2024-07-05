import huggy.schemas.playlist_params as p
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from huggy.core.model_engine.recommendation import Recommendation
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
    latitude: float = None,
    longitude: float = None,
    modelEndpoint: str = None,
    db: AsyncSession = Depends(get_db),
    call_id: str = Depends(get_call_id),
):
    user = await UserContextDB().get_user_context(db, user_id, latitude, longitude)

    if modelEndpoint is not None:
        playlist_params.model_endpoint = modelEndpoint
    if playlist_params.is_restrained is None:
        playlist_params.is_restrained = True
    scoring = Recommendation(
        user, params_in=playlist_params, call_id=call_id, context="recommendation"
    )

    user_recommendations = await scoring.get_scoring(db)

    return jsonable_encoder(
        {
            "playlist_recommended_offers": user_recommendations,
            "params": {
                "reco_origin": scoring.reco_origin,
                "model_origin": scoring.model_origin,
                "call_id": call_id,
            },
        }
    )
