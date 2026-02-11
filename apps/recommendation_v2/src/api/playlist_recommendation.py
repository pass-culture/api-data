from fastapi import APIRouter

from schemas.playlist_recommendation import RecommendationMetadata
from schemas.playlist_recommendation import RecommendationResponse


router = APIRouter()


@router.post("/playlist_recommendation/{user_id}")
async def get_playlist(user_id: str) -> RecommendationResponse:
    return RecommendationResponse(
        playlist_recommended_offers=["1", "2", "3"],
        params=RecommendationMetadata(reco_origin="algo", model_origin="model_v1", call_id="call_123"),
    )
