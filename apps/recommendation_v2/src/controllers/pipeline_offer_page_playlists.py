import asyncio
from collections import deque

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from controllers.pipeline_similar_offer import generate_similar_offers
from core.tracking import DeferredTrackingContext
from core.tracking import log_past_offer_context_to_sink
from models.offer import OfferMetadata
from schemas.categories import SearchGroupNameEnum
from schemas.offer_page_playlists import AnalyticsPlaylistTypeEnum
from schemas.offer_page_playlists import OfferPagePlaylistsResponse
from schemas.offer_page_playlists import OfferPlaylistItem
from schemas.offer_page_playlists import OfferPlaylistTitleEnum
from schemas.offer_page_playlists import SimilarOfferPlaylistConfig
from schemas.similar_offer import SimilarOfferModelChoices
from services.db import AsyncSessionFactory
from services.logger import logger


# Minimum number of remaining duplicates needed to remove one from each playlist at once.
MIN_DUPLICATES_FOR_PAIR_REMOVAL = 2

# Search groups that use dual same-type playlists (coreservation + graph).
SEARCH_GROUPS_WITH_DUAL_SAME_TYPE_PLAYLISTS: frozenset[SearchGroupNameEnum] = frozenset(
    {SearchGroupNameEnum.LIVRES, SearchGroupNameEnum.MUSIQUE}
)

# All usable search groups (excludes NONE which is not a real category).
ALL_SEARCH_GROUPS: list[SearchGroupNameEnum] = [
    search_group for search_group in SearchGroupNameEnum if search_group != SearchGroupNameEnum.NONE
]


def build_similar_offer_playlist_configs(offer_search_group: SearchGroupNameEnum) -> list[SimilarOfferPlaylistConfig]:
    """
    Return the ordered list of "similar offer" playlists to generate for a given offer category.

    The number and nature of playlists depend on the ``search_group_name`` of the reference offer.

    Composition rules
    ------------------
    - **LIVRES / MUSIQUE**: two playlists targeting the *same* category, but using
      two different retrieval models:
        1. "Les fans aiment aussi"  -> same type, coreservation model
        2. "Dans la meme categorie" -> same type, graph model
    - **Any other known category**: one same-type playlist and one cross-type
      playlist (all categories except the offer's own):
        1. "Les fans aiment aussi"   -> same type, coreservation model
        2. "Ca peut aussi te plaire" -> all other types, coreservation model
    - **NONE / search_group_name not supplied**: same pattern as any standard category,
      using ``SearchGroupNameEnum.NONE`` as the "same type" category.

    .. warning::
        This function is the single source of truth for the playlist composition
        rules, also summarized in ``docs/offer_page_playlists.md``. If you change
        this function (add/remove a category rule, change a title, a retrieval
        model, etc.), update that documentation file in the same change.

    Args:
        offer_search_group: The ``search_group_name`` of the reference offer.
                            Use ``SearchGroupNameEnum.NONE`` when the offer is
                            not found in the database or has no search group.

    Returns:
        An ordered list of :class:`SimilarOfferPlaylistConfig` instances, each describing
        one playlist to generate via ``generate_similar_offers``.
    """
    if offer_search_group in SEARCH_GROUPS_WITH_DUAL_SAME_TYPE_PLAYLISTS:
        # Books & Music: two same-type playlists with different retrieval models.
        # Each is tagged with the analytics type matching its retrieval model,
        # for both LIVRES and MUSIQUE.
        return [
            SimilarOfferPlaylistConfig(
                title=OfferPlaylistTitleEnum.LES_FANS_AIMENT_AUSSI,
                analytics_playlist_type=AnalyticsPlaylistTypeEnum.SAME_CATEGORY_TWO_TOWER,
                retrieval_model=SimilarOfferModelChoices.coreservation,
                search_group_names=[offer_search_group],
            ),
            SimilarOfferPlaylistConfig(
                title=OfferPlaylistTitleEnum.DANS_LA_MEME_CATEGORIE,
                analytics_playlist_type=AnalyticsPlaylistTypeEnum.SAME_CATEGORY_GRAPH,
                retrieval_model=SimilarOfferModelChoices.graph,
                search_group_names=[offer_search_group],
            ),
        ]

    # Standard case (including NONE): same-type + cross-type playlists.
    # When offer_search_group is NONE, cross_type_search_groups = ALL_SEARCH_GROUPS (all non-NONE categories).
    cross_type_search_groups = [
        search_group for search_group in ALL_SEARCH_GROUPS if search_group != offer_search_group
    ]
    return [
        SimilarOfferPlaylistConfig(
            title=OfferPlaylistTitleEnum.LES_FANS_AIMENT_AUSSI,
            analytics_playlist_type=AnalyticsPlaylistTypeEnum.SAME_CATEGORY_TWO_TOWER,
            retrieval_model=SimilarOfferModelChoices.coreservation,
            search_group_names=[offer_search_group],
        ),
        SimilarOfferPlaylistConfig(
            title=OfferPlaylistTitleEnum.CA_PEUT_AUSSI_TE_PLAIRE,
            analytics_playlist_type=AnalyticsPlaylistTypeEnum.OTHER_CATEGORIES_TWO_TOWER,
            retrieval_model=SimilarOfferModelChoices.coreservation,
            search_group_names=cross_type_search_groups,
        ),
    ]


