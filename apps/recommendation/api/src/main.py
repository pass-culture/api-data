import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from huggy.core.model_engine.recommendation import Recommendation
from huggy.core.model_engine.similar_offer import SimilarOffer
from huggy.crud.offer import Offer
import huggy.schemas.offer as o
import huggy.schemas.user as u
from huggy.crud.user import UserContextDB
from huggy.database.session import get_db
import huggy.schemas.playlist_params as p
from huggy.utils.cloud_logging import logger
from huggy.utils.env_vars import (
    API_TOKEN,
    API_LOCAL,
    CORS_ALLOWED_ORIGIN,
    call_id_trace_context,
    cloud_trace_context,
)
from huggy.utils.exception import ExceptionHandlerMiddleware

app = FastAPI(title="passCulture - Recommendation")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGIN,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.add_middleware(ExceptionHandlerMiddleware)


async def setup_trace(request: Request):
    if "x-cloud-trace-context" in request.headers:
        cloud_trace_context.set(request.headers.get("x-cloud-trace-context"))


async def check_token(request: Request):
    if API_LOCAL:
        return True
    if request.query_params.get("token", None) != API_TOKEN:
        raise HTTPException(status_code=401, detail="Not authorized")


async def get_call_id():
    call_id = str(uuid.uuid4())
    call_id_trace_context.set(call_id)
    return call_id


@app.get("/", dependencies=[Depends(setup_trace)])
async def read_root():
    logger.info("Welcome to the recommendation API!")
    return "Welcome to the recommendation API!"


@app.get("/check")
async def check():
    return "OK"


async def __similar_offers(
    db: AsyncSession,
    offer_id: str,
    playlist_params: p.PlaylistParams,
    latitude: float,
    longitude: float,
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

        await scoring.save_recommendation(db, offer_recommendations)

    return jsonable_encoder(
        {
            "results": offer_recommendations,
            "params": {
                "reco_origin": scoring.reco_origin,
                "call_id": call_id,
            },
        }
    )


@app.post(
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
        latitude=latitude,  # TODO feat: PC-25775
        longitude=longitude,
        call_id=call_id,
    )


@app.get(
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
        latitude=latitude,  # TODO feat: PC-25775
        longitude=longitude,
        call_id=call_id,
    )


@app.post(
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

    scoring = Recommendation(
        user, params_in=playlist_params, call_id=call_id, context="recommendation"
    )

    user_recommendations = await scoring.get_scoring(db)

    await scoring.save_recommendation(db, user_recommendations)
    return jsonable_encoder(
        {
            "playlist_recommended_offers": user_recommendations,
            "params": {
                "reco_origin": scoring.reco_origin,
                "call_id": call_id,
            },
        }
    )
