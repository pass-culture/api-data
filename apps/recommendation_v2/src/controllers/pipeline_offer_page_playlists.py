import asyncio

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from controllers.pipeline_similar_offer import SIMILAR_OFFERS_LIST_MAXIMUM_SIZE
from controllers.pipeline_similar_offer import SimilarOfferRetrievalResult
from controllers.pipeline_similar_offer import finalize_similar_offers
from controllers.pipeline_similar_offer import retrieve_similar_offer_candidates
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
        # Legacy analytics mapping (from the old client-side implementation):
        # the "books" tag was only ever used for LIVRES (the legacy component
        # unconditionally forced search_group_names=[LIVRES] and retrieval_model=graph,
        # regardless of the actual offer category — it never covered MUSIQUE).
        # The coreservation playlist always used the generic "same category" tag,
        # for both LIVRES and MUSIQUE, exactly like any other category.
        graph_analytics_playlist_type = (
            AnalyticsPlaylistTypeEnum.BOOKS_SAME_CATEGORY
            if offer_search_group == SearchGroupNameEnum.LIVRES
            else AnalyticsPlaylistTypeEnum.SAME_CATEGORY
        )
        return [
            SimilarOfferPlaylistConfig(
                title=OfferPlaylistTitleEnum.LES_FANS_AIMENT_AUSSI,
                analytics_playlist_type=AnalyticsPlaylistTypeEnum.SAME_CATEGORY,
                retrieval_model=SimilarOfferModelChoices.coreservation,
                search_group_names=[offer_search_group],
            ),
            SimilarOfferPlaylistConfig(
                title=OfferPlaylistTitleEnum.DANS_LA_MEME_CATEGORIE,
                analytics_playlist_type=graph_analytics_playlist_type,
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
            analytics_playlist_type=AnalyticsPlaylistTypeEnum.SAME_CATEGORY,
            retrieval_model=SimilarOfferModelChoices.coreservation,
            search_group_names=[offer_search_group],
        ),
        SimilarOfferPlaylistConfig(
            title=OfferPlaylistTitleEnum.CA_PEUT_AUSSI_TE_PLAIRE,
            analytics_playlist_type=AnalyticsPlaylistTypeEnum.OTHER_CATEGORIES,
            retrieval_model=SimilarOfferModelChoices.coreservation,
            search_group_names=cross_type_search_groups,
        ),
    ]


async def _retrieve_similar_offer_playlist_candidates(
    playlist_config: SimilarOfferPlaylistConfig,
    offer_id: str,
    user_id: str | None,
    latitude: float | None,
    longitude: float | None,
) -> SimilarOfferRetrievalResult:
    """
    Run only the retrieval phase (Vertex AI call + already-booked filter, see
    ``pipeline_similar_offer.retrieve_similar_offer_candidates``) for a single playlist config.

    This phase never depends on other playlists, so it is scheduled concurrently for
    *every* playlist right from the start of :func:`generate_offer_page_playlists`. Its
    output (raw candidate ``item_id`` values) is also used to build the *approximate*
    cross-playlist exclusion set for lower-priority playlists (see
    :func:`_build_approximate_exclude_item_ids`), so the finalization phase of every
    playlist can itself run concurrently too (see :func:`_finalize_similar_offer_playlist`).

    Opens its own dedicated ``AsyncSession`` (see :func:`_finalize_similar_offer_playlist`
    for why sessions must not be shared/reused across concurrent coroutines).

    Args:
        playlist_config: Describes which category and retrieval model to use for this playlist.
        offer_id: The unique identifier of the reference offer.
        user_id: Optional user ID for personalized filtering.
        latitude: The user's current GPS latitude.
        longitude: The user's current GPS longitude.

    Returns:
        A :class:`SimilarOfferRetrievalResult`, ready to be finalized once this playlist's
        turn comes up (see :func:`_finalize_similar_offer_playlist`).
    """
    async with AsyncSessionFactory() as db_session:
        return await retrieve_similar_offer_candidates(
            db=db_session,
            offer_id=offer_id,
            retrieval_model=playlist_config.retrieval_model,
            user_id=user_id,
            categories=None,
            subcategories=None,
            search_group_names=playlist_config.search_group_names,
            latitude=latitude,
            longitude=longitude,
        )