def _select_duplicates_to_remove(
    sorted_duplicates: list[str],
    pos_1: dict[str, int],
    pos_2: dict[str, int],
    results_1: list[str],
    results_2: list[str],
) -> tuple[set[str], set[str]]:
    """
    Decide from which playlist each duplicate offer must be removed so that both end up with the same size.

    Each duplicate offer (present in both playlists) is assigned to exactly one playlist for removal,
    so it only remains in the other one. Removals are chosen to lose as little ranking as possible.

    ``sorted_duplicates`` must be sorted by ``(pos_1 - pos_2, pos_1)`` descending: its start holds the
    offers worst-ranked in playlist 1 (removed from playlist 1 first), its end holds the offers
    worst-ranked in playlist 2 (removed from playlist 2 first). The duplicates are consumed from both
    ends of a ``deque`` (``popleft`` for playlist 1, ``pop`` for playlist 2), in three phases:

    1. Size balancing: while the playlists differ in size and duplicates remain, remove a duplicate
       from the longer playlist.
    2. Equal split: once sizes are equal, remove duplicates by pairs, one from each playlist,
       so sizes stay equal.
    3. Odd tie-break: if a single duplicate remains, remove it from the playlist where its position
       is larger (worse-ranked); on an exact tie (``pos_1 == pos_2``), remove it from playlist 2.

    Args:
        sorted_duplicates: Offer ids present in both playlists, sorted as described above.
        pos_1: Position (index) of each offer in playlist 1.
        pos_2: Position (index) of each offer in playlist 2.
        results_1: Offer ids of playlist 1 (only its size is used).
        results_2: Offer ids of playlist 2 (only its size is used).

    Returns:
        A tuple ``(remove_from_1, remove_from_2)`` of offer id sets to remove from playlist 1 and 2.
    """
    remove_from_1: set[str] = set()
    remove_from_2: set[str] = set()

    # Duplicates still to assign. Front = worst-ranked in playlist 1, back = worst-ranked in playlist 2.
    remaining_duplicates = deque(sorted_duplicates)
    size_1 = len(results_1)
    size_2 = len(results_2)

    # Phase 1: while one playlist is longer than the other, remove duplicates from the longer one.
    while remaining_duplicates and size_1 != size_2:
        if size_1 > size_2:
            offer_to_remove = remaining_duplicates.popleft()
            remove_from_1.add(offer_to_remove)
            size_1 -= 1
            removed_from = "playlist_1"
        else:
            offer_to_remove = remaining_duplicates.pop()
            remove_from_2.add(offer_to_remove)
            size_2 -= 1
            removed_from = "playlist_2"
        logger.debug(
            "⚖️ [Phase 1 - Size balancing] Removed duplicate from the longer playlist.",
            extra={
                "offer_id": offer_to_remove,
                "removed_from": removed_from,
                "pos_1": pos_1[offer_to_remove],
                "pos_2": pos_2[offer_to_remove],
                "new_size_1": size_1,
                "new_size_2": size_2,
            },
        )

    # Phase 2: sizes are equal, so remove duplicates by pairs (one per playlist) to keep them equal.
    while len(remaining_duplicates) >= MIN_DUPLICATES_FOR_PAIR_REMOVAL:
        offer_removed_1 = remaining_duplicates.popleft()
        remove_from_1.add(offer_removed_1)
        size_1 -= 1

        offer_removed_2 = remaining_duplicates.pop()
        remove_from_2.add(offer_removed_2)
        size_2 -= 1

        logger.debug(
            "⚖️ [Phase 2 - Equal split] Removed 1 duplicate from each playlist to keep sizes balanced.",
            extra={
                "removed_from_playlist_1": {
                    "offer_id": offer_removed_1,
                    "pos_1": pos_1[offer_removed_1],
                    "pos_2": pos_2[offer_removed_1],
                },
                "removed_from_playlist_2": {
                    "offer_id": offer_removed_2,
                    "pos_1": pos_1[offer_removed_2],
                    "pos_2": pos_2[offer_removed_2],
                },
                "new_size_1": size_1,
                "new_size_2": size_2,
            },
        )

    # Phase 3: at most one duplicate is left. Remove it from the playlist where it is worse-ranked
    # (larger position); on an exact tie, remove it from playlist 2.
    if remaining_duplicates:
        last_duplicate = remaining_duplicates.pop()
        if pos_1[last_duplicate] > pos_2[last_duplicate]:
            remove_from_1.add(last_duplicate)
            size_1 -= 1
            removed_target = "playlist_1"
            reason = "worse_position_in_playlist_1"
        else:
            remove_from_2.add(last_duplicate)
            size_2 -= 1
            removed_target = "playlist_2"
            reason = (
                "worse_position_in_playlist_2"
                if pos_2[last_duplicate] > pos_1[last_duplicate]
                else "equal_position_tie_breaker_playlist_2"
            )
        logger.debug(
            "⚖️ [Phase 3 - Odd tie-breaker] Resolved last remaining duplicate at equal playlist size.",
            extra={
                "offer_id": last_duplicate,
                "pos_1": pos_1[last_duplicate],
                "pos_2": pos_2[last_duplicate],
                "removed_from": removed_target,
                "reason": reason,
                "new_size_1": size_1,
                "new_size_2": size_2,
            },
        )

    return remove_from_1, remove_from_2


