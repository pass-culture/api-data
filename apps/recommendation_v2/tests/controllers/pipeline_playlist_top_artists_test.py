"""
Integration tests for the ``controllers.pipeline_playlist_top_artists`` module.
"""

import pytest

from config import settings
from controllers.pipeline_playlist_top_artists import build_favored_discovery_artists
from controllers.pipeline_playlist_top_artists import compute_candidate_sort_key
from controllers.pipeline_playlist_top_artists import generate_playlist_top_artists
from models.artist import Artist
from schemas.playlist_top_artists import TopArtistsSearchGroupNameEnum
from schemas.similar_artists import MatchedArtist

from tests.factories.models import ArtistFactory
from tests.factories.models import ArtistTopByCategoryFactory
from tests.factories.models import SimilarArtistFactory


DEFAULT_SCORE_NAME = settings.PLAYLIST_TOP_ARTISTS_DEFAULT_SCORE_NAME

TOP_ARTIST_1 = "11111111-1111-1111-1111-111111111111"
TOP_ARTIST_2 = "22222222-2222-2222-2222-222222222222"
TOP_ARTIST_3 = "33333333-3333-3333-3333-333333333333"

SHARED_CANDIDATE = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
SOLO_CANDIDATE = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

TOP_1 = "top-1"
TOP_2 = "top-2"
TOP_3 = "top-3"

CANDIDATE_IN_ALL_THREE = "candidate-in-all-three"
CANDIDATE_IN_TWO = "candidate-in-two"
CANDIDATE_ONLY_TOP_1 = "candidate-only-top-1"

CINEMA = "CINEMA"
MUSIQUE = "MUSIQUE"


async def _run_playlist_top_artists_pipeline(
    db,
    *,
    filter_has_bookable_offer_in_main_category: bool = True,
    filter_main_category_matches_search_group_name: bool = True,
    search_group_name: TopArtistsSearchGroupNameEnum,
    discovery_size: int = 7,
):
    """
    Invoke :func:`generate_playlist_top_artists` with sensible test defaults.
    """
    return await generate_playlist_top_artists(
        db=db,
        search_group_name=search_group_name,
        filter_has_bookable_offer_in_main_category=filter_has_bookable_offer_in_main_category,
        filter_main_category_matches_search_group_name=filter_main_category_matches_search_group_name,
        score_name=DEFAULT_SCORE_NAME,
        discovery_size=discovery_size,
    )


async def _seed_eligible_discovery_candidate(
    artist_id: str,
    search_group_name: str = TopArtistsSearchGroupNameEnum.CINEMA.value,
) -> None:
    """
    Seed ``artist_mv`` so that the given candidate passes both default category filters.
    """
    await ArtistFactory.create_async(
        artist_id=artist_id,
        main_search_group_name=search_group_name,
        main_search_group_name_has_bookable_offer=True,
    )


async def _seed_top_artists_trio() -> None:
    """
    Seed the top 3 ``CINEMA`` artists alongside a ``MUSIQUE`` noise record.
    """
    top_artists_seed_data = (
        (TOP_ARTIST_1, 1, 9.0),
        (TOP_ARTIST_2, 2, 8.0),
        (TOP_ARTIST_3, 3, 7.0),
    )
    for artist_id, category_rank, score_value in top_artists_seed_data:
        await ArtistTopByCategoryFactory.create_async(
            artist_id=artist_id,
            search_group_name=TopArtistsSearchGroupNameEnum.CINEMA.value,
            score_name=DEFAULT_SCORE_NAME,
            category_rank=category_rank,
            score_value=score_value,
        )

    # Noise: another category must never leak into the CINEMA trio.
    await ArtistTopByCategoryFactory.create_async(
        artist_id="should-not-appear",
        search_group_name=TopArtistsSearchGroupNameEnum.MUSIQUE.value,
        score_name=DEFAULT_SCORE_NAME,
        category_rank=1,
        score_value=9.9,
    )


