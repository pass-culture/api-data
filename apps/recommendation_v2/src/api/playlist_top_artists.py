"""
FastAPI router for the ``/playlist_top_artists/{search_group_name}`` endpoint.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Path
from fastapi import Query
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from controllers.pipeline_playlist_top_artists import generate_playlist_top_artists
from schemas.playlist_top_artists import PlaylistTopArtistsResponse
from schemas.playlist_top_artists import TopArtistsSearchGroupNameEnum
from services.db import get_database_session
from services.logger import logger
from utils.benchmark import log_execution_time


router = APIRouter()

# Default number of discovery artists returned alongside the top artists.
DEFAULT_DISCOVERY_PLAYLIST_SIZE = 7


@dataclass(frozen=True)
class TopArtistsDevelopmentQueryParams:
    """
    Holds tuning parameters that are only customizable as query parameters in local development.

    Attributes:
        score_name (str): Scoring variant used to rank the category's top artists.
        discovery_size (int): Number of discovery artists to include after the top artists.
        filter_has_bookable_offer_in_main_category (bool): Exclude discovery candidates without a confirmed
            bookable offer in their main category.
        filter_main_category_matches_search_group_name (bool): Exclude discovery candidates whose main category
            differs from ``search_group_name``.
    """

    filter_has_bookable_offer_in_main_category: bool
    filter_main_category_matches_search_group_name: bool
    score_name: str
    discovery_size: int


def _get_default_development_query_params() -> TopArtistsDevelopmentQueryParams:
    """
    Return fixed default tuning parameters for non-local environments (dev, stg, prod),
    where ``score_name``, ``discovery_size``, ``filter_has_bookable_offer_in_main_category``, and
    ``filter_main_category_matches_search_group_name`` are not exposed in the public HTTP API.
    """
    return TopArtistsDevelopmentQueryParams(
        filter_has_bookable_offer_in_main_category=True,
        filter_main_category_matches_search_group_name=True,
        score_name=settings.PLAYLIST_TOP_ARTISTS_DEFAULT_SCORE_NAME,
        discovery_size=DEFAULT_DISCOVERY_PLAYLIST_SIZE,
    )


def _get_local_development_query_params(
    *,
    filter_has_bookable_offer_in_main_category: Annotated[
        bool,
        Query(
            description="(local dev only) Exclude discovery candidates without a confirmed bookable offer "
            "in their main category (artist_mv.main_search_group_name_has_bookable_offer)."
        ),
    ] = True,
    filter_main_category_matches_search_group_name: Annotated[
        bool,
        Query(
            description="(local dev only) Exclude discovery candidates whose main category "
            "(artist_mv.main_search_group_name) differs from `search_group_name`."
        ),
    ] = True,
    score_name: Annotated[
        str,
        Query(description="(local dev only) The scoring variant used to rank the category's top artists."),
    ] = settings.PLAYLIST_TOP_ARTISTS_DEFAULT_SCORE_NAME,
    discovery_size: Annotated[
        int,
        Query(description="(local dev only) Number of discovery artists to return.", ge=1, le=50),
    ] = DEFAULT_DISCOVERY_PLAYLIST_SIZE,
) -> TopArtistsDevelopmentQueryParams:
    """
    Expose ``score_name``, ``discovery_size``, ``filter_has_bookable_offer_in_main_category``, and
    ``filter_main_category_matches_search_group_name`` as optional query parameters when running locally.
    """
    return TopArtistsDevelopmentQueryParams(
        filter_has_bookable_offer_in_main_category=filter_has_bookable_offer_in_main_category,
        filter_main_category_matches_search_group_name=filter_main_category_matches_search_group_name,
        score_name=score_name,
        discovery_size=discovery_size,
    )


get_development_query_params = (
    _get_local_development_query_params if settings.IS_LOCAL else _get_default_development_query_params
)


@router.get(
    "/playlist_top_artists/{search_group_name}",
    response_model=PlaylistTopArtistsResponse,
    summary="Generate a top-artists discovery playlist for a given category",
)
@log_execution_time
async def get_playlist_top_artists(
    db: Annotated[AsyncSession, Depends(get_database_session)],
    search_group_name: Annotated[
        TopArtistsSearchGroupNameEnum,
        Path(
            description="The category (search_group_name) to find top artists for. "
            "Only CINEMA, LIVRES and MUSIQUE are currently supported.",
            json_schema_extra={"example": "CINEMA"},
        ),
    ],
    development_params: Annotated[TopArtistsDevelopmentQueryParams, Depends(get_development_query_params)],
) -> PlaylistTopArtistsResponse:
    """
    Generate a "top artists" discovery playlist for a given category.

    Returns ``playlist_artists``: a flat ordered list of artist IDs containing the
    category's 3 top artists first, followed by the favored discovery artists.

    ---

    **Path parameters**

    - ``search_group_name``: Category used to look up the top artists (``artist_top_by_category_mv``).
      Only ``CINEMA``, ``LIVRES`` and ``MUSIQUE`` are currently supported.

    The category's 3 top artists are fetched first, then their similar artists
    (same source as ``/similar_artists/{artist_id}``) are aggregated: candidates similar
    to *several* of the 3 top artists are favored (ranked first), with ties broken by their
    average similarity rank across the lists they appear in. Candidates duplicating one
    of the 3 tops are always excluded.
    """
    logger.info(
        "📥 Incoming playlist_top_artists request.",
        extra={
            "search_group_name": search_group_name.value,
            "filter_has_bookable_offer_in_main_category": (
                development_params.filter_has_bookable_offer_in_main_category
            ),
            "filter_main_category_matches_search_group_name": (
                development_params.filter_main_category_matches_search_group_name
            ),
            "score_name": development_params.score_name,
            "discovery_size": development_params.discovery_size,
        },
    )

    pipeline_result = await generate_playlist_top_artists(
        db=db,
        search_group_name=search_group_name,
        filter_has_bookable_offer_in_main_category=(development_params.filter_has_bookable_offer_in_main_category),
        filter_main_category_matches_search_group_name=(
            development_params.filter_main_category_matches_search_group_name
        ),
        score_name=development_params.score_name,
        discovery_size=development_params.discovery_size,
    )

    top_artist_ids = [artist.artist_id for artist in pipeline_result.top_artists]
    discovery_artist_ids = [artist.artist_id for artist in pipeline_result.discovery_artists]
    playlist_artist_ids = [*top_artist_ids, *discovery_artist_ids]

    logger.info(
        "✅ playlist_top_artists request completed.",
        extra={
            "search_group_name": search_group_name.value,
            "call_id": pipeline_result.params.call_id,
            "top_artists_count": len(top_artist_ids),
            "discovery_artists_count": len(discovery_artist_ids),
        },
    )

    return PlaylistTopArtistsResponse(
        playlist_artists=playlist_artist_ids,
        params=pipeline_result.params,
    )
