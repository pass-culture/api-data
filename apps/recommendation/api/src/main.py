import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from huggy.core.model_engine.recommendation import Recommendation
from huggy.core.model_engine.similar_offer import SimilarOffer
from huggy.crud.offer import Offer
from huggy.crud.user import UserContextDB
from huggy.database.session import get_db
from huggy.schemas.playlist_params import (
    GetSimilarOfferPlaylistParams,
    PlaylistParams,
    PostSimilarOfferPlaylistParams,
)
from huggy.utils.cloud_logging import logger
from huggy.utils.env_vars import (
    API_TOKEN,
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


@app.post(
    "/similar_offers/{offer_id}",
    dependencies=[Depends(setup_trace), Depends(check_token)],
)
async def similar_offers(
    offer_id: str,
    token: str,
    playlist_params: PostSimilarOfferPlaylistParams,
    latitude: float = None,  # venue_latitude
    longitude: float = None,  # venue_longitude
    db: AsyncSession = Depends(get_db),
    call_id: str = Depends(get_call_id),
):
    user = await UserContextDB().get_user_context(
        db, playlist_params.user_id, latitude, longitude
    )

    offer = await Offer().get_offer_characteristics(db, offer_id, latitude, longitude)

    scoring = SimilarOffer(user, offer, playlist_params, call_id=call_id)

    offer_recommendations = await scoring.get_scoring(db)

    log_extra_data = {
        "user_id": user.user_id,
        "offer_id": offer.offer_id,
        "iris_id": user.iris_id,
        "call_id": call_id,
        "reco_origin": scoring.reco_origin,
        "retrieval_model_name": scoring.scorer.retrieval_endpoints[
            0
        ].model_display_name,
        "retrieval_model_version": scoring.scorer.retrieval_endpoints[0].model_version,
        "retrieval_endpoint_name": scoring.scorer.retrieval_endpoints[0].endpoint_name,
        "ranking_model_name": scoring.scorer.ranking_endpoint.model_display_name,
        "ranking_model_version": scoring.scorer.ranking_endpoint.model_version,
        "ranking_endpoint_name": scoring.scorer.ranking_endpoint.endpoint_name,
        "recommended_offers": offer_recommendations,
    }

    logger.info(
        f"Get similar offer of offer_id {offer.offer_id} for user {user.user_id}",
        extra=log_extra_data,
    )

    await scoring.save_recommendation(db, offer_recommendations)

    return jsonable_encoder(
        {
            "results": offer_recommendations,
            "params": {
                "reco_origin": scoring.reco_origin,
                "retrieval_model_endpoint": scoring.scorer.retrieval_endpoints[
                    0
                ].endpoint_name,
                "retrieval_model_name": scoring.scorer.retrieval_endpoints[
                    0
                ].model_display_name,
                "retrieval_model_version": scoring.scorer.retrieval_endpoints[
                    0
                ].model_version,
                "ranking_model_name": scoring.scorer.ranking_endpoint.model_display_name,
                "ranking_model_version": scoring.scorer.ranking_endpoint.model_version,
                "ranking_endpoint_name": scoring.scorer.ranking_endpoint.endpoint_name,
                "geo_located": user.is_geolocated,
                "call_id": call_id,
            },
        }
    )


@app.get(
    "/similar_offers/{offer_id}",
    dependencies=[Depends(setup_trace), Depends(check_token)],
)
async def similar_offers(
    offer_id: str,
    token: str,
    playlist_params: GetSimilarOfferPlaylistParams = Depends(),
    latitude: float = None,  # venue_latitude
    longitude: float = None,  # venue_longitude
    db: AsyncSession = Depends(get_db),
    call_id: str = Depends(get_call_id),
):
    user = await UserContextDB().get_user_context(
        db, playlist_params.user_id, latitude, longitude
    )  # corriger pour avoir la latitude / longitude de l'user (et non de la venue)

    offer = await Offer().get_offer_characteristics(db, offer_id, latitude, longitude)

    scoring = SimilarOffer(user, offer, playlist_params, call_id=call_id)

    offer_recommendations = await scoring.get_scoring(db)
    # fallback to reco
    if len(offer_recommendations) == 0:
        scoring = Recommendation(user, params_in=playlist_params)
        offer_recommendations = await scoring.get_scoring(db)

    log_extra_data = {
        "user_id": user.user_id,
        "offer_id": offer.offer_id,
        "iris_id": user.iris_id,
        "call_id": call_id,
        "reco_origin": scoring.reco_origin,
        "retrieval_model_name": scoring.scorer.retrieval_endpoints[
            0
        ].model_display_name,
        "retrieval_model_version": scoring.scorer.retrieval_endpoints[0].model_version,
        "retrieval_endpoint_name": scoring.scorer.retrieval_endpoints[0].endpoint_name,
        "ranking_model_name": scoring.scorer.ranking_endpoint.model_display_name,
        "ranking_model_version": scoring.scorer.ranking_endpoint.model_version,
        "ranking_endpoint_name": scoring.scorer.ranking_endpoint.endpoint_name,
        "recommended_offers": offer_recommendations,
    }

    logger.info(
        f"Get similar offer of offer_id {offer.offer_id} for user {user.user_id}",
        extra=jsonable_encoder(log_extra_data),
    )

    await scoring.save_recommendation(db, offer_recommendations)

    return jsonable_encoder(
        {
            "results": offer_recommendations,
            "params": {
                "reco_origin": scoring.reco_origin,
                "retrieval_model_endpoint": scoring.scorer.retrieval_endpoints[
                    0
                ].endpoint_name,
                "retrieval_model_name": scoring.scorer.retrieval_endpoints[
                    0
                ].model_display_name,
                "retrieval_model_version": scoring.scorer.retrieval_endpoints[
                    0
                ].model_version,
                "ranking_model_name": scoring.scorer.ranking_endpoint.model_display_name,
                "ranking_model_version": scoring.scorer.ranking_endpoint.model_version,
                "ranking_endpoint_name": scoring.scorer.ranking_endpoint.endpoint_name,
                "geo_located": user.is_geolocated,
                "call_id": call_id,
            },
        }
    )


@app.post(
    "/playlist_recommendation/{user_id}",
    dependencies=[Depends(setup_trace), Depends(check_token)],
)
async def playlist_recommendation(
    user_id: str,
    token: str,
    playlist_params: PlaylistParams,
    latitude: float = None,
    longitude: float = None,
    modelEnpoint: str = None,
    db: AsyncSession = Depends(get_db),
    call_id: str = Depends(get_call_id),
):
    user = await UserContextDB().get_user_context(db, user_id, latitude, longitude)
    if modelEnpoint is not None:
        playlist_params.model_endpoint = modelEnpoint

    scoring = Recommendation(user, params_in=playlist_params, call_id=call_id)

    user_recommendations = await scoring.get_scoring(db)

    log_extra_data = {
        "user_id": user.user_id,
        "iris_id": user.iris_id,
        "call_id": call_id,
        "reco_origin": scoring.reco_origin,
        "retrieval_model_name": scoring.scorer.retrieval_endpoints[
            0
        ].model_display_name,
        "retrieval_model_version": scoring.scorer.retrieval_endpoints[0].model_version,
        "retrieval_endpoint_name": scoring.scorer.retrieval_endpoints[0].endpoint_name,
        "ranking_model_name": scoring.scorer.ranking_endpoint.model_display_name,
        "ranking_model_version": scoring.scorer.ranking_endpoint.model_version,
        "ranking_endpoint_name": scoring.scorer.ranking_endpoint.endpoint_name,
        "recommended_offers": user_recommendations,
    }

    logger.info(
        f"Get recommendations for user {user.user_id}",
        extra=jsonable_encoder(log_extra_data),
    )

    await scoring.save_recommendation(db, user_recommendations)
    return jsonable_encoder(
        {
            "playlist_recommended_offers": user_recommendations,
            "params": {
                "reco_origin": scoring.reco_origin,
                "retrieval_model_endpoint": scoring.scorer.retrieval_endpoints[
                    0
                ].endpoint_name,
                "retrieval_model_name": scoring.scorer.retrieval_endpoints[
                    0
                ].model_display_name,
                "retrieval_model_version": scoring.scorer.retrieval_endpoints[
                    0
                ].model_version,
                "ranking_model_name": scoring.scorer.ranking_endpoint.model_display_name,
                "ranking_model_version": scoring.scorer.ranking_endpoint.model_version,
                "ranking_endpoint_name": scoring.scorer.ranking_endpoint.endpoint_name,
                "geo_located": user.is_geolocated,
                "call_id": call_id,
            },
        }
    )