@pytest.mark.asyncio
async def test_returns_empty_result_when_no_top_artist_found(db_session):
    response = await _run_playlist_top_artists_pipeline(
        db=db_session,
        search_group_name=TopArtistsSearchGroupNameEnum.CINEMA,
    )

    assert response.top_artists == []
    assert response.discovery_artists == []
    assert response.params.search_group_name == TopArtistsSearchGroupNameEnum.CINEMA.value


@pytest.mark.asyncio
async def test_fetches_top_3_artists_ordered_by_category_rank(db_session):
    await _seed_top_artists_trio()

    response = await _run_playlist_top_artists_pipeline(
        db=db_session,
        search_group_name=TopArtistsSearchGroupNameEnum.CINEMA,
    )

    assert [top_artist.artist_id for top_artist in response.top_artists] == [
        TOP_ARTIST_1,
        TOP_ARTIST_2,
        TOP_ARTIST_3,
    ]
    assert [top_artist.category_rank for top_artist in response.top_artists] == [1, 2, 3]


@pytest.mark.asyncio
async def test_discovery_artists_favor_candidates_shared_between_tops(db_session):
    await _seed_top_artists_trio()
    await _seed_eligible_discovery_candidate(SHARED_CANDIDATE)
    await _seed_eligible_discovery_candidate(SOLO_CANDIDATE)

    await SimilarArtistFactory.create_async(
        artist_id=TOP_ARTIST_1,
        similar_artists_json=[
            {"artist_id_match": SHARED_CANDIDATE, "rank": 2},
            {"artist_id_match": SOLO_CANDIDATE, "rank": 1},
        ],
    )
    await SimilarArtistFactory.create_async(
        artist_id=TOP_ARTIST_2,
        similar_artists_json=[{"artist_id_match": SHARED_CANDIDATE, "rank": 1}],
    )

    response = await _run_playlist_top_artists_pipeline(
        db=db_session,
        search_group_name=TopArtistsSearchGroupNameEnum.CINEMA,
    )

    assert response.discovery_artists[0].artist_id == SHARED_CANDIDATE
    assert response.discovery_artists[0].appearance_count == 2
    assert SOLO_CANDIDATE in [artist.artist_id for artist in response.discovery_artists]


@pytest.mark.asyncio
async def test_discovery_size_param_is_respected(db_session):
    await _seed_top_artists_trio()
    for index in range(1, 11):
        await _seed_eligible_discovery_candidate(f"candidate-{index}")

    await SimilarArtistFactory.create_async(
        artist_id=TOP_ARTIST_1,
        similar_artists_json=[{"artist_id_match": f"candidate-{index}", "rank": index} for index in range(1, 11)],
    )

    response = await _run_playlist_top_artists_pipeline(
        db=db_session,
        search_group_name=TopArtistsSearchGroupNameEnum.CINEMA,
        discovery_size=2,
    )

    assert len(response.discovery_artists) == 2


@pytest.mark.asyncio
async def test_filter_has_bookable_offer_in_main_category_defaults_to_true_and_excludes_ineligible_candidate(
    db_session,
):
    await _seed_top_artists_trio()
    await ArtistFactory.create_async(
        artist_id=SOLO_CANDIDATE,
        main_search_group_name=TopArtistsSearchGroupNameEnum.CINEMA.value,
        main_search_group_name_has_bookable_offer=False,
    )
    await SimilarArtistFactory.create_async(
        artist_id=TOP_ARTIST_1,
        similar_artists_json=[{"artist_id_match": SOLO_CANDIDATE, "rank": 1}],
    )

    response = await _run_playlist_top_artists_pipeline(
        db=db_session,
        search_group_name=TopArtistsSearchGroupNameEnum.CINEMA,
    )

    assert response.discovery_artists == []


