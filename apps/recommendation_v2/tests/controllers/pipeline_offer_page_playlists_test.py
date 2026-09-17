"""
Unit tests for pipeline_offer_page_playlists controller.

These tests cover:
- build_similar_offer_playlist_configs: the playlist composition rules.
- _build_approximate_exclude_item_ids: the approximate cross-playlist dedup logic.
- generate_offer_page_playlists: the fully-parallel orchestration of sub-pipelines
  (both retrieval and finalization phases run concurrently for all playlists, using
  an approximate cross-playlist deduplication).
"""

import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi import status

from controllers.pipeline_offer_page_playlists import _build_approximate_exclude_item_ids
from controllers.pipeline_offer_page_playlists import build_similar_offer_playlist_configs
from controllers.pipeline_offer_page_playlists import generate_offer_page_playlists
from controllers.pipeline_similar_offer import SIMILAR_OFFERS_LIST_MAXIMUM_SIZE
from controllers.pipeline_similar_offer import SimilarOfferRetrievalResult
from schemas.categories import SearchGroupNameEnum
from schemas.offer_page_playlists import AnalyticsPlaylistTypeEnum
from schemas.offer_page_playlists import OfferPagePlaylistsResponse
from schemas.offer_page_playlists import OfferPlaylistTitleEnum
from schemas.playlist_recommendation import RecommendationMetadata
from schemas.similar_offer import SimilarOfferModelChoices
from services.logger import call_id_context


def _make_retrieval_result(item_ids_with_ranks: list[tuple[str, int]]) -> SimilarOfferRetrievalResult:
    """Builds a minimal stand-in for a SimilarOfferRetrievalResult, only exposing the
    ``unbooked_candidate_items`` attribute (with ``item_id``/``item_rank``) actually
    read by :func:`_build_approximate_exclude_item_ids`."""
    return cast(
        "SimilarOfferRetrievalResult",
        cast(
            "object",
            SimpleNamespace(
                unbooked_candidate_items=[
                    SimpleNamespace(item_id=item_id, item_rank=item_rank) for item_id, item_rank in item_ids_with_ranks
                ]
            ),
        ),
    )


# ---------------------------------------------------------------------------
# build_similar_offer_playlist_configs — playlist composition rules
# ---------------------------------------------------------------------------


class BuildSimilarOfferPlaylistConfigsTest:
    """Verify the playlist composition logic for each offer category."""

    def test_livres_returns_two_same_type_playlists_with_different_models(self):
        configs = build_similar_offer_playlist_configs(SearchGroupNameEnum.LIVRES)

        assert len(configs) == 2
        coreservation, graph = configs

        assert coreservation.analytics_playlist_type == AnalyticsPlaylistTypeEnum.SAME_CATEGORY
        assert coreservation.retrieval_model == SimilarOfferModelChoices.coreservation
        assert coreservation.search_group_names == [SearchGroupNameEnum.LIVRES]
        assert coreservation.title == OfferPlaylistTitleEnum.LES_FANS_AIMENT_AUSSI

        assert graph.analytics_playlist_type == AnalyticsPlaylistTypeEnum.BOOKS_SAME_CATEGORY
        assert graph.retrieval_model == SimilarOfferModelChoices.graph
        assert graph.search_group_names == [SearchGroupNameEnum.LIVRES]
        assert graph.title == OfferPlaylistTitleEnum.DANS_LA_MEME_CATEGORIE

    def test_musique_returns_two_same_type_playlists_with_different_models(self):
        configs = build_similar_offer_playlist_configs(SearchGroupNameEnum.MUSIQUE)

        assert len(configs) == 2
        assert configs[0].retrieval_model == SimilarOfferModelChoices.coreservation
        assert configs[0].analytics_playlist_type == AnalyticsPlaylistTypeEnum.SAME_CATEGORY
        assert configs[1].retrieval_model == SimilarOfferModelChoices.graph
        assert configs[1].analytics_playlist_type == AnalyticsPlaylistTypeEnum.SAME_CATEGORY
        for playlist_config in configs:
            assert playlist_config.search_group_names == [SearchGroupNameEnum.MUSIQUE]

    def test_cinema_returns_same_type_and_cross_type_playlists(self):
        configs = build_similar_offer_playlist_configs(SearchGroupNameEnum.CINEMA)

        assert len(configs) == 2
        same_type, cross_type = configs

        assert same_type.analytics_playlist_type == AnalyticsPlaylistTypeEnum.SAME_CATEGORY
        assert same_type.search_group_names == [SearchGroupNameEnum.CINEMA]
        assert same_type.retrieval_model == SimilarOfferModelChoices.coreservation
        assert same_type.title == OfferPlaylistTitleEnum.LES_FANS_AIMENT_AUSSI

        assert cross_type.analytics_playlist_type == AnalyticsPlaylistTypeEnum.OTHER_CATEGORIES
        assert cross_type.title == OfferPlaylistTitleEnum.CA_PEUT_AUSSI_TE_PLAIRE
        assert cross_type.retrieval_model == SimilarOfferModelChoices.coreservation
        # Cross-type must NOT contain the offer's own category or NONE.
        assert SearchGroupNameEnum.CINEMA not in cross_type.search_group_names
        assert SearchGroupNameEnum.NONE not in cross_type.search_group_names
        # Cross-type must contain all other non-NONE categories.
        assert SearchGroupNameEnum.LIVRES in cross_type.search_group_names
        assert SearchGroupNameEnum.SPECTACLES in cross_type.search_group_names

    def test_cross_type_excludes_offer_category_and_none(self):
        """All standard categories should produce a cross-type list free of NONE."""
        standard_categories = [
            search_group
            for search_group in SearchGroupNameEnum
            if search_group not in (SearchGroupNameEnum.NONE, SearchGroupNameEnum.LIVRES, SearchGroupNameEnum.MUSIQUE)
        ]
        for category in standard_categories:
            configs = build_similar_offer_playlist_configs(category)
            _, cross_type = configs
            assert category not in cross_type.search_group_names, f"Own category leaked into cross_type for {category}"
            assert SearchGroupNameEnum.NONE not in cross_type.search_group_names

    def test_none_returns_same_type_and_cross_type_playlists(self):
        """NONE → same_type(NONE) + cross_type(all non-NONE categories)."""
        configs = build_similar_offer_playlist_configs(SearchGroupNameEnum.NONE)

        assert len(configs) == 2
        same_type, cross_type = configs

        assert same_type.analytics_playlist_type == AnalyticsPlaylistTypeEnum.SAME_CATEGORY
        assert same_type.search_group_names == [SearchGroupNameEnum.NONE]
        assert same_type.title == OfferPlaylistTitleEnum.LES_FANS_AIMENT_AUSSI

        assert cross_type.analytics_playlist_type == AnalyticsPlaylistTypeEnum.OTHER_CATEGORIES
        assert cross_type.title == OfferPlaylistTitleEnum.CA_PEUT_AUSSI_TE_PLAIRE
        # Cross-type must contain all non-NONE categories.
        assert SearchGroupNameEnum.NONE not in cross_type.search_group_names
        assert SearchGroupNameEnum.CINEMA in cross_type.search_group_names
        assert SearchGroupNameEnum.LIVRES in cross_type.search_group_names


