import typing as t

import huggy.schemas.playlist_params as p
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from huggy.core.model_engine.recommendation import Recommendation
from huggy.core.model_engine.similar_offer import SimilarOffer
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
    offer_recommendations = []
    user = await UserContextDB().get_user_context(
        db, playlist_params.user_id, latitude, longitude
    )

    offer = await Offer().get_offer_characteristics(db, offer_id)

    scoring = SimilarOffer(
        user, playlist_params, call_id=call_id, context="similar_offer", offer=offer
    )

    if not offer.is_sensitive:
        offer_recommendations = await scoring.get_scoring(db)

        # fallback to reco
        if len(offer_recommendations) == 0:
            scoring = Recommendation(
                user,
                params_in=playlist_params,
                call_id=call_id,
                context="recommendation_fallback",
            )
            offer_recommendations = await scoring.get_scoring(db)

    return jsonable_encoder(
        {
            "results": offer_recommendations,
            "params": {
                "reco_origin": scoring.reco_origin,
                "model_origin": scoring.model_origin,
                "call_id": call_id,
            },
        }
    )


@r.post(
    "/similar_offers/{offer_id}",
    dependencies=[Depends(setup_trace), Depends(check_token)],
)
async def similar_offers(
    offer_id: str,
    playlist_params: p.PostSimilarOfferPlaylistParams,
    token: str = None,
    latitude: float = None,
    longitude: float = None,
    db: AsyncSession = Depends(get_db),
    call_id: str = Depends(get_call_id),
):
    return await __similar_offers(
        db,
        offer_id=offer_id,
        playlist_params=playlist_params,
        latitude=latitude,
        longitude=longitude,
        call_id=call_id,
    )


@r.get(
    "/similar_offers/{offer_id}",
    dependencies=[Depends(setup_trace), Depends(check_token)],
)
async def similar_offers(
    offer_id: str,
    playlist_params: p.GetSimilarOfferPlaylistParams = Depends(),
    token: str = None,
    latitude: float = None,
    longitude: float = None,
    db: AsyncSession = Depends(get_db),
    call_id: str = Depends(get_call_id),
):
    return await __similar_offers(
        db,
        offer_id=offer_id,
        playlist_params=playlist_params,
        latitude=latitude,
        longitude=longitude,
        call_id=call_id,
    )