def deduplicate_and_balance_playlists(playlists: list[OfferPlaylistItem]) -> list[OfferPlaylistItem]:
    """
    Remove duplicate offers shared between the two offer-page playlists while balancing their lengths.

    Steps
    -----
    1. Compute the position of each offer in ``playlist_1`` (``pos_1``) and ``playlist_2`` (``pos_2``).
    2. Identify all ``offer_id`` values present in both playlists. If there are none, return unchanged.
    3. Sort these duplicates by ``(pos_1 - pos_2, pos_1)`` descending:
       - the start of the list holds offers ranked worse in ``playlist_1`` than in ``playlist_2``
         (best candidates to remove from ``playlist_1``);
       - the end of the list holds offers ranked worse in ``playlist_2`` than in ``playlist_1``
         (best candidates to remove from ``playlist_2``).
    4. Delegate to :func:`_select_duplicates_to_remove` to decide, for each duplicate, from which
       playlist it is removed (size balancing first, then even split, then tie-break).
    5. Rebuild ``results`` of both playlists without the removed offers (relative order preserved).

    Playlists with fewer than two entries are returned untouched.

    Args:
        playlists: The list of generated :class:`OfferPlaylistItem` objects (expected length 2).

    Returns:
        The same list of :class:`OfferPlaylistItem` objects with ``results`` deduplicated in place.
    """
    if len(playlists) < 2:  # noqa: PLR2004
        return playlists

    playlist_1, playlist_2 = playlists[0], playlists[1]
    results_1 = playlist_1.results
    results_2 = playlist_2.results

    pos_1 = {offer_id: index for index, offer_id in enumerate(results_1)}
    pos_2 = {offer_id: index for index, offer_id in enumerate(results_2)}
    duplicates = [offer_id for offer_id in results_1 if offer_id in pos_2]
    if not duplicates:
        logger.debug(
            "⚖️ Deduplication skipped: no duplicate offers found between playlists.",
            extra={
                "playlist_1_size": len(results_1),
                "playlist_2_size": len(results_2),
            },
        )
        return playlists

    # Sort descending by (pos_1 - pos_2, pos_1):
    # - left side: worst-placed in playlist_1 relative to playlist_2 -> remove from playlist_1
    # - right side: worst-placed in playlist_2 relative to playlist_1 -> remove from playlist_2
    sorted_duplicates = sorted(
        duplicates,
        key=lambda offer_id: (pos_1[offer_id] - pos_2[offer_id], pos_1[offer_id]),
        reverse=True,
    )

    logger.debug(
        "🔍 Starting offer_page_playlists deduplication.",
        extra={
            "playlist_1_initial_size": len(results_1),
            "playlist_2_initial_size": len(results_2),
            "duplicates_count": len(sorted_duplicates),
            "sorted_duplicates": [
                {
                    "offer_id": offer_id,
                    "pos_1": pos_1[offer_id],
                    "pos_2": pos_2[offer_id],
                    "pos_delta": pos_1[offer_id] - pos_2[offer_id],
                }
                for offer_id in sorted_duplicates
            ],
        },
    )

    remove_from_1, remove_from_2 = _select_duplicates_to_remove(sorted_duplicates, pos_1, pos_2, results_1, results_2)

    playlist_1.results = [offer_id for offer_id in results_1 if offer_id not in remove_from_1]
    playlist_2.results = [offer_id for offer_id in results_2 if offer_id not in remove_from_2]

    logger.info(
        "⚖️ Deduplicated and balanced offer_page_playlists.",
        extra={
            "playlist_1_initial_size": len(results_1),
            "playlist_2_initial_size": len(results_2),
            "duplicates_found": len(duplicates),
            "removed_from_playlist_1_count": len(remove_from_1),
            "removed_from_playlist_2_count": len(remove_from_2),
            "removed_from_playlist_1": sorted(remove_from_1),
            "removed_from_playlist_2": sorted(remove_from_2),
            "playlist_1_final_size": len(playlist_1.results),
            "playlist_2_final_size": len(playlist_2.results),
        },
    )

    return playlists