@pytest.mark.asyncio
async def test_filter_has_bookable_offer_in_main_category_false_keeps_candidate_without_bookable_offer(db_session):
    await _seed_top_artists_trio()
    await ArtistFactory.create_async(
        artist_id=SOLO_CANDIDATE,
        main_search_group_name=TopArtistsSearchGroupNameEnum.CINEMA.value,
        main_search_group_name_has_bookable_offer=False,
    )
    await SimilarArtistFactory.create_async(
        artist_id=TOP_ARTIST_1,
        similar_artists_json=[{"artist_id_match": SOLO_CANDIDATE, "rank": 1}],
    )

    response = await _run_playlist_top_artists_pipeline(
        db=db_session,
        search_group_name=TopArtistsSearchGroupNameEnum.CINEMA,
        filter_has_bookable_offer_in_main_category=False,
    )

    assert [artist.artist_id for artist in response.discovery_artists] == [SOLO_CANDIDATE]


@pytest.mark.asyncio
async def test_filter_main_category_matches_search_group_name_defaults_to_true_and_excludes_other_category_candidate(
    db_session,
):
    await _seed_top_artists_trio()
    await ArtistFactory.create_async(
        artist_id=SOLO_CANDIDATE,
        main_search_group_name=TopArtistsSearchGroupNameEnum.MUSIQUE.value,
        main_search_group_name_has_bookable_offer=True,
    )
    await SimilarArtistFactory.create_async(
        artist_id=TOP_ARTIST_1,
        similar_artists_json=[{"artist_id_match": SOLO_CANDIDATE, "rank": 1}],
    )

    response = await _run_playlist_top_artists_pipeline(
        db=db_session,
        search_group_name=TopArtistsSearchGroupNameEnum.CINEMA,
    )

    assert response.discovery_artists == []


@pytest.mark.asyncio
async def test_filter_main_category_matches_search_group_name_false_keeps_other_category_candidate(db_session):
    await _seed_top_artists_trio()
    await ArtistFactory.create_async(
        artist_id=SOLO_CANDIDATE,
        main_search_group_name=TopArtistsSearchGroupNameEnum.MUSIQUE.value,
        main_search_group_name_has_bookable_offer=True,
    )
    await SimilarArtistFactory.create_async(
        artist_id=TOP_ARTIST_1,
        similar_artists_json=[{"artist_id_match": SOLO_CANDIDATE, "rank": 1}],
    )

    response = await _run_playlist_top_artists_pipeline(
        db=db_session,
        search_group_name=TopArtistsSearchGroupNameEnum.CINEMA,
        filter_main_category_matches_search_group_name=False,
    )

    assert [artist.artist_id for artist in response.discovery_artists] == [SOLO_CANDIDATE]


@pytest.mark.asyncio
async def test_candidate_missing_from_artist_mv_is_excluded_by_default(db_session):
    """
    An artist absent from ``artist_mv`` is treated as unknown and excluded (fail-closed)
    when the default filters are enabled.
    """
    await _seed_top_artists_trio()
    await SimilarArtistFactory.create_async(
        artist_id=TOP_ARTIST_1,
        similar_artists_json=[{"artist_id_match": SOLO_CANDIDATE, "rank": 1}],
    )

    response = await _run_playlist_top_artists_pipeline(
        db=db_session,
        search_group_name=TopArtistsSearchGroupNameEnum.CINEMA,
    )

    assert response.discovery_artists == []


# ---------------------------------------------------------------------------
# build_favored_discovery_artists (unit tests, no database)
# ---------------------------------------------------------------------------


def _build_discovery_artists_with_defaults(
    top_artist_ids: list[str],
    similar_artists_by_top: dict[str, list[MatchedArtist]],
    *,
    filter_has_bookable_offer_in_main_category: bool,
    filter_main_category_matches_search_group_name: bool,
    target_size: int = 10,
    search_group_name: str = CINEMA,
    artists_by_id: dict[str, Artist] | None = None,
):
    """Invoke `build_favored_discovery_artists` with default test values for optional parameters."""
    return build_favored_discovery_artists(
        top_artist_ids=top_artist_ids,
        similar_artists_by_top=similar_artists_by_top,
        search_group_name=TopArtistsSearchGroupNameEnum(search_group_name),
        artists_by_id=artists_by_id or {},
        filter_has_bookable_offer_in_main_category=filter_has_bookable_offer_in_main_category,
        filter_main_category_matches_search_group_name=filter_main_category_matches_search_group_name,
        target_size=target_size,
    )