# ---------------------------------------------------------------------------
# _build_approximate_exclude_item_ids — approximate cross-playlist dedup logic
# ---------------------------------------------------------------------------


class BuildApproximateExcludeItemIdsTest:
    """Verify the approximate exclusion set built from higher-priority playlists' raw candidates."""

    def test_first_playlist_has_no_exclusion(self):
        retrieval_results = [_make_retrieval_result([("item-A", 1)]), _make_retrieval_result([("item-B", 1)])]
        assert _build_approximate_exclude_item_ids(retrieval_results, 0) is None

    def test_excludes_top_candidates_of_higher_priority_playlist_only(self):
        higher_priority = _make_retrieval_result(
            [(f"item-{i}", i) for i in range(SIMILAR_OFFERS_LIST_MAXIMUM_SIZE + 5)]
        )
        lower_priority = _make_retrieval_result([])

        result = _build_approximate_exclude_item_ids([higher_priority, lower_priority], 1)

        # Only the top SIMILAR_OFFERS_LIST_MAXIMUM_SIZE candidates (by item_rank) are kept,
        # even though the higher-priority playlist retrieved more candidates than that.
        assert result == {f"item-{i}" for i in range(SIMILAR_OFFERS_LIST_MAXIMUM_SIZE)}

    def test_sorts_candidates_by_item_rank_before_capping(self):
        # Deliberately out-of-order ranks: only the 2 lowest ranks should be kept.
        higher_priority = _make_retrieval_result([("item-C", 3), ("item-A", 1), ("item-B", 2)])

        result = _build_approximate_exclude_item_ids([higher_priority], 1)

        assert result == {"item-A", "item-B", "item-C"}

    def test_unions_candidates_across_multiple_higher_priority_playlists(self):
        first = _make_retrieval_result([("item-A", 1)])
        second = _make_retrieval_result([("item-B", 1)])
        third = _make_retrieval_result([])

        result = _build_approximate_exclude_item_ids([first, second, third], 2)

        assert result == {"item-A", "item-B"}

    def test_returns_none_when_no_candidates_found(self):
        assert _build_approximate_exclude_item_ids([_make_retrieval_result([])], 1) is None