async def _generate_single_similar_offer_playlist(
    playlist_config: SimilarOfferPlaylistConfig,
    offer_id: str,
    user_id: str | None,
    latitude: float | None,
    longitude: float | None,
) -> tuple[OfferPlaylistItem, list[DeferredTrackingContext]]:
    """
    Run the ``generate_similar_offers`` pipeline for a single playlist config
    with deferred BigQuery tracking so that only post-deduplication offers are logged.

    Each call opens its own dedicated ``AsyncSession`` because SQLAlchemy async
    sessions are **not** safe for concurrent use: sharing a single session across
    parallel coroutines (as done in ``asyncio.gather``) would trigger an
    ``IllegalStateChangeError`` as soon as two coroutines attempt a DB operation
    at the same time.

    Args:
        playlist_config: Describes which category, retrieval model and title
                          to use for this playlist.
        offer_id: The unique identifier of the reference offer.
        user_id: Optional user ID for personalized filtering.
        latitude: The user's current GPS latitude.
        longitude: The user's current GPS longitude.

    Returns:
        A tuple of the generated :class:`OfferPlaylistItem` and the list of
        :class:`DeferredTrackingContext` entries to flush after deduplication.
    """
    deferred_tracking_sink: list[DeferredTrackingContext] = []

    async with AsyncSessionFactory() as playlist_db_session:
        similar_offers_response = await generate_similar_offers(
            db=playlist_db_session,
            offer_id=offer_id,
            retrieval_model=playlist_config.retrieval_model,
            user_id=user_id,
            search_group_names=playlist_config.search_group_names,
            latitude=latitude,
            longitude=longitude,
            deferred_tracking_sink=deferred_tracking_sink,
        )

    playlist_item = OfferPlaylistItem(
        title=playlist_config.title,
        analytics_playlist_type=playlist_config.analytics_playlist_type,
        results=similar_offers_response.results,
        params=similar_offers_response.params,
    )
    return playlist_item, deferred_tracking_sink