def test_favors_candidates_appearing_in_several_lists():
    similar_artists_by_top = {
        TOP_1: [
            MatchedArtist(artist_id_match=CANDIDATE_IN_ALL_THREE, rank=7),
            MatchedArtist(artist_id_match=CANDIDATE_IN_TWO, rank=3),
            MatchedArtist(artist_id_match=CANDIDATE_ONLY_TOP_1, rank=1),
        ],
        TOP_2: [
            MatchedArtist(artist_id_match=CANDIDATE_IN_ALL_THREE, rank=7),
            MatchedArtist(artist_id_match=CANDIDATE_IN_TWO, rank=4),
        ],
        TOP_3: [
            MatchedArtist(artist_id_match=CANDIDATE_IN_ALL_THREE, rank=8),
        ],
    }

    discovery_artists = _build_discovery_artists_with_defaults(
        top_artist_ids=[TOP_1, TOP_2, TOP_3],
        similar_artists_by_top=similar_artists_by_top,
        filter_has_bookable_offer_in_main_category=False,
        filter_main_category_matches_search_group_name=False,
        target_size=10,
        search_group_name=CINEMA,
    )

    # The candidate present in all 3 lists must be ranked first, regardless of rank values.
    assert discovery_artists[0].artist_id == CANDIDATE_IN_ALL_THREE
    assert discovery_artists[0].appearance_count == 3
    assert discovery_artists[0].avg_rank == 7.33
    assert set(discovery_artists[0].source_top_artist_ids) == {TOP_1, TOP_2, TOP_3}

    # The candidate present in 2 lists comes next.
    assert discovery_artists[1].artist_id == CANDIDATE_IN_TWO
    assert discovery_artists[1].appearance_count == 2
    assert discovery_artists[1].avg_rank == 3.5
    assert set(discovery_artists[1].source_top_artist_ids) == {TOP_1, TOP_2}

    # The candidate present in only 1 list comes last.
    assert discovery_artists[2].artist_id == CANDIDATE_ONLY_TOP_1
    assert discovery_artists[2].appearance_count == 1
    assert set(discovery_artists[2].source_top_artist_ids) == {TOP_1}


def test_excludes_top_artists_from_discovery_candidates():
    similar_artists_by_top = {
        TOP_1: [
            MatchedArtist(artist_id_match=TOP_2, rank=1),
            MatchedArtist(artist_id_match=CANDIDATE_ONLY_TOP_1, rank=2),
        ],
    }

    discovery_artists = _build_discovery_artists_with_defaults(
        top_artist_ids=[TOP_1, TOP_2, TOP_3],
        similar_artists_by_top=similar_artists_by_top,
        filter_has_bookable_offer_in_main_category=False,
        filter_main_category_matches_search_group_name=False,
        target_size=10,
        search_group_name=CINEMA,
    )

    discovery_ids = [artist.artist_id for artist in discovery_artists]
    assert TOP_2 not in discovery_ids
    assert discovery_ids == [CANDIDATE_ONLY_TOP_1]


def test_result_is_capped_at_target_size():
    similar_artists_by_top = {
        TOP_1: [MatchedArtist(artist_id_match=f"candidate-{index}", rank=index) for index in range(1, 11)],
    }

    discovery_artists = _build_discovery_artists_with_defaults(
        top_artist_ids=[TOP_1],
        similar_artists_by_top=similar_artists_by_top,
        filter_has_bookable_offer_in_main_category=False,
        filter_main_category_matches_search_group_name=False,
        target_size=3,
        search_group_name=CINEMA,
    )

    assert len(discovery_artists) == 3


def test_returns_empty_list_when_no_similar_artists_found():
    discovery_artists = _build_discovery_artists_with_defaults(
        top_artist_ids=[TOP_1, TOP_2, TOP_3],
        similar_artists_by_top={},
        filter_has_bookable_offer_in_main_category=True,
        filter_main_category_matches_search_group_name=True,
    )

    assert discovery_artists == []


