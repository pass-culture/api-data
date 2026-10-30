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
from controllers.pipeline_offer_page_playlists import deduplicate_and_balance_playlists
from controllers.pipeline_offer_page_playlists import generate_offer_page_playlists
from core.tracking import DeferredTrackingContext
from schemas.categories import SearchGroupNameEnum
from schemas.offer_page_playlists import AnalyticsPlaylistTypeEnum
from schemas.offer_page_playlists import OfferPagePlaylistsResponse
from schemas.offer_page_playlists import OfferPlaylistItem
from schemas.offer_page_playlists import OfferPlaylistTitleEnum
from schemas.playlist_recommendation import RecommendationMetadata
from schemas.similar_offer import SimilarOfferModelChoices

from tests.factories.schemas import EnrichedRecommendableOfferFactory
from tests.factories.schemas import UserContextFactory


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
    mock_similar.side_effect = [
        mocker.MagicMock(results=["offer-1", "offer-2"], params=dummy_metadata),
        mocker.MagicMock(results=["offer-3", "offer-4"], params=dummy_metadata),
    ]

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
    assert cross_type.results == ["offer-3", "offer-4"]
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


# ---------------------------------------------------------------------------
# deduplicate_and_balance_playlists — balancing & rank-based deduplication
# ---------------------------------------------------------------------------


def _make_playlist_item(
    results: list[str],
    title: OfferPlaylistTitleEnum = OfferPlaylistTitleEnum.LES_FANS_AIMENT_AUSSI,
    analytics_type: AnalyticsPlaylistTypeEnum = AnalyticsPlaylistTypeEnum.SAME_CATEGORY_TWO_TOWER,
) -> OfferPlaylistItem:
    return OfferPlaylistItem(
        title=title,
        analytics_playlist_type=analytics_type,
        results=list(results),
        params=RecommendationMetadata(
            reco_origin="similar_offer",
            model_origin="default",
            call_id="call-id",
        ),
    )