async def _finalize_similar_offer_playlist(
    playlist_config: SimilarOfferPlaylistConfig,
    retrieval: SimilarOfferRetrievalResult,
    exclude_item_ids: set[str] | None,
) -> OfferPlaylistItem:
    """
    Run the finalization phase (cross-playlist dedup + resolution + ranking +
    diversification + fallback + logging, see ``pipeline_similar_offer.finalize_similar_offers``)
    for a single playlist, from an already-fetched :class:`SimilarOfferRetrievalResult`.

    Each call opens its own dedicated ``AsyncSession`` because SQLAlchemy async
    sessions are **not** safe for concurrent use: sharing a single session across
    parallel coroutines (as done in ``asyncio.gather``) would trigger an
    ``IllegalStateChangeError`` as soon as two coroutines attempt a DB operation
    at the same time. This is exactly what happens here: every playlist's finalization
    is launched concurrently via ``asyncio.gather`` in :func:`generate_offer_page_playlists`.

    Args:
        playlist_config: Describes which title and playlist_type to use for the response.
        retrieval: The pre-fetched candidates for this playlist
                   (see :func:`_retrieve_similar_offer_playlist_candidates`).
        exclude_item_ids: Optional *approximate* set of ``item_id`` values already used by a
                          higher-priority playlist on the same page (see
                          :func:`_build_approximate_exclude_item_ids`). Offers linked
                          to these items are excluded from the candidate pool
                          before ranking/diversification/truncation, so results
                          rarely overlap by item_id with a previous playlist.

    Returns:
        The generated :class:`OfferPlaylistItem`, ready to be included in the response.
    """
    async with AsyncSessionFactory() as db_session:
        similar_offers_response = await finalize_similar_offers(
            db=db_session,
            retrieval=retrieval,
            exclude_item_ids=exclude_item_ids,
        )

    return OfferPlaylistItem(
        title=playlist_config.title,
        analytics_playlist_type=playlist_config.analytics_playlist_type,
        results=similar_offers_response.results,
        params=similar_offers_response.params,
    )


def _build_approximate_exclude_item_ids(
    retrieval_results: list[SimilarOfferRetrievalResult],
    playlist_index: int,
) -> set[str] | None:
    """
    Builds an *approximate* cross-playlist exclusion set for the playlist at ``playlist_index``,
    using only data already available right after the (concurrent) retrieval phase of every
    higher-priority playlist — see :func:`_retrieve_similar_offer_playlist_candidates`.

    This trades exactness for parallelism: an *exact* deduplication would require waiting for
    each higher-priority playlist's fully finalized results (resolution + ranking +
    diversification + truncation) before building the exclusion set, forcing playlists to be
    finalized strictly sequentially. Here, every playlist's finalization (resolution, ranking,
    diversification) can instead run concurrently, at the cost of an imperfect exclusion set:

    - For each higher-priority playlist, we take its top ``SIMILAR_OFFERS_LIST_MAXIMUM_SIZE``
      retrieval candidates (sorted by ``item_rank``, the Vertex AI retrieval order) as a proxy
      for what will likely end up in its final list.
    - This is only an approximation: venue resolution (e.g. no venue within range), ranking
      reshuffling, or diversification/truncation can still change which items actually make
      the final cut. As a result, this may exclude a few items from a lower-priority playlist
      that were never actually shown elsewhere, or (more rarely) fail to exclude an item that
      does end up duplicated across two playlists on the same page.

    Args:
        retrieval_results: Retrieval results for every playlist, in priority order, already awaited.
        playlist_index: Index (in ``retrieval_results``) of the playlist to build the set for.

    Returns:
        The approximate set of ``item_id`` values to exclude, or ``None`` for the highest-priority
        playlist (nothing to exclude against) or if no higher-priority playlist produced candidates.
    """
    if playlist_index == 0:
        return None

    exclude_item_ids: set[str] = set()
    for higher_priority_result in retrieval_results[:playlist_index]:
        top_candidates = sorted(
            higher_priority_result.unbooked_candidate_items,
            key=lambda item: item.item_rank,
        )[:SIMILAR_OFFERS_LIST_MAXIMUM_SIZE]
        exclude_item_ids.update(candidate.item_id for candidate in top_candidates)

    return exclude_item_ids or None