def _flush_deferred_tracking_for_playlists(
    playlists: list[OfferPlaylistItem],
    deferred_tracking_per_playlist: list[list[DeferredTrackingContext]],
) -> None:
    """
    Flush deferred BigQuery tracking logs for each playlist, keeping only offers
    that survived cross-playlist deduplication (and preserving their final order).
    """
    for playlist_item, tracking_contexts in zip(playlists, deferred_tracking_per_playlist, strict=True):
        kept_offer_ids = set(playlist_item.results)
        for tracking_context in tracking_contexts:
            displayed_offers = [offer for offer in tracking_context.final_playlist if offer.offer_id in kept_offer_ids]
            log_past_offer_context_to_sink(
                user_context=tracking_context.user_context,
                final_playlist=displayed_offers,
                params=tracking_context.params,
                call_id=tracking_context.call_id,
                reco_origin=tracking_context.reco_origin,
                context_name=tracking_context.context_name,
                model_description=tracking_context.model_description,
                input_offer_id=tracking_context.input_offer_id,
            )


async def generate_offer_page_playlists(
    db: AsyncSession,
    offer_id: str,
    user_id: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> OfferPagePlaylistsResponse:
    """
    Build all recommendation playlists for an offer detail page in parallel,
    then deduplicate and balance their sizes before logging displayed offers to BigQuery.

    Each playlist is produced by a dedicated ``generate_similar_offers`` call,
    each running with its **own** ``AsyncSession``.  SQLAlchemy async sessions
    are not safe for concurrent use, so sharing a single session across
    parallel coroutines (via ``asyncio.gather``) would trigger an
    ``IllegalStateChangeError``.  Creating one session per task avoids this.

    All calls are executed concurrently via ``asyncio.gather``, so the total
    latency is roughly equal to the slowest individual pipeline rather than
    the sum of all pipelines.

    Args:
        db: The async database session used to fetch offer metadata.
        offer_id: The unique identifier of the reference offer.
        user_id: Optional user ID for personalized filtering
                 (e.g., excluding already-booked items).
        latitude: The user's current GPS latitude.
        longitude: The user's current GPS longitude.

    Returns:
        :class:`OfferPagePlaylistsResponse` containing all generated playlists
        in the order defined by :func:`build_similar_offer_playlist_configs`.

    Raises:
        HTTPException: HTTP 404 if the offer is not found in ``offer_metadata_mv``.
    """
    offer_metadata_record = await db.execute(
        select(OfferMetadata.search_group_name).where(OfferMetadata.offer_id == offer_id).limit(1)
    )
    search_group_name_str = offer_metadata_record.scalar_one_or_none()

    if search_group_name_str is None:
        logger.warning(
            "Offer not found in offer metadata table.",
            extra={"offer_id": offer_id},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Offer '{offer_id}' not found.",
        )

    search_group_name = SearchGroupNameEnum(search_group_name_str)

    similar_offer_playlist_configs = build_similar_offer_playlist_configs(search_group_name)

    logger.info(
        "🎬 Starting offer_page_playlists pipeline.",
        extra={
            "offer_id": offer_id,
            "offer_search_group": search_group_name,
            "playlist_count": len(similar_offer_playlist_configs),
            "playlist_types": [
                playlist_config.analytics_playlist_type for playlist_config in similar_offer_playlist_configs
            ],
        },
    )

    generated_results = await asyncio.gather(
        *[
            _generate_single_similar_offer_playlist(
                playlist_config=playlist_config,
                offer_id=offer_id,
                user_id=user_id,
                latitude=latitude,
                longitude=longitude,
            )
            for playlist_config in similar_offer_playlist_configs
        ]
    )

    playlist_items = [item for item, _ in generated_results]
    deferred_tracking_per_playlist = [tracking_contexts for _, tracking_contexts in generated_results]

    deduplicate_and_balance_playlists(playlist_items)
    _flush_deferred_tracking_for_playlists(playlist_items, deferred_tracking_per_playlist)

    logger.info(
        "✅ offer_page_playlists pipeline completed.",
        extra={
            "offer_id": offer_id,
            "playlists": [
                {"title": playlist.title, "type": playlist.analytics_playlist_type, "count": len(playlist.results)}
                for playlist in playlist_items
            ],
        },
    )

    return OfferPagePlaylistsResponse(
        offer_id=offer_id,
        playlists=playlist_items,
    )
