"""
Controller orchestrating the ``/playlist_top_artists/{search_group_name}`` pipeline.

Coordinates database queries across ``artist_top_by_category_mv``, ``similar_artist_mv``,
and ``artist_mv``, and builds the discovery block using the filtering and ranking helpers defined here.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.artist import Artist
from models.artist_top_by_category import ArtistTopByCategory
from models.similar_artists import SimilarArtist
from schemas.playlist_top_artists import DiscoveryArtist
from schemas.playlist_top_artists import PlaylistTopArtistsParams
from schemas.playlist_top_artists import PlaylistTopArtistsResult
from schemas.playlist_top_artists import TopArtist
from schemas.playlist_top_artists import TopArtistsSearchGroupNameEnum
from schemas.similar_artists import MatchedArtist
from services.logger import call_id_context
from services.logger import logger


# Number of top artists fetched from `artist_top_by_category_mv` per category.
TOP_ARTISTS_COUNT = 3


async def _fetch_top_artists_for_category(
    db: AsyncSession,
    search_group_name: TopArtistsSearchGroupNameEnum,
    score_name: str,
    limit: int,
) -> list[TopArtist]:
    """Fetch the category's top-ranked artists from `artist_top_by_category_mv`."""
    statement = (
        select(ArtistTopByCategory.artist_id, ArtistTopByCategory.category_rank)
        .where(
            ArtistTopByCategory.search_group_name == search_group_name.value,
            ArtistTopByCategory.score_name == score_name,
        )
        .order_by(ArtistTopByCategory.category_rank.asc())
        .limit(limit)
    )
    query_result = await db.execute(statement)

    return [TopArtist(artist_id=row.artist_id, category_rank=row.category_rank) for row in query_result.all()]


async def _fetch_similar_artists_by_top_artist_id(
    db: AsyncSession,
    top_artist_ids: list[str],
) -> dict[str, list[MatchedArtist]]:
    """Fetch the ordered similarity lists from `similar_artist_mv` for the given top artists."""
    if not top_artist_ids:
        return {}

    statement = select(SimilarArtist.artist_id, SimilarArtist.similar_artists_json).where(
        SimilarArtist.artist_id.in_(top_artist_ids)
    )
    query_result = await db.execute(statement)

    return {
        row.artist_id: [MatchedArtist(**item) for item in (row.similar_artists_json or [])]
        for row in query_result.all()
    }


def _extract_discovery_candidate_artist_ids(
    similar_artists_by_top_artist_id: dict[str, list[MatchedArtist]],
    excluded_top_artist_ids: list[str],
) -> list[str]:
    """Collect unique candidate artist IDs from the top artists' similarity lists, excluding the tops themselves."""
    excluded_ids_set = set(excluded_top_artist_ids)

    candidate_artist_ids = {
        candidate.artist_id_match
        for similar_artists in similar_artists_by_top_artist_id.values()
        for candidate in similar_artists
        if candidate.artist_id_match not in excluded_ids_set
    }

    return list(candidate_artist_ids)


async def _fetch_artists_by_artist_id(
    db: AsyncSession,
    artist_ids: list[str],
) -> dict[str, Artist]:
    """Fetch `Artist` records from `artist_mv` keyed by `artist_id`."""
    if not artist_ids:
        return {}

    statement = select(Artist).where(Artist.artist_id.in_(artist_ids))
    query_result = await db.execute(statement)

    return {artist.artist_id: artist for artist in query_result.scalars().all()}


def _has_bookable_offer_in_main_category(artist: Artist | None) -> bool:
    """Return True if the artist is known and has a bookable offer in their main category (fail-closed)."""
    return artist is not None and artist.main_search_group_name_has_bookable_offer is True


def _matches_target_search_group(
    artist: Artist | None,
    target_search_group: TopArtistsSearchGroupNameEnum,
) -> bool:
    """Return True if the artist is known and their main category matches `target_search_group` (fail-closed)."""
    return artist is not None and artist.main_search_group_name == target_search_group.value


def is_eligible_discovery_candidate(
    artist: Artist | None,
    target_search_group: TopArtistsSearchGroupNameEnum,
    *,
    filter_has_bookable_offer_in_main_category: bool,
    filter_main_category_matches_search_group_name: bool,
) -> bool:
    """
    Return whether a candidate artist passes the enabled discovery filters.

    Missing metadata (`artist is None` or `NULL` columns in `artist_mv`) is treated
    as unknown and rejected whenever the corresponding filter is enabled (fail-closed).
    """
    passes_bookable_offer_filter = (
        not filter_has_bookable_offer_in_main_category or _has_bookable_offer_in_main_category(artist)
    )
    passes_category_match_filter = not filter_main_category_matches_search_group_name or _matches_target_search_group(
        artist, target_search_group
    )

    return passes_bookable_offer_filter and passes_category_match_filter