async def generate_offer_page_playlists(
    db: AsyncSession,
    offer_id: str,
    user_id: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> OfferPagePlaylistsResponse:
    """
    Build all recommendation playlists for an offer detail page.

    Each playlist is produced by dedicated ``AsyncSession``-scoped calls into the
    ``pipeline_similar_offer`` module. SQLAlchemy async sessions are not safe for
    concurrent use, so sharing a single session across parallel coroutines (via
    ``asyncio.gather``) would trigger an ``IllegalStateChangeError``. Creating one
    session per task avoids this.

    Both pipeline phases are launched **concurrently for every playlist**:

    1. The (network-bound) **retrieval** phase (Vertex AI call + already-booked filter,
       see :func:`_retrieve_similar_offer_playlist_candidates`) never depends on other
       playlists, so it is launched right away for all playlists via ``asyncio.gather``.
    2. The (DB-bound) **finalization** phase (resolution + ranking + diversification,
       see :func:`_finalize_similar_offer_playlist`) is also launched concurrently for
       all playlists, once every retrieval has completed.

    Cross-playlist deduplication is therefore **approximate** rather than exact: since no
    playlist waits for another's *final* results anymore, the exclusion set passed to a
    given playlist is built from the raw retrieval candidates of higher-priority playlists
    (see :func:`_build_approximate_exclude_item_ids`) instead of their truly final,
    post-diversification results. This trades a small risk of imperfect deduplication
    (a rare duplicated item across two playlists, or a candidate excluded even though it
    would not actually have appeared elsewhere) for full parallelization of the slowest
    part of the pipeline across all playlists (order defined by
    :func:`build_similar_offer_playlist_configs`, the "Les fans aiment aussi"
    coreservation playlist still being treated as the highest priority one).

    This deduplication is applied before ranking/diversification/truncation in the
    underlying pipeline, but there is no guarantee on the resulting size of a
    deduplicated playlist: if too few alternative candidates remain, it may end up with
    fewer than the usual maximum number of results — this is an accepted trade-off.

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

    # Launch the retrieval phase of every playlist concurrently, right away — it never
    # depends on other playlists, so there is no reason to wait for anything here.
    retrieval_tasks = [
        asyncio.create_task(
            _retrieve_similar_offer_playlist_candidates(
                playlist_config=playlist_config,
                offer_id=offer_id,
                user_id=user_id,
                latitude=latitude,
                longitude=longitude,
            )
        )
        for playlist_config in similar_offer_playlist_configs
    ]
    retrieval_results = list(await asyncio.gather(*retrieval_tasks))

    # Launch the finalization phase of every playlist concurrently too. Each playlist's
    # exclusion set is built from the raw retrieval candidates of higher-priority playlists
    # (approximate deduplication, see _build_approximate_exclude_item_ids), so no playlist
    # needs to wait for another one's *final* results before starting.
    finalize_tasks = [
        asyncio.create_task(
            _finalize_similar_offer_playlist(
                playlist_config=playlist_config,
                retrieval=retrieval_result,
                exclude_item_ids=_build_approximate_exclude_item_ids(retrieval_results, playlist_index),
            )
        )
        for playlist_index, (playlist_config, retrieval_result) in enumerate(
            zip(similar_offer_playlist_configs, retrieval_results, strict=True)
        )
    ]
    playlist_items = list(await asyncio.gather(*finalize_tasks))

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
        playlists=list(playlist_items),
    )