class DeduplicateAndBalancePlaylistsTest:
    """Verify cross-playlist deduplication and size balancing rules."""

    def test_example_1_removes_all_duplicates_from_longer_playlist_1(self):
        """
        Playlist 1 has 20 offers, Playlist 2 has 15 offers, 4 duplicates
        → all 4 duplicates are removed from Playlist 1 → final sizes: 16 and 15.
        """
        duplicates = [f"dup-{i}" for i in range(4)]
        p1_offers = [f"p1-{i}" for i in range(16)] + duplicates
        p2_offers = [f"p2-{i}" for i in range(11)] + duplicates

        playlist_1 = _make_playlist_item(p1_offers)
        playlist_2 = _make_playlist_item(
            p2_offers,
            title=OfferPlaylistTitleEnum.DANS_LA_MEME_CATEGORIE,
            analytics_type=AnalyticsPlaylistTypeEnum.SAME_CATEGORY_GRAPH,
        )

        deduplicate_and_balance_playlists([playlist_1, playlist_2])

        assert len(playlist_1.results) == 16
        assert len(playlist_2.results) == 15
        assert set(playlist_1.results).isdisjoint(set(playlist_2.results))

    def test_example_2_equal_playlists_split_even_duplicates_equally(self):
        """
        Playlist 1 has 20 offers, Playlist 2 has 20 offers, 6 duplicates
        → 3 duplicates removed from Playlist 1 and 3 from Playlist 2 → final sizes: 17 and 17.
        """
        duplicates = [f"dup-{i}" for i in range(6)]
        # Place dup-0..2 early in P1 (late in P2) and dup-3..5 late in P1 (early in P2)
        p1_offers = duplicates[:3] + [f"p1-{i}" for i in range(14)] + duplicates[3:]
        p2_offers = duplicates[3:] + [f"p2-{i}" for i in range(14)] + duplicates[:3]

        playlist_1 = _make_playlist_item(p1_offers)
        playlist_2 = _make_playlist_item(p2_offers)

        deduplicate_and_balance_playlists([playlist_1, playlist_2])

        assert len(playlist_1.results) == 17
        assert len(playlist_2.results) == 17
        assert set(playlist_1.results).isdisjoint(set(playlist_2.results))
        # dup-0..2 were better ranked in P1 so they must stay in P1; dup-3..5 stay in P2
        for dup_id in duplicates[:3]:
            assert dup_id in playlist_1.results
            assert dup_id not in playlist_2.results
        for dup_id in duplicates[3:]:
            assert dup_id in playlist_2.results
            assert dup_id not in playlist_1.results

    def test_example_3_unequal_playlists_rebalance_then_split_remaining_duplicates(self):
        """
        Playlist 1 has 20 offers, Playlist 2 has 18 offers, 8 duplicates
        → 2 removed from Playlist 1 first (reaching 18 vs 18), then 3 removed from each
        for the remaining 6 duplicates → final sizes: 15 and 15.
        """
        duplicates = [f"dup-{i}" for i in range(8)]
        p1_offers = [f"p1-{i}" for i in range(12)] + duplicates
        p2_offers = [f"p2-{i}" for i in range(10)] + duplicates

        playlist_1 = _make_playlist_item(p1_offers)
        playlist_2 = _make_playlist_item(p2_offers)

        deduplicate_and_balance_playlists([playlist_1, playlist_2])

        assert len(playlist_1.results) == 15
        assert len(playlist_2.results) == 15
        assert set(playlist_1.results).isdisjoint(set(playlist_2.results))

    def test_removes_from_playlist_2_when_playlist_2_is_longer(self):
        """When Playlist 2 is longer than Playlist 1, duplicates are removed from Playlist 2 first."""
        duplicates = ["dup-1", "dup-2"]
        playlist_1 = _make_playlist_item(["p1-1", *duplicates])  # 3 offers
        playlist_2 = _make_playlist_item(["p2-1", "p2-2", "p2-3", *duplicates])  # 5 offers

        deduplicate_and_balance_playlists([playlist_1, playlist_2])

        assert len(playlist_1.results) == 3
        assert len(playlist_2.results) == 3
        assert playlist_1.results == ["p1-1", "dup-1", "dup-2"]
        assert playlist_2.results == ["p2-1", "p2-2", "p2-3"]

    def test_tie_breaker_removes_from_playlist_where_offer_is_worse_placed(self):
        """
        When playlists have equal sizes and 1 duplicate:
        - If the duplicate is worse placed in Playlist 1 (pos_1 > pos_2), remove from Playlist 1.
        - If the duplicate is worse placed in Playlist 2 (pos_2 > pos_1), remove from Playlist 2.
        """
        # Case A: dup is at index 2 in P1 and index 0 in P2 -> worse placed in P1 -> remove from P1
        p1_a = _make_playlist_item(["p1-1", "p1-2", "dup"])
        p2_a = _make_playlist_item(["dup", "p2-1", "p2-2"])
        deduplicate_and_balance_playlists([p1_a, p2_a])
        assert p1_a.results == ["p1-1", "p1-2"]
        assert p2_a.results == ["dup", "p2-1", "p2-2"]

        # Case B: dup is at index 0 in P1 and index 2 in P2 -> worse placed in P2 -> remove from P2
        p1_b = _make_playlist_item(["dup", "p1-1", "p1-2"])
        p2_b = _make_playlist_item(["p2-1", "p2-2", "dup"])
        deduplicate_and_balance_playlists([p1_b, p2_b])
        assert p1_b.results == ["dup", "p1-1", "p1-2"]
        assert p2_b.results == ["p2-1", "p2-2"]

    def test_tie_breaker_removes_from_playlist_2_when_size_and_position_are_equal(self):
        """
        When playlists have equal sizes and the duplicate is at the exact same position
        in both playlists (pos_1 == pos_2), remove it from Playlist 2.
        """
        playlist_1 = _make_playlist_item(["p1-1", "dup", "p1-2"])
        playlist_2 = _make_playlist_item(["p2-1", "dup", "p2-2"])

        deduplicate_and_balance_playlists([playlist_1, playlist_2])

        assert playlist_1.results == ["p1-1", "dup", "p1-2"]
        assert playlist_2.results == ["p2-1", "p2-2"]

    def test_no_duplicates_leaves_playlists_unchanged(self):
        playlist_1 = _make_playlist_item(["offer-1", "offer-2"])
        playlist_2 = _make_playlist_item(["offer-3", "offer-4"])

        deduplicate_and_balance_playlists([playlist_1, playlist_2])

        assert playlist_1.results == ["offer-1", "offer-2"]
        assert playlist_2.results == ["offer-3", "offer-4"]

    def test_single_playlist_returns_unchanged(self):
        playlist_1 = _make_playlist_item(["offer-1", "offer-2"])
        result = deduplicate_and_balance_playlists([playlist_1])
        assert len(result) == 1
        assert result[0].results == ["offer-1", "offer-2"]