# ---------------------------------------------------------------------------
# Business logic (aggregation, ranking, pipeline orchestration)
# ---------------------------------------------------------------------------


def compute_candidate_sort_key(
    ranks_by_top_artist: dict[str, int],
    top_artist_ids: list[str] | None = None,
) -> tuple[int, float, int]:
    """
    Return `(-appearance_count, avg_rank, best_top_artist_position)`.

    Sort by overlap count DESC, then average rank ASC, then by the position (0 = top 1, 1 = top 2, ...)
    of the best-ranked top artist the candidate is similar to ASC (tie-breaker).
    """
    appearance_count = len(ranks_by_top_artist)
    average_similarity_rank = sum(ranks_by_top_artist.values()) / appearance_count

    top_artist_positions = {artist_id: position for position, artist_id in enumerate(top_artist_ids or [])}
    best_top_artist_position = min(
        (top_artist_positions.get(artist_id, len(top_artist_positions)) for artist_id in ranks_by_top_artist),
    )

    return (-appearance_count, average_similarity_rank, best_top_artist_position)


def _build_discovery_artist(candidate_artist_id: str, ranks_by_top_artist: dict[str, int]) -> DiscoveryArtist:
    """Build a `DiscoveryArtist` schema from aggregated similarity ranks across top artists."""
    appearance_count = len(ranks_by_top_artist)
    average_similarity_rank = round(sum(ranks_by_top_artist.values()) / appearance_count, 2)

    return DiscoveryArtist(
        artist_id=candidate_artist_id,
        appearance_count=appearance_count,
        avg_rank=average_similarity_rank,
        source_top_artist_ids=list(ranks_by_top_artist.keys()),
        ranks_by_top_artist=ranks_by_top_artist,
    )


def build_favored_discovery_artists(  # noqa: PLR0913
    top_artist_ids: list[str],
    similar_artists_by_top: dict[str, list[MatchedArtist]],
    *,
    filter_has_bookable_offer_in_main_category: bool,
    filter_main_category_matches_search_group_name: bool,
    target_size: int,
    search_group_name: TopArtistsSearchGroupNameEnum,
    artists_by_id: dict[str, Artist],
) -> list[DiscoveryArtist]:
    """
    Build the discovery block by favoring candidates similar to multiple top artists.

    Algorithm Overview ("Favor Overlap"):
    =====================================
        Top Artist 1 ──► [Cand A (rank 3), Cand B (rank 1), Cand C (rank 2)] ──┐
        Top Artist 2 ──► [Cand A (rank 1), Cand B (rank 2)]                  ──┼──► Aggregate & Filter
        Top Artist 3 ──► [Cand A (rank 2)]                                   ──┘
                                                                                      │
                                                                                      ▼
        Ranked Discovery Candidates (sorted by appearance_count DESC, avg_rank ASC):
          1. Cand A  (appearance_count = 3, avg_rank = 2.0)
          2. Cand B  (appearance_count = 2, avg_rank = 1.5)
          3. Cand C  (appearance_count = 1, avg_rank = 2.0)
    """
    excluded_top_artist_ids = set(top_artist_ids)
    candidate_ranks_by_top_artist: dict[str, dict[str, int]] = {}

    # 1. Aggregate similarity ranks per eligible candidate across all top artists
    for top_artist_id in top_artist_ids:
        for similar_candidate in similar_artists_by_top.get(top_artist_id, []):
            candidate_artist_id = similar_candidate.artist_id_match

            if candidate_artist_id in excluded_top_artist_ids:
                continue

            candidate_artist = artists_by_id.get(candidate_artist_id)
            if not is_eligible_discovery_candidate(
                candidate_artist,
                search_group_name,
                filter_has_bookable_offer_in_main_category=filter_has_bookable_offer_in_main_category,
                filter_main_category_matches_search_group_name=filter_main_category_matches_search_group_name,
            ):
                continue

            candidate_ranks_by_top_artist.setdefault(candidate_artist_id, {})[top_artist_id] = similar_candidate.rank

    # 2. Rank candidates by appearance count (DESC) then average similarity rank (ASC)
    ranked_candidates = sorted(
        candidate_ranks_by_top_artist.items(),
        key=lambda item: compute_candidate_sort_key(item[1], top_artist_ids),
    )

    # 3. Build the final capped list of DiscoveryArtist objects
    return [
        _build_discovery_artist(candidate_artist_id, ranks_by_top_artist)
        for candidate_artist_id, ranks_by_top_artist in ranked_candidates[:target_size]
    ]


