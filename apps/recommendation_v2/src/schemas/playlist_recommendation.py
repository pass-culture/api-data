from typing import List

from pydantic import BaseModel


class RecommendationMetadata(BaseModel):
    reco_origin: str
    model_origin: str
    call_id: str


class RecommendationResponse(BaseModel):
    playlist_recommended_offers: List[str]
    params: RecommendationMetadata
