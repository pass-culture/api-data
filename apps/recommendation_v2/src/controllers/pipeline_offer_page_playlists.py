from sqlalchemy import select

from controllers.pipeline_similar_offer import generate_similar_offers
from models.offer import RecommendableOffers
from schemas.categories import SearchGroupNameEnum
from schemas.offer_page_playlists import OfferPagePlaylistsResponse
from schemas.offer_page_playlists import OfferPlaylistItem
from schemas.offer_page_playlists import OfferPlaylistTitleEnum
from schemas.offer_page_playlists import OfferPlaylistTypeEnum
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
        return [
            SimilarOfferPlaylistConfig(
                title=OfferPlaylistTitleEnum.LES_FANS_AIMENT_AUSSI,
                playlist_type=OfferPlaylistTypeEnum.SAME_TYPE_CORESERVATION,
                retrieval_model=SimilarOfferModelChoices.coreservation,
                search_group_names=[offer_search_group],
            ),
            SimilarOfferPlaylistConfig(
                title=OfferPlaylistTitleEnum.DANS_LA_MEME_CATEGORIE,
                playlist_type=OfferPlaylistTypeEnum.SAME_TYPE_GRAPH,
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
            playlist_type=OfferPlaylistTypeEnum.SAME_TYPE,
            retrieval_model=SimilarOfferModelChoices.coreservation,
            search_group_names=[offer_search_group],
        ),
        SimilarOfferPlaylistConfig(
            title=OfferPlaylistTitleEnum.CA_PEUT_AUSSI_TE_PLAIRE,
            playlist_type=OfferPlaylistTypeEnum.CROSS_TYPE,
            retrieval_model=SimilarOfferModelChoices.coreservation,
            search_group_names=cross_type_search_groups,
        ),
    ]


async def _generate_single_similar_offer_playlist(
    playlist_config: SimilarOfferPlaylistConfig,
    offer_id: str,
    user_id: str | None,
    latitude: float | None,
    longitude: float | None,
    exclude_item_ids: set[str] | None = None,
) -> OfferPlaylistItem:
    """
    Run the ``generate_similar_offers`` pipeline for a single playlist config.

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
        exclude_item_ids: Optional set of ``item_id`` values already used by a
                          higher-priority playlist on the same page. Offers linked
                          to these items are excluded from the candidate pool
                          before ranking/diversification/truncation, so results
                          never overlap by item_id with a previous playlist.

    Returns:
        The generated :class:`OfferPlaylistItem`, ready to be included in the response.
    """
    async with AsyncSessionFactory() as playlist_db_session:
        similar_offers_response = await generate_similar_offers(
            db=playlist_db_session,
            offer_id=offer_id,
            retrieval_model=playlist_config.retrieval_model,
            user_id=user_id,
            search_group_names=playlist_config.search_group_names,
            latitude=latitude,
            longitude=longitude,
            exclude_item_ids=exclude_item_ids,
        )

    return OfferPlaylistItem(
        title=playlist_config.title,
        playlist_type=playlist_config.playlist_type,
        results=similar_offers_response.results,
        params=similar_offers_response.params,
    )


async def _resolve_item_ids_for_offer_ids(offer_ids: list[str]) -> set[str]:
    """
    Batch-resolves the ``item_id`` values linked to a list of ``offer_id``.

    Used to know which items were already shown by a higher-priority playlist,
    so the next playlist can exclude them from its own candidate pool. Opens its
    own dedicated ``AsyncSession`` (see :func:`_generate_single_similar_offer_playlist`
    for why sessions must not be shared/reused across sequential DB operations
    from different pipeline stages).

    Args:
        offer_ids: The offer IDs returned by a previously generated playlist.

    Returns:
        The set of distinct ``item_id`` values linked to those offers. Offers not
        found in ``recommendable_offers_raw_mv`` (e.g. non-recommendable offers)
        are silently skipped — they simply cannot be cross-referenced.
    """
    if not offer_ids:
        return set()

    async with AsyncSessionFactory() as db_session:
        query_result = await db_session.execute(
            select(RecommendableOffers.item_id).where(RecommendableOffers.offer_id.in_(offer_ids))
        )
        return set(query_result.scalars().all())


