from enum import StrEnum

from pydantic import BaseModel

from schemas.playlist_recommendation import RecommendationMetadata


class SimilarOfferModelChoices(StrEnum):
    graph = "graph"
    coreservation = "coreservation"


class SimilarOfferResponse(BaseModel):
    """
    Response model for similar offer recommendations.

    This model defines the structure of the JSON response sent back to the client
    after processing a similar offer recommendation request. It includes a list
    of recommended offer IDs and associated metadata about the recommendation.
    """

    results: list[str]
    params: RecommendationMetadata
    from_cache: bool = False
