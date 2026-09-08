"""
Unit tests for pipeline_offer_page_playlists controller.

These tests cover:
- build_similar_offer_playlist_configs: the playlist composition rules.
- generate_offer_page_playlists: the partially-parallel orchestration of sub-pipelines
  (retrieval phase concurrent for all playlists, finalization phase sequential for
  exact cross-playlist deduplication).
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

from controllers.pipeline_offer_page_playlists import _resolve_item_ids_for_offer_ids
from controllers.pipeline_offer_page_playlists import build_similar_offer_playlist_configs
from controllers.pipeline_offer_page_playlists import generate_offer_page_playlists
from schemas.categories import SearchGroupNameEnum
from schemas.offer_page_playlists import OfferPagePlaylistsResponse
from schemas.offer_page_playlists import OfferPlaylistTitleEnum
from schemas.offer_page_playlists import OfferPlaylistTypeEnum
from schemas.playlist_recommendation import RecommendationMetadata
from schemas.similar_offer import SimilarOfferModelChoices

from tests.factories.models import RecommendableOffersFactory


# ---------------------------------------------------------------------------
# build_similar_offer_playlist_configs — playlist composition rules
# ---------------------------------------------------------------------------


class BuildSimilarOfferPlaylistConfigsTest:
    """Verify the playlist composition logic for each offer category."""

    def test_livres_returns_two_same_type_playlists_with_different_models(self):
        configs = build_similar_offer_playlist_configs(SearchGroupNameEnum.LIVRES)

        assert len(configs) == 2  # noqa: PLR2004
        coreservation, graph = configs

        assert coreservation.playlist_type == OfferPlaylistTypeEnum.SAME_TYPE_CORESERVATION
        assert coreservation.retrieval_model == SimilarOfferModelChoices.coreservation
        assert coreservation.search_group_names == [SearchGroupNameEnum.LIVRES]
        assert coreservation.title == OfferPlaylistTitleEnum.LES_FANS_AIMENT_AUSSI

        assert graph.playlist_type == OfferPlaylistTypeEnum.SAME_TYPE_GRAPH
        assert graph.retrieval_model == SimilarOfferModelChoices.graph
        assert graph.search_group_names == [SearchGroupNameEnum.LIVRES]
        assert graph.title == OfferPlaylistTitleEnum.DANS_LA_MEME_CATEGORIE

    def test_musique_returns_two_same_type_playlists_with_different_models(self):
        configs = build_similar_offer_playlist_configs(SearchGroupNameEnum.MUSIQUE)

        assert len(configs) == 2  # noqa: PLR2004
        assert configs[0].retrieval_model == SimilarOfferModelChoices.coreservation
        assert configs[1].retrieval_model == SimilarOfferModelChoices.graph
        for playlist_config in configs:
            assert playlist_config.search_group_names == [SearchGroupNameEnum.MUSIQUE]

    def test_cinema_returns_same_type_and_cross_type_playlists(self):
        configs = build_similar_offer_playlist_configs(SearchGroupNameEnum.CINEMA)

        assert len(configs) == 2  # noqa: PLR2004
        same_type, cross_type = configs

        assert same_type.playlist_type == OfferPlaylistTypeEnum.SAME_TYPE
        assert same_type.search_group_names == [SearchGroupNameEnum.CINEMA]
        assert same_type.retrieval_model == SimilarOfferModelChoices.coreservation
        assert same_type.title == OfferPlaylistTitleEnum.LES_FANS_AIMENT_AUSSI

        assert cross_type.playlist_type == OfferPlaylistTypeEnum.CROSS_TYPE
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

        assert len(configs) == 2  # noqa: PLR2004
        same_type, cross_type = configs

        assert same_type.playlist_type == OfferPlaylistTypeEnum.SAME_TYPE
        assert same_type.search_group_names == [SearchGroupNameEnum.NONE]
        assert same_type.title == OfferPlaylistTitleEnum.LES_FANS_AIMENT_AUSSI

        assert cross_type.playlist_type == OfferPlaylistTypeEnum.CROSS_TYPE
        assert cross_type.title == OfferPlaylistTitleEnum.CA_PEUT_AUSSI_TE_PLAIRE
        # Cross-type must contain all non-NONE categories.
        assert SearchGroupNameEnum.NONE not in cross_type.search_group_names
        assert SearchGroupNameEnum.CINEMA in cross_type.search_group_names
        assert SearchGroupNameEnum.LIVRES in cross_type.search_group_names


# ---------------------------------------------------------------------------
# generate_offer_page_playlists — orchestration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_offer_page_playlists_returns_correct_structure(mocker):
    """
    Verify that the controller returns an OfferPagePlaylistsResponse with one
    OfferPlaylistItem per playlist config, preserving titles and types.
    """

    dummy_metadata = RecommendationMetadata(
        reco_origin="similar_offer",
        model_origin="default",
        call_id="test-call-id",
    )

    mocker.patch(
        "controllers.pipeline_offer_page_playlists.retrieve_similar_offer_candidates",
        new_callable=mocker.AsyncMock,
        return_value=mocker.sentinel.retrieval_result,
    )
    mock_finalize = mocker.patch(
        "controllers.pipeline_offer_page_playlists.finalize_similar_offers",
        new_callable=mocker.AsyncMock,
    )
    mock_finalize.return_value = mocker.MagicMock(
        results=["offer-1", "offer-2"],
        params=dummy_metadata,
    )
    mocker.patch(
        "controllers.pipeline_offer_page_playlists._resolve_item_ids_for_offer_ids",
        new_callable=mocker.AsyncMock,
        return_value=set(),
    )

    result = await generate_offer_page_playlists(
        offer_id="test-offer-id",
        search_group_name=SearchGroupNameEnum.CINEMA,
        user_id=None,
        latitude=48.8566,
        longitude=2.3522,
    )

    assert isinstance(result, OfferPagePlaylistsResponse)
    assert result.offer_id == "test-offer-id"
    assert len(result.playlists) == 2  # CINEMA → same_type + cross_type  # noqa: PLR2004

    same_type = result.playlists[0]
    assert same_type.title == OfferPlaylistTitleEnum.LES_FANS_AIMENT_AUSSI
    assert same_type.playlist_type == OfferPlaylistTypeEnum.SAME_TYPE
    assert same_type.results == ["offer-1", "offer-2"]

    cross_type = result.playlists[1]
    assert cross_type.title == OfferPlaylistTitleEnum.CA_PEUT_AUSSI_TE_PLAIRE
    assert cross_type.playlist_type == OfferPlaylistTypeEnum.CROSS_TYPE


@pytest.mark.asyncio
async def test_generate_offer_page_playlists_runs_retrieval_concurrently(mocker):
    """
    Verify that the retrieval phase is called once per playlist config, and that all
    retrieval calls are scheduled before any of them is awaited (i.e. concurrently),
    while the finalization phase is also called once per playlist config.
    CINEMA → 2 configs → 2 retrieval calls + 2 finalize calls.
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
        return_value=mocker.sentinel.retrieval_result,
    )
    mock_finalize = mocker.patch(
        "controllers.pipeline_offer_page_playlists.finalize_similar_offers",
        new_callable=mocker.AsyncMock,
    )
    mock_finalize.return_value = mocker.MagicMock(results=[], params=dummy_metadata)

    await generate_offer_page_playlists(offer_id="x", search_group_name=SearchGroupNameEnum.CINEMA)
    assert mock_retrieve.call_count == 2  # noqa: PLR2004
    assert mock_finalize.call_count == 2  # noqa: PLR2004
    mock_retrieve.reset_mock()
    mock_finalize.reset_mock()

    await generate_offer_page_playlists(offer_id="x", search_group_name=SearchGroupNameEnum.LIVRES)
    assert mock_retrieve.call_count == 2  # noqa: PLR2004
    assert mock_finalize.call_count == 2  # noqa: PLR2004


