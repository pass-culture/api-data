import asyncio

from controllers.pipeline_similar_offer import generate_similar_offers
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
                search_group_names=[offer_search_group],  # type: ignore[list-item]
            ),
            SimilarOfferPlaylistConfig(
                title=OfferPlaylistTitleEnum.DANS_LA_MEME_CATEGORIE,
                playlist_type=OfferPlaylistTypeEnum.SAME_TYPE_GRAPH,
                retrieval_model=SimilarOfferModelChoices.graph,
                search_group_names=[offer_search_group],  # type: ignore[list-item]
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
        )

    return OfferPlaylistItem(
        title=playlist_config.title,
        playlist_type=playlist_config.playlist_type,
        results=similar_offers_response.results,
        params=similar_offers_response.params,
    )


async def generate_offer_page_playlists(
    offer_id: str,
    search_group_name: SearchGroupNameEnum,
    user_id: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> OfferPagePlaylistsResponse:
    """
    Build all recommendation playlists for an offer detail page in parallel.

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

    All calls are executed concurrently via ``asyncio.gather``, so the total
    latency is roughly equal to the slowest individual pipeline rather than
    the sum of all pipelines.

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

    playlist_items = await asyncio.gather(
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
