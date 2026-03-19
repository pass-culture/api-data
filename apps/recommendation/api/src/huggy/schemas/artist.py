from pydantic import BaseModel


class MatchedArtist(BaseModel):
    artist_id_match: str
    rank: int


class SimilarArtistsParams(BaseModel):
    artist_id: str
    call_id: str


class SimilarArtistsResponse(BaseModel):
    similar_artists: list[MatchedArtist]
    params: SimilarArtistsParams