async def generate_offer_page_playlists(
    offer_id: str,
    search_group_name: SearchGroupNameEnum,
    user_id: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> OfferPagePlaylistsResponse:
    """
    Build all recommendation playlists for an offer detail page.

    The ``search_group_name`` of the reference offer must be supplied by the
    caller (e.g. the client, which already knows the category of the offer
    it is displaying). It is **not** resolved from the database:
    the ``recommendable_offers_raw_mv`` table only contains ~32M
    "recommendable" offers, so many valid ``offer_id`` values (non-recommendable
    or freshly created offers) would otherwise have no known category.

    Each playlist is produced by a dedicated ``generate_similar_offers`` call,
    each running with its **own** ``AsyncSession``.  SQLAlchemy async sessions
    are not safe for concurrent use, so sharing a single session across
    parallel coroutines (via ``asyncio.gather``) would trigger an
    ``IllegalStateChangeError``.  Creating one session per task avoids this.

    Playlists are generated **sequentially**, in the order defined by
    :func:`build_similar_offer_playlist_configs` (the "Les fans aiment aussi"
    two-tower/coreservation playlist always runs first). After each playlist is
    generated, the ``item_id`` values of its results are resolved and excluded
    from the candidate pool of the next playlist, so no offer linked to an
    already-shown item reappears in a lower-priority playlist. This deduplication
    is applied before ranking/diversification/truncation in the underlying
    pipeline, but there is no guarantee on the resulting size of a deduplicated
    playlist: if too few alternative candidates remain, it may end up with fewer
    than the usual maximum number of results — this is an accepted trade-off.

    Args:
        offer_id: The unique identifier of the reference offer.
        search_group_name: The ``search_group_name`` of the reference offer,
                            supplied by the caller.
        user_id: Optional user ID for personalized filtering
                 (e.g., excluding already-booked items).
        latitude: The user's current GPS latitude.
        longitude: The user's current GPS longitude.

    Returns:
        :class:`OfferPagePlaylistsResponse` containing all generated playlists
        in the order defined by :func:`build_similar_offer_playlist_configs`.
    """
    similar_offer_playlist_configs = build_similar_offer_playlist_configs(search_group_name)

    logger.info(
        "🎬 Starting offer_page_playlists pipeline.",
        extra={
            "offer_id": offer_id,
            "offer_search_group": search_group_name,
            "playlist_count": len(similar_offer_playlist_configs),
            "playlist_types": [playlist_config.playlist_type for playlist_config in similar_offer_playlist_configs],
        },
    )

    playlist_items: list[OfferPlaylistItem] = []
    used_item_ids: set[str] = set()

    for playlist_config in similar_offer_playlist_configs:
        playlist_item = await _generate_single_similar_offer_playlist(
            playlist_config=playlist_config,
            offer_id=offer_id,
            user_id=user_id,
            latitude=latitude,
            longitude=longitude,
            exclude_item_ids=used_item_ids or None,
        )
        playlist_items.append(playlist_item)

        # Resolve item_ids of this playlist's results and add them to the exclusion
        # set for the next (lower-priority) playlist.
        newly_used_item_ids = await _resolve_item_ids_for_offer_ids(playlist_item.results)
        used_item_ids |= newly_used_item_ids

    logger.info(
        "✅ offer_page_playlists pipeline completed.",
        extra={
            "offer_id": offer_id,
            "playlists": [
                {"title": playlist.title, "type": playlist.playlist_type, "count": len(playlist.results)}
                for playlist in playlist_items
            ],
        },
    )

    return OfferPagePlaylistsResponse(
        offer_id=offer_id,
        playlists=list(playlist_items),
    )