@pytest.mark.asyncio
async def test_generate_offer_page_playlists_with_none_search_group_name(mocker):
    """When search_group_name is NONE → same_type(NONE) + cross_type."""

    dummy_metadata = RecommendationMetadata(
        reco_origin="similar_offer",
        model_origin="default",
        call_id="test-call-id",
    )
    mocker.patch(
        "controllers.pipeline_offer_page_playlists.retrieve_similar_offer_candidates",
        new_callable=mocker.AsyncMock,
        return_value=mocker.sentinel.retrieval_result,
    )
    mock_finalize = mocker.patch(
        "controllers.pipeline_offer_page_playlists.finalize_similar_offers",
        new_callable=mocker.AsyncMock,
    )
    mock_finalize.return_value = mocker.MagicMock(results=[], params=dummy_metadata)

    result = await generate_offer_page_playlists(
        offer_id="unknown-offer-id",
        search_group_name=SearchGroupNameEnum.NONE,
    )

    assert len(result.playlists) == 2  # noqa: PLR2004
    assert result.playlists[0].playlist_type == OfferPlaylistTypeEnum.SAME_TYPE
    assert result.playlists[1].playlist_type == OfferPlaylistTypeEnum.CROSS_TYPE
    assert mock_finalize.call_count == 2  # noqa: PLR2004


