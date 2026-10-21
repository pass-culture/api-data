"""
Pydantic schemas and enumerations for the ``/playlist_top_artists/{search_group_name}`` endpoint.
"""

from enum import Enum

from pydantic import BaseModel

from schemas.categories import SearchGroupNameEnum


class TopArtistsSearchGroupNameEnum(str, Enum):
    """
    Categories supported by the ``/playlist_top_artists/{search_group_name}`` endpoint.

    This is a restricted subset of :class:`schemas.categories.SearchGroupNameEnum`
    corresponding to the categories populated in ``artist_top_by_category_mv``.
    """

    CINEMA = SearchGroupNameEnum.CINEMA.value
    LIVRES = SearchGroupNameEnum.LIVRES.value
    MUSIQUE = SearchGroupNameEnum.MUSIQUE.value


class TopArtist(BaseModel):
    """
    Represents one of the top-ranked artists for a category.

    Attributes:
        artist_id (str): Unique identifier of the top artist.
        category_rank (int): 1-based rank of the artist within the category.
    """

    artist_id: str
    category_rank: int


class DiscoveryArtist(BaseModel):
    """
    Represents a discovery artist selected from the similarity lists of the top artists.

    Candidates appearing in the similarity lists of *multiple* top artists are
    prioritized first (by ``appearance_count`` descending), with ties broken by
    ``avg_rank`` ascending (lower rank = higher similarity).

    Attributes:
        artist_id (str): Unique identifier of the discovery artist.
        appearance_count (int): Number of top artists whose similarity list includes this artist.
        avg_rank (float): Mean similarity rank across the top artists' lists in which it appears.
        source_top_artist_ids (list[str]): Ordered list of top artist IDs that matched this candidate.
        ranks_by_top_artist (dict[str, int]): Mapping of ``top_artist_id -> similarity_rank``.
    """

    artist_id: str
    appearance_count: int
    avg_rank: float
    source_top_artist_ids: list[str]
    ranks_by_top_artist: dict[str, int]


class PlaylistTopArtistsParams(BaseModel):
    """
    Execution metadata returned alongside the playlist response for traceability.

    Attributes:
        search_group_name (str): Category for which the playlist was generated.
        score_name (str): Scoring variant used to select the category's top artists.
        call_id (str): Unique UUID identifying the pipeline execution.
    """

    search_group_name: str
    score_name: str
    call_id: str


class PlaylistTopArtistsResult(BaseModel):
    """
    Internal pipeline output containing the detailed composition of top and discovery artists.

    Attributes:
        top_artists (list[TopArtist]): Ordered list of the category's top artists.
        discovery_artists (list[DiscoveryArtist]): Ordered list of favored discovery artists.
        params (PlaylistTopArtistsParams): Execution parameters and traceability metadata.
    """

    top_artists: list[TopArtist]
    discovery_artists: list[DiscoveryArtist]
    params: PlaylistTopArtistsParams


class PlaylistTopArtistsResponse(BaseModel):
    """
    Public HTTP response for ``/playlist_top_artists/{search_group_name}``.

    Attributes:
        playlist_artists (list[str]): Flat ordered list of artist IDs
            (top artists first, followed by discovery artists).
        params (PlaylistTopArtistsParams): Execution parameters and traceability metadata.
    """

    playlist_artists: list[str]
    params: PlaylistTopArtistsParams