# ---------------------------------------------------------------------------
# generate_offer_page_playlists — orchestration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_offer_page_playlists_returns_correct_structure(mocker):
    """
    Verify that the controller resolves category from DB and returns an OfferPagePlaylistsResponse
    with one OfferPlaylistItem per playlist config, preserving titles and analytics types.
    """
    dummy_metadata = RecommendationMetadata(
        reco_origin="similar_offer",
        model_origin="default",
        call_id="test-call-id",
        ab_test="test-variant",
    )

    mock_db = AsyncMock()
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.return_value = SearchGroupNameEnum.CINEMA.value
    mock_db.execute.return_value = mock_db_result

    mocker.patch(
        "controllers.pipeline_offer_page_playlists.retrieve_similar_offer_candidates",
        new_callable=mocker.AsyncMock,
        return_value=_make_retrieval_result([]),
    )
    mock_finalize = mocker.patch(
        "controllers.pipeline_offer_page_playlists.finalize_similar_offers",
        new_callable=mocker.AsyncMock,
    )
    mock_finalize.return_value = mocker.MagicMock(
        results=["offer-1", "offer-2"],
        params=dummy_metadata,
    )

    result = await generate_offer_page_playlists(
        db=mock_db,
        offer_id="test-offer-id",
        user_id=None,
        latitude=48.8566,
        longitude=2.3522,
    )

    assert isinstance(result, OfferPagePlaylistsResponse)
    assert result.offer_id == "test-offer-id"
    assert len(result.playlists) == 2  # CINEMA → same_type + cross_type

    same_type = result.playlists[0]
    assert same_type.title == OfferPlaylistTitleEnum.LES_FANS_AIMENT_AUSSI
    assert same_type.analytics_playlist_type == AnalyticsPlaylistTypeEnum.SAME_CATEGORY
    assert same_type.results == ["offer-1", "offer-2"]
    assert same_type.params.ab_test == "test-variant"

    cross_type = result.playlists[1]
    assert cross_type.title == OfferPlaylistTitleEnum.CA_PEUT_AUSSI_TE_PLAIRE
    assert cross_type.analytics_playlist_type == AnalyticsPlaylistTypeEnum.OTHER_CATEGORIES
    assert cross_type.params.ab_test == "test-variant"


@pytest.mark.asyncio
async def test_generate_offer_page_playlists_runs_retrieval_and_finalization_concurrently(mocker):
    """
    Verify that both the retrieval and the finalization phases are called once per
    playlist config. CINEMA → 2 configs → 2 retrieval calls + 2 finalize calls.
    LIVRES → 2 configs → 2 retrieval calls + 2 finalize calls.
    """
    dummy_metadata = RecommendationMetadata(
        reco_origin="similar_offer",
        model_origin="default",
        call_id="test-call-id",
    )
    mock_retrieve = mocker.patch(
        "controllers.pipeline_offer_page_playlists.retrieve_similar_offer_candidates",
        new_callable=mocker.AsyncMock,
        return_value=_make_retrieval_result([]),
    )
    mock_finalize = mocker.patch(
        "controllers.pipeline_offer_page_playlists.finalize_similar_offers",
        new_callable=mocker.AsyncMock,
    )
    mock_finalize.return_value = mocker.MagicMock(results=[], params=dummy_metadata)

    mock_db = AsyncMock()
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.return_value = SearchGroupNameEnum.CINEMA.value
    mock_db.execute.return_value = mock_db_result

    await generate_offer_page_playlists(db=mock_db, offer_id="x")
    assert mock_retrieve.call_count == 2
    assert mock_finalize.call_count == 2
    mock_retrieve.reset_mock()
    mock_finalize.reset_mock()

    mock_db_result.scalar_one_or_none.return_value = SearchGroupNameEnum.LIVRES.value
    await generate_offer_page_playlists(db=mock_db, offer_id="x")
    assert mock_retrieve.call_count == 2
    assert mock_finalize.call_count == 2


@pytest.mark.asyncio
async def test_generate_offer_page_playlists_raises_404_when_offer_not_found(mocker):
    """When the offer is not in offer_metadata_mv, raises HTTPException with 404 status."""
    mock_db = AsyncMock()
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_db_result

    with pytest.raises(HTTPException) as exc_info:
        await generate_offer_page_playlists(db=mock_db, offer_id="non-existent-offer")

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "non-existent-offer" in exc_info.value.detail