@pytest.mark.asyncio
async def test_generate_offer_page_playlists_deduplicates_second_playlist_by_item_id(mocker):
    """
    The 1st playlist ("Les fans aiment aussi") must be finalized without any exclusion.
    The 2nd playlist must be finalized with exclude_item_ids containing the item_ids
    resolved from the 1st playlist's results, so no offer linked to those items
    can reappear in the 2nd playlist.
    """

    dummy_metadata = RecommendationMetadata(
        reco_origin="similar_offer",
        model_origin="default",
        call_id="test-call-id",
    )
    mocker.patch(
        "controllers.pipeline_offer_page_playlists.retrieve_similar_offer_candidates",
        new_callable=mocker.AsyncMock,
        return_value=mocker.sentinel.retrieval_result,
    )
    mock_finalize = mocker.patch(
        "controllers.pipeline_offer_page_playlists.finalize_similar_offers",
        new_callable=mocker.AsyncMock,
    )
    mock_finalize.return_value = mocker.MagicMock(results=["offer-1", "offer-2"], params=dummy_metadata)

    mock_resolve_item_ids = mocker.patch(
        "controllers.pipeline_offer_page_playlists._resolve_item_ids_for_offer_ids",
        new_callable=mocker.AsyncMock,
        return_value={"item-A", "item-B"},
    )

    await generate_offer_page_playlists(
        offer_id="test-offer-id",
        search_group_name=SearchGroupNameEnum.CINEMA,
    )

    assert mock_finalize.call_count == 2  # noqa: PLR2004
    first_call_kwargs = mock_finalize.call_args_list[0].kwargs
    second_call_kwargs = mock_finalize.call_args_list[1].kwargs

    # 1st playlist (LES_FANS_AIMENT_AUSSI) must not exclude anything.
    assert first_call_kwargs["exclude_item_ids"] is None

    # 2nd playlist must exclude the item_ids resolved from the 1st playlist's results.
    assert second_call_kwargs["exclude_item_ids"] == {"item-A", "item-B"}

    # item_ids are resolved once per playlist, based on that playlist's own results.
    assert mock_resolve_item_ids.call_count == 2  # noqa: PLR2004
    mock_resolve_item_ids.assert_any_call(["offer-1", "offer-2"])


# ---------------------------------------------------------------------------
# _resolve_item_ids_for_offer_ids — cross-connection visibility regression test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_item_ids_sees_data_committed_through_a_different_session(db_session, engine, mocker):
    """
    Regression test for a subtle test-isolation pitfall (see ``tests/conftest.py::db_session``
    docstring): ``pipeline_offer_page_playlists`` opens its *own* ``AsyncSession`` objects via
    ``AsyncSessionFactory``, each one borrowing a *different physical connection* from the pool
    than ``db_session`` — required for the concurrent retrieval tasks in
    :func:`generate_offer_page_playlists` to run safely in parallel.

    If ``db_session`` ever goes back to the classic "open connection + begin transaction +
    roll back on teardown" recipe, data seeded here via ``RecommendableOffersFactory``
    would stay stuck in an uncommitted transaction only visible to ``db_session``'s own
    connection — silently invisible to the separate connection used below, causing this
    assertion to fail with an empty set instead of a clear error.
    """
    await RecommendableOffersFactory.create_async(offer_id="seeded-offer", item_id="seeded-item")

    # Mirrors exactly what the `client` fixture does: a session factory bound to the
    # test engine, opening its own (different) physical connection from the pool.
    test_async_session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    mocker.patch("controllers.pipeline_offer_page_playlists.AsyncSessionFactory", test_async_session_factory)

    resolved_item_ids = await _resolve_item_ids_for_offer_ids(["seeded-offer"])

    assert resolved_item_ids == {"seeded-item"}
