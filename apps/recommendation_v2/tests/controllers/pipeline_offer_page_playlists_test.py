"""
Unit tests for pipeline_offer_page_playlists controller.

These tests cover:
- build_similar_offer_playlist_configs: the playlist composition rules.
- generate_offer_page_playlists: resolving search_group_name from DB, 404 on missing offer, and parallel sub-pipelines.
"""

from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi import status

from controllers.pipeline_offer_page_playlists import build_similar_offer_playlist_configs
from controllers.pipeline_offer_page_playlists import generate_offer_page_playlists
from schemas.categories import SearchGroupNameEnum
from schemas.offer_page_playlists import AnalyticsPlaylistTypeEnum
from schemas.offer_page_playlists import OfferPagePlaylistsResponse
from schemas.offer_page_playlists import OfferPlaylistTitleEnum
from schemas.playlist_recommendation import RecommendationMetadata
from schemas.similar_offer import SimilarOfferModelChoices


# ---------------------------------------------------------------------------
# build_similar_offer_playlist_configs — playlist composition rules
# ---------------------------------------------------------------------------


class BuildSimilarOfferPlaylistConfigsTest:
    """Verify the playlist composition logic for each offer category."""

    def test_livres_returns_two_same_type_playlists_with_different_models(self):
        configs = build_similar_offer_playlist_configs(SearchGroupNameEnum.LIVRES)

        assert len(configs) == 2
        coreservation, graph = configs

        assert coreservation.analytics_playlist_type == AnalyticsPlaylistTypeEnum.SAME_CATEGORY_TWO_TOWER
        assert coreservation.retrieval_model == SimilarOfferModelChoices.coreservation
        assert coreservation.search_group_names == [SearchGroupNameEnum.LIVRES]
        assert coreservation.title == OfferPlaylistTitleEnum.LES_FANS_AIMENT_AUSSI

        assert graph.analytics_playlist_type == AnalyticsPlaylistTypeEnum.SAME_CATEGORY_GRAPH
        assert graph.retrieval_model == SimilarOfferModelChoices.graph
        assert graph.search_group_names == [SearchGroupNameEnum.LIVRES]
        assert graph.title == OfferPlaylistTitleEnum.DANS_LA_MEME_CATEGORIE

    def test_musique_returns_two_same_type_playlists_with_different_models(self):
        configs = build_similar_offer_playlist_configs(SearchGroupNameEnum.MUSIQUE)

        assert len(configs) == 2
        assert configs[0].retrieval_model == SimilarOfferModelChoices.coreservation
        assert configs[0].analytics_playlist_type == AnalyticsPlaylistTypeEnum.SAME_CATEGORY_TWO_TOWER
        assert configs[1].retrieval_model == SimilarOfferModelChoices.graph
        assert configs[1].analytics_playlist_type == AnalyticsPlaylistTypeEnum.SAME_CATEGORY_GRAPH
        for playlist_config in configs:
            assert playlist_config.search_group_names == [SearchGroupNameEnum.MUSIQUE]

    def test_cinema_returns_same_type_and_cross_type_playlists(self):
        configs = build_similar_offer_playlist_configs(SearchGroupNameEnum.CINEMA)

        assert len(configs) == 2
        same_type, cross_type = configs

        assert same_type.analytics_playlist_type == AnalyticsPlaylistTypeEnum.SAME_CATEGORY_TWO_TOWER
        assert same_type.search_group_names == [SearchGroupNameEnum.CINEMA]
        assert same_type.retrieval_model == SimilarOfferModelChoices.coreservation
        assert same_type.title == OfferPlaylistTitleEnum.LES_FANS_AIMENT_AUSSI

        assert cross_type.analytics_playlist_type == AnalyticsPlaylistTypeEnum.OTHER_CATEGORIES_TWO_TOWER
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

        assert same_type.analytics_playlist_type == AnalyticsPlaylistTypeEnum.SAME_CATEGORY_TWO_TOWER
        assert same_type.search_group_names == [SearchGroupNameEnum.NONE]
        assert same_type.title == OfferPlaylistTitleEnum.LES_FANS_AIMENT_AUSSI

        assert cross_type.analytics_playlist_type == AnalyticsPlaylistTypeEnum.OTHER_CATEGORIES_TWO_TOWER
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

    mock_similar = mocker.patch(
        "controllers.pipeline_offer_page_playlists.generate_similar_offers",
        new_callable=mocker.AsyncMock,
    )
    mock_similar.return_value = mocker.MagicMock(
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
    assert same_type.analytics_playlist_type == AnalyticsPlaylistTypeEnum.SAME_CATEGORY_TWO_TOWER
    assert same_type.results == ["offer-1", "offer-2"]
    assert same_type.params.ab_test == "test-variant"

    cross_type = result.playlists[1]
    assert cross_type.title == OfferPlaylistTitleEnum.CA_PEUT_AUSSI_TE_PLAIRE
    assert cross_type.analytics_playlist_type == AnalyticsPlaylistTypeEnum.OTHER_CATEGORIES_TWO_TOWER
    assert cross_type.params.ab_test == "test-variant"


@pytest.mark.asyncio
async def test_generate_offer_page_playlists_runs_pipelines_in_parallel(mocker):
    """
    Verify that generate_similar_offers is called once per playlist config.
    CINEMA → 2 configs → 2 calls.
    LIVRES → 2 configs → 2 calls.
    """
    dummy_metadata = RecommendationMetadata(
        reco_origin="similar_offer",
        model_origin="default",
        call_id="test-call-id",
    )
    mock_similar = mocker.patch(
        "controllers.pipeline_offer_page_playlists.generate_similar_offers",
        new_callable=mocker.AsyncMock,
    )
    mock_similar.return_value = mocker.MagicMock(results=[], params=dummy_metadata)

    mock_db = AsyncMock()
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.return_value = SearchGroupNameEnum.CINEMA.value
    mock_db.execute.return_value = mock_db_result

    await generate_offer_page_playlists(db=mock_db, offer_id="x")
    assert mock_similar.call_count == 2
    mock_similar.reset_mock()

    mock_db_result.scalar_one_or_none.return_value = SearchGroupNameEnum.LIVRES.value
    await generate_offer_page_playlists(db=mock_db, offer_id="x")
    assert mock_similar.call_count == 2


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