def test_filter_has_bookable_offer_in_main_category_excludes_candidates_without_bookable_offer():
    similar_artists_by_top = {
        TOP_1: [
            MatchedArtist(artist_id_match="eligible-candidate", rank=1),
            MatchedArtist(artist_id_match="ineligible-candidate", rank=2),
        ],
    }
    artists_by_id = {
        "eligible-candidate": Artist(
            artist_id="eligible-candidate",
            main_search_group_name=CINEMA,
            main_search_group_name_has_bookable_offer=True,
        ),
        "ineligible-candidate": Artist(
            artist_id="ineligible-candidate",
            main_search_group_name=CINEMA,
            main_search_group_name_has_bookable_offer=False,
        ),
    }

    discovery_artists = _build_discovery_artists_with_defaults(
        top_artist_ids=[TOP_1],
        similar_artists_by_top=similar_artists_by_top,
        search_group_name=CINEMA,
        artists_by_id=artists_by_id,
        filter_has_bookable_offer_in_main_category=True,
        filter_main_category_matches_search_group_name=False,
    )

    discovery_ids = [artist.artist_id for artist in discovery_artists]
    assert discovery_ids == ["eligible-candidate"]


def test_filter_has_bookable_offer_in_main_category_excludes_candidates_missing_from_artist_mv():
    """A candidate absent from `artist_mv` (or with a NULL flag) is treated as unknown
    and excluded (fail-closed), matching the fact that an artist may have no
    determined main category / eligibility yet."""
    similar_artists_by_top = {
        TOP_1: [MatchedArtist(artist_id_match="unknown-candidate", rank=1)],
    }

    discovery_artists = _build_discovery_artists_with_defaults(
        top_artist_ids=[TOP_1],
        similar_artists_by_top=similar_artists_by_top,
        search_group_name=CINEMA,
        artists_by_id={},
        filter_has_bookable_offer_in_main_category=True,
        filter_main_category_matches_search_group_name=False,
    )

    assert discovery_artists == []


def test_filter_has_bookable_offer_in_main_category_disabled_keeps_ineligible_candidates():
    similar_artists_by_top = {
        TOP_1: [MatchedArtist(artist_id_match="ineligible-candidate", rank=1)],
    }
    artists_by_id = {
        "ineligible-candidate": Artist(
            artist_id="ineligible-candidate",
            main_search_group_name=CINEMA,
            main_search_group_name_has_bookable_offer=False,
        ),
    }

    discovery_artists = _build_discovery_artists_with_defaults(
        top_artist_ids=[TOP_1],
        similar_artists_by_top=similar_artists_by_top,
        search_group_name=CINEMA,
        artists_by_id=artists_by_id,
        filter_has_bookable_offer_in_main_category=False,
        filter_main_category_matches_search_group_name=False,
    )

    assert [artist.artist_id for artist in discovery_artists] == ["ineligible-candidate"]


def test_filter_main_category_matches_search_group_name_excludes_candidates_from_another_category():
    similar_artists_by_top = {
        TOP_1: [
            MatchedArtist(artist_id_match="same-category-candidate", rank=1),
            MatchedArtist(artist_id_match="other-category-candidate", rank=2),
        ],
    }
    artists_by_id = {
        "same-category-candidate": Artist(
            artist_id="same-category-candidate",
            main_search_group_name=CINEMA,
            main_search_group_name_has_bookable_offer=True,
        ),
        "other-category-candidate": Artist(
            artist_id="other-category-candidate",
            main_search_group_name=MUSIQUE,
            main_search_group_name_has_bookable_offer=True,
        ),
    }

    discovery_artists = _build_discovery_artists_with_defaults(
        top_artist_ids=[TOP_1],
        similar_artists_by_top=similar_artists_by_top,
        search_group_name=CINEMA,
        artists_by_id=artists_by_id,
        filter_has_bookable_offer_in_main_category=False,
        filter_main_category_matches_search_group_name=True,
    )

    assert [artist.artist_id for artist in discovery_artists] == ["same-category-candidate"]