async def generate_playlist_top_artists(
    db: AsyncSession,
    *,
    search_group_name: TopArtistsSearchGroupNameEnum,
    filter_has_bookable_offer_in_main_category: bool,
    filter_main_category_matches_search_group_name: bool,
    score_name: str,
    discovery_size: int,
) -> PlaylistTopArtistsResult:
    """
    Compose the top-artists discovery playlist for a given category.

    Pipeline Architecture:
    ======================
        [search_group_name, score_name]
                       │
                       ▼
        1. Fetch Top 3 Artists (artist_top_by_category_mv)
                       │
                       ├──► (Empty?) ──► Return empty PlaylistTopArtistsResult
                       │
                       ▼
        2. Fetch Similar Artists for each Top Artist (similar_artist_mv)
                       │
                       ▼
        3. Fetch Candidate Artist Metadata (artist_mv)
           (only executed if filter_has_bookable_offer_in_main_category or
           filter_main_category_matches_search_group_name is True)
                       │
                       ▼
        4. Aggregate, Filter & Rank Discovery Candidates (build_favored_discovery_artists)
                       │
                       ▼
        [PlaylistTopArtistsResult(top_artists, discovery_artists, params)]
    """
    # 1. Context initialization
    call_id = str(uuid.uuid4())
    call_id_context.set(call_id)

    playlist_params = PlaylistTopArtistsParams(
        search_group_name=search_group_name.value,
        score_name=score_name,
        call_id=call_id,
    )

    logger.info(
        "🚀 Starting playlist_top_artists pipeline.",
        extra={
            "search_group_name": search_group_name.value,
            "filter_has_bookable_offer_in_main_category": filter_has_bookable_offer_in_main_category,
            "filter_main_category_matches_search_group_name": filter_main_category_matches_search_group_name,
            "score_name": score_name,
            "discovery_size": discovery_size,
        },
    )

    # 2. Fetch the category's top artists
    top_artists = await _fetch_top_artists_for_category(
        db=db,
        search_group_name=search_group_name,
        score_name=score_name,
        limit=TOP_ARTISTS_COUNT,
    )

    if not top_artists:
        logger.warning(
            "No top artists found for the given search_group_name.",
            extra={"search_group_name": search_group_name.value, "score_name": score_name},
        )
        return PlaylistTopArtistsResult(
            top_artists=[],
            discovery_artists=[],
            params=playlist_params,
        )

    top_artist_ids = [top_artist.artist_id for top_artist in top_artists]
    logger.info(
        "🏆 Top artists fetched for category.",
        extra={
            "search_group_name": search_group_name.value,
            "top_artists_count": len(top_artists),
            "top_artist_ids": top_artist_ids,
        },
    )

    # 3. Fetch similar artists for the top artists and extract discovery candidates
    similar_artists_by_top_artist_id = await _fetch_similar_artists_by_top_artist_id(db, top_artist_ids)
    candidate_artist_ids = _extract_discovery_candidate_artist_ids(
        similar_artists_by_top_artist_id=similar_artists_by_top_artist_id,
        excluded_top_artist_ids=top_artist_ids,
    )
    logger.info(
        "🔎 Similar artists fetched and discovery candidates extracted.",
        extra={
            "top_artists_with_similars_count": len(similar_artists_by_top_artist_id),
            "candidate_artists_count": len(candidate_artist_ids),
        },
    )

    # 4. Fetch category/eligibility metadata only when at least one filter requires it
    should_fetch_artist_metadata = (
        filter_has_bookable_offer_in_main_category or filter_main_category_matches_search_group_name
    ) and bool(candidate_artist_ids)
    if should_fetch_artist_metadata:
        artists_by_id = await _fetch_artists_by_artist_id(db, candidate_artist_ids)
        logger.info(
            "📋 Candidate artist metadata fetched from artist_mv.",
            extra={
                "requested_candidates_count": len(candidate_artist_ids),
                "fetched_artists_count": len(artists_by_id),
            },
        )
    else:
        artists_by_id = {}
        logger.info(
            "⏭️ Skipping artist_mv metadata lookup.",
            extra={
                "filter_has_bookable_offer_in_main_category": filter_has_bookable_offer_in_main_category,
                "filter_main_category_matches_search_group_name": filter_main_category_matches_search_group_name,
                "candidate_artists_count": len(candidate_artist_ids),
            },
        )

    # 5. Build favored discovery artists and return the composed result
    discovery_artists = build_favored_discovery_artists(
        top_artist_ids=top_artist_ids,
        similar_artists_by_top=similar_artists_by_top_artist_id,
        filter_has_bookable_offer_in_main_category=filter_has_bookable_offer_in_main_category,
        filter_main_category_matches_search_group_name=filter_main_category_matches_search_group_name,
        target_size=discovery_size,
        search_group_name=search_group_name,
        artists_by_id=artists_by_id,
    )

    logger.info(
        "✅ Top artists playlist composed.",
        extra={
            "search_group_name": search_group_name.value,
            "top_artists_count": len(top_artists),
            "discovery_artists_count": len(discovery_artists),
        },
    )

    return PlaylistTopArtistsResult(
        top_artists=top_artists,
        discovery_artists=discovery_artists,
        params=playlist_params,
    )