@pytest.mark.asyncio
async def test_generate_offer_page_playlists_logs_only_post_deduplication_offers_to_sink(mocker):
    """
    Verify that log_past_offer_context_to_sink is called AFTER deduplication and only
    logs the offers that remain in each playlist.
    """
    dummy_metadata = RecommendationMetadata(
        reco_origin="similar_offer",
        model_origin="default",
        call_id="test-call-id",
    )
    user_context = UserContextFactory.build()

    # Playlist 1 has 3 offers (including "dup-offer" at index 2),
    # Playlist 2 has 2 offers (including "dup-offer" at index 0).
    # Since Playlist 1 is longer (3 vs 2), "dup-offer" must be removed from Playlist 1.
    p1_enriched = [
        EnrichedRecommendableOfferFactory.build(offer_id="p1-only-1"),
        EnrichedRecommendableOfferFactory.build(offer_id="p1-only-2"),
        EnrichedRecommendableOfferFactory.build(offer_id="dup-offer"),
    ]
    p2_enriched = [
        EnrichedRecommendableOfferFactory.build(offer_id="dup-offer"),
        EnrichedRecommendableOfferFactory.build(offer_id="p2-only-1"),
    ]

    call_idx = 0

    async def fake_generate_similar_offers(**kwargs):
        nonlocal call_idx
        sink = kwargs["deferred_tracking_sink"]
        if call_idx == 0:
            call_idx += 1
            sink.append(
                DeferredTrackingContext(
                    user_context=user_context,
                    final_playlist=p1_enriched,
                    params=None,
                    call_id="call-1",
                    reco_origin="similar_offer",
                    context_name="similar_offer",
                    model_description="coreservation",
                    input_offer_id="ref-offer",
                )
            )
            return mocker.MagicMock(results=[o.offer_id for o in p1_enriched], params=dummy_metadata)

        sink.append(
            DeferredTrackingContext(
                user_context=user_context,
                final_playlist=p2_enriched,
                params=None,
                call_id="call-2",
                reco_origin="graph",
                context_name="similar_offer",
                model_description="graph",
                input_offer_id="ref-offer",
            )
        )
        return mocker.MagicMock(results=[o.offer_id for o in p2_enriched], params=dummy_metadata)

    mocker.patch(
        "controllers.pipeline_offer_page_playlists.generate_similar_offers",
        side_effect=fake_generate_similar_offers,
    )
    mock_sink = mocker.patch("controllers.pipeline_offer_page_playlists.log_past_offer_context_to_sink")

    mock_db = AsyncMock()
    mock_db_result = MagicMock()
    mock_db_result.scalar_one_or_none.return_value = SearchGroupNameEnum.LIVRES.value
    mock_db.execute.return_value = mock_db_result

    response = await generate_offer_page_playlists(db=mock_db, offer_id="ref-offer")

    assert response.playlists[0].results == ["p1-only-1", "p1-only-2"]
    assert response.playlists[1].results == ["dup-offer", "p2-only-1"]

    assert mock_sink.call_count == 2
    logged_p1_ids = [o.offer_id for o in mock_sink.call_args_list[0].kwargs["final_playlist"]]
    logged_p2_ids = [o.offer_id for o in mock_sink.call_args_list[1].kwargs["final_playlist"]]
    assert logged_p1_ids == ["p1-only-1", "p1-only-2"]
    assert logged_p2_ids == ["dup-offer", "p2-only-1"]