@pytest.mark.asyncio
async def test_generate_offer_page_playlists_approximately_deduplicates_second_playlist(mocker):
    """
    The 1st playlist ("Les fans aiment aussi") must be finalized without any exclusion.
    The 2nd playlist must be finalized with an *approximate* exclude_item_ids set, built
    directly from the 1st playlist's raw retrieval candidates (item_id values), since
    finalization now runs concurrently for every playlist instead of waiting for the
    1st playlist's actual final results.
    """
    mock_db = AsyncMock()
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.return_value = SearchGroupNameEnum.CINEMA.value
    mock_db.execute.return_value = mock_db_result

    dummy_metadata = RecommendationMetadata(
        reco_origin="similar_offer",
        model_origin="default",
        call_id="test-call-id",
    )

    first_playlist_retrieval = _make_retrieval_result([("item-A", 1), ("item-B", 2)])
    second_playlist_retrieval = _make_retrieval_result([])

    mocker.patch(
        "controllers.pipeline_offer_page_playlists.retrieve_similar_offer_candidates",
        new_callable=mocker.AsyncMock,
        side_effect=[first_playlist_retrieval, second_playlist_retrieval],
    )
    mock_finalize = mocker.patch(
        "controllers.pipeline_offer_page_playlists.finalize_similar_offers",
        new_callable=mocker.AsyncMock,
    )
    mock_finalize.return_value = mocker.MagicMock(results=["offer-1", "offer-2"], params=dummy_metadata)

    await generate_offer_page_playlists(db=mock_db, offer_id="test-offer-id")

    assert mock_finalize.call_count == 2
    first_call_kwargs = mock_finalize.call_args_list[0].kwargs
    second_call_kwargs = mock_finalize.call_args_list[1].kwargs

    # 1st playlist (LES_FANS_AIMENT_AUSSI) must not exclude anything.
    assert first_call_kwargs["exclude_item_ids"] is None

    # 2nd playlist must exclude the item_ids taken from the 1st playlist's raw candidates.
    assert second_call_kwargs["exclude_item_ids"] == {"item-A", "item-B"}


# ---------------------------------------------------------------------------
# call_id isolation across concurrently generated playlists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_offer_page_playlists_each_playlist_gets_an_isolated_unique_call_id(mocker):
    """
    Regression test for the fully-concurrent orchestration: retrieval and finalization
    now run inside their own ``asyncio.Task`` per playlist (via ``asyncio.create_task``
    + ``asyncio.gather``). Each ``asyncio.Task`` gets its own isolated copy of
    ``contextvars`` (see ``tests/services/logger_test.py`` for the generic guarantee),
    so setting ``call_id_context`` inside one playlist's retrieval/finalization coroutine
    must never leak into another playlist's logs.

    This test simulates ``retrieve_similar_offer_candidates`` / ``finalize_similar_offers``
    with fakes that behave like the real ones w.r.t. call_id: they generate/reuse a
    call_id, call ``call_id_context.set(...)``, yield control to the event loop (so any
    context leak between concurrently running tasks would have a chance to manifest),
    then record what ``call_id_context.get()`` actually returns.
    """
    mock_db = AsyncMock()
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.return_value = SearchGroupNameEnum.CINEMA.value
    mock_db.execute.return_value = mock_db_result

    dummy_metadata = RecommendationMetadata(
        reco_origin="similar_offer",
        model_origin="default",
        call_id="test-call-id",
    )

    call_id_counter = (f"call-{i}" for i in range(1000))
    observed_call_ids_during_retrieval: list[str] = []
    observed_call_ids_during_finalize: list[str] = []

    async def fake_retrieve(*args, **kwargs):
        call_id = next(call_id_counter)
        call_id_context.set(call_id)
        await asyncio.sleep(0)  # yield control: let sibling playlist tasks interleave
        observed_call_ids_during_retrieval.append(call_id_context.get())
        return cast("object", SimpleNamespace(call_id=call_id, unbooked_candidate_items=[]))

    async def fake_finalize(db, retrieval, exclude_item_ids=None):
        call_id_context.set(retrieval.call_id)
        await asyncio.sleep(0)  # yield control: let sibling playlist tasks interleave
        observed_call_ids_during_finalize.append(call_id_context.get())
        return mocker.MagicMock(results=[], params=dummy_metadata)

    mocker.patch(
        "controllers.pipeline_offer_page_playlists.retrieve_similar_offer_candidates",
        side_effect=fake_retrieve,
    )
    mocker.patch(
        "controllers.pipeline_offer_page_playlists.finalize_similar_offers",
        side_effect=fake_finalize,
    )

    await generate_offer_page_playlists(db=mock_db, offer_id="test-offer-id")

    # CINEMA → 2 playlists → 2 retrieval calls + 2 finalize calls.
    assert len(observed_call_ids_during_retrieval) == 2
    assert len(observed_call_ids_during_finalize) == 2

    # Every playlist got its own, unique call_id — no two playlists share one.
    assert len(set(observed_call_ids_during_retrieval)) == 2
    assert len(set(observed_call_ids_during_finalize)) == 2

    # Each playlist's finalize phase observed exactly the call_id its own retrieval
    # phase generated — never a sibling playlist's call_id (no cross-task leakage).
    assert set(observed_call_ids_during_retrieval) == set(observed_call_ids_during_finalize)