def test_filter_main_category_matches_search_group_name_excludes_candidates_without_main_category():
    """`main_search_group_name` can be NULL — must not crash and must be excluded."""
    similar_artists_by_top = {
        TOP_1: [MatchedArtist(artist_id_match="no-main-category-candidate", rank=1)],
    }
    artists_by_id = {
        "no-main-category-candidate": Artist(
            artist_id="no-main-category-candidate",
            main_search_group_name=None,
            main_search_group_name_has_bookable_offer=True,
        ),
    }

    discovery_artists = _build_discovery_artists_with_defaults(
        top_artist_ids=[TOP_1],
        similar_artists_by_top=similar_artists_by_top,
        search_group_name=CINEMA,
        artists_by_id=artists_by_id,
        filter_has_bookable_offer_in_main_category=False,
        filter_main_category_matches_search_group_name=True,
    )

    assert discovery_artists == []


def test_exposes_rank_per_top_artist():
    similar_artists_by_top = {
        TOP_1: [MatchedArtist(artist_id_match=CANDIDATE_IN_TWO, rank=4)],
        TOP_2: [MatchedArtist(artist_id_match=CANDIDATE_IN_TWO, rank=2)],
    }

    discovery_artists = _build_discovery_artists_with_defaults(
        top_artist_ids=[TOP_1, TOP_2, TOP_3],
        similar_artists_by_top=similar_artists_by_top,
        filter_has_bookable_offer_in_main_category=False,
        filter_main_category_matches_search_group_name=False,
    )

    assert discovery_artists[0].ranks_by_top_artist == {TOP_1: 4, TOP_2: 2}
    assert discovery_artists[0].avg_rank == 3.0


# ---------------------------------------------------------------------------
# Business logic: compute_candidate_sort_key (unit tests)
# ---------------------------------------------------------------------------


def test_compute_candidate_sort_key_orders_by_appearance_count_desc_then_avg_rank_asc():
    assert compute_candidate_sort_key({TOP_1: 3, TOP_2: 2}) < compute_candidate_sort_key({TOP_1: 1})
    assert compute_candidate_sort_key({TOP_1: 1, TOP_2: 2}) < compute_candidate_sort_key({TOP_1: 2, TOP_2: 3})


def test_compute_candidate_sort_key_breaks_ties_by_top_artist_position():
    top_artist_ids = [TOP_1, TOP_2, TOP_3]

    key_from_top_1 = compute_candidate_sort_key({TOP_1: 1}, top_artist_ids)
    key_from_top_2 = compute_candidate_sort_key({TOP_2: 1}, top_artist_ids)
    key_from_top_3 = compute_candidate_sort_key({TOP_3: 1}, top_artist_ids)

    assert key_from_top_1 < key_from_top_2 < key_from_top_3


def test_compute_candidate_sort_key_tie_breaker_does_not_override_avg_rank():
    top_artist_ids = [TOP_1, TOP_2, TOP_3]

    assert compute_candidate_sort_key({TOP_3: 1}, top_artist_ids) < compute_candidate_sort_key(
        {TOP_1: 2}, top_artist_ids
    )


def test_rank_1_similar_artists_are_ordered_by_top_artist_position():
    """Without overlap, rank-1 candidates are ordered top 1, top 2, top 3, then rank-2 candidates follow."""
    similar_artists_by_top = {
        TOP_1: [
            MatchedArtist(artist_id_match="top-1-rank-1", rank=1),
            MatchedArtist(artist_id_match="top-1-rank-2", rank=2),
        ],
        TOP_2: [MatchedArtist(artist_id_match="top-2-rank-1", rank=1)],
        TOP_3: [MatchedArtist(artist_id_match="top-3-rank-1", rank=1)],
    }

    discovery_artists = _build_discovery_artists_with_defaults(
        top_artist_ids=[TOP_1, TOP_2, TOP_3],
        similar_artists_by_top=similar_artists_by_top,
        filter_has_bookable_offer_in_main_category=False,
        filter_main_category_matches_search_group_name=False,
    )

    assert [artist.artist_id for artist in discovery_artists] == [
        "top-1-rank-1",
        "top-2-rank-1",
        "top-3-rank-1",
        "top-1-rank-2",
    ]
