"""
Service layer for database operations within the Streamlit application.

Handles direct asynchronous connections to the database using SQLAlchemy,
managing event loops properly to avoid conflicts with Streamlit.
"""

import asyncio

from sqlalchemy import pool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql.expression import func

from config import settings
from controllers.pipeline_playlist_top_artists import TOP_ARTISTS_COUNT
from core.user_context import THRESHOLD_BOOKINGS
from core.user_context import THRESHOLD_CLICKS
from core.user_context import THRESHOLD_FAVORITES
from models.offer import RecommendableOffers
from models.similar_artists import SimilarArtist
from models.user import EnrichedUser


def _build_discovery_artist_composition_dict(
    discovery_artist_id: str,
    similar_artists_by_top_id: dict[str, list[dict]],
) -> dict:
    """
    Reconstruct the similarity-rank breakdown of a single discovery artist across the top artists.

    Args:
        discovery_artist_id (str): Artist ID of the discovery candidate.
        similar_artists_by_top_id (dict[str, list[dict]]): Mapping of
            ``top_artist_id -> raw similar_artists_json list``.

    Returns:
        dict: Composition metadata with ``artist_id``, ``appearance_count``, ``avg_rank``,
        and ``ranks_by_top_artist``.
    """
    ranks_by_top_artist = {
        top_artist_id: similar_entry["rank"]
        for top_artist_id, similar_artists in similar_artists_by_top_id.items()
        for similar_entry in similar_artists
        if similar_entry.get("artist_id_match") == discovery_artist_id
    }
    similarity_ranks = list(ranks_by_top_artist.values())
    appearance_count = len(similarity_ranks)
    average_rank = round(sum(similarity_ranks) / appearance_count, 2) if similarity_ranks else None

    return {
        "artist_id": discovery_artist_id,
        "appearance_count": appearance_count,
        "avg_rank": average_rank,
        "ranks_by_top_artist": ranks_by_top_artist,
    }


def get_playlist_top_artists_composition(
    playlist_artist_ids: list[str],
    top_artists_count: int = TOP_ARTISTS_COUNT,
) -> tuple[list[dict], list[dict]]:
    """
    Reconstruct the detailed composition of a ``playlist_top_artists`` API response from the database.

    The public API endpoint returns a flat list of artist IDs where:
    - The first ``top_artists_count`` (3) elements are the category's top artists.
    - The remaining elements are the discovery artists.

    For each discovery artist, this function queries ``similar_artist_mv`` for the top artists
    to rebuild its ``appearance_count``, ``avg_rank``, and ``ranks_by_top_artist`` breakdown
    for display in the Streamlit debug table.

    Args:
        playlist_artist_ids (list[str]): Flat ordered list of artist IDs returned by the API.
        top_artists_count (int): Number of leading top artists in the playlist (defaults to 3).

    Returns:
        tuple[list[dict], list[dict]]: A pair ``(top_artists, discovery_artists)`` where:
        - ``top_artists`` contains dicts with ``artist_id`` and ``category_rank``.
        - ``discovery_artists`` contains dicts with ``artist_id``, ``appearance_count``,
          ``avg_rank``, and ``ranks_by_top_artist``.
    """
    if not playlist_artist_ids:
        return [], []

    top_artist_ids = playlist_artist_ids[:top_artists_count]
    discovery_artist_ids = playlist_artist_ids[top_artists_count:]

    async def _fetch_similar_artists_by_top_id_async() -> dict[str, list[dict]]:
        temp_engine = create_async_engine(settings.DATABASE_URL, poolclass=pool.NullPool)
        temp_session_factory = async_sessionmaker(temp_engine, expire_on_commit=False)

        async with temp_session_factory() as session:
            statement = select(SimilarArtist.artist_id, SimilarArtist.similar_artists_json).where(
                SimilarArtist.artist_id.in_(top_artist_ids)
            )
            query_result = await session.execute(statement)
            similar_artists_by_top_id = {row.artist_id: row.similar_artists_json or [] for row in query_result.all()}

        await temp_engine.dispose()
        return similar_artists_by_top_id

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        similar_artists_by_top_id = loop.run_until_complete(_fetch_similar_artists_by_top_id_async())
    finally:
        loop.close()

    top_artists = [
        {"artist_id": artist_id, "category_rank": position}
        for position, artist_id in enumerate(top_artist_ids, start=1)
    ]

    discovery_artists = [
        _build_discovery_artist_composition_dict(discovery_artist_id, similar_artists_by_top_id)
        for discovery_artist_id in discovery_artist_ids
    ]

    return top_artists, discovery_artists


def get_random_user(*, is_cold_start: bool) -> str:
    """
    Retrieves a random user UUID from the database.

    Automatically creates and closes a temporary SQLAlchemy engine to safely
    run an asynchronous query within a Streamlit synchronous context.

    Parameters:
    - is_cold_start (bool): If True, filters for users with low activity thresholds.
                            If False, filters for highly active users.

    Returns:
    - str: The UUID of the randomly selected user.
    """

    async def _get_user_async():
        # Using a temporary engine with NullPool to avoid Streamlit event loop errors
        temp_engine = create_async_engine(settings.DATABASE_URL, poolclass=pool.NullPool)
        temp_session_factory = async_sessionmaker(temp_engine, expire_on_commit=False)

        async with temp_session_factory() as session:
            stmt = select(EnrichedUser.user_id)

            # Apply cold start logic based on given thresholds and embedding status
            has_enough_activity = (
                (EnrichedUser.booking_cnt >= THRESHOLD_BOOKINGS)
                | (EnrichedUser.consult_offer >= THRESHOLD_CLICKS)
                | (EnrichedUser.has_added_offer_to_favorites >= THRESHOLD_FAVORITES)
            )
            if is_cold_start:
                stmt = stmt.where(~has_enough_activity | ~EnrichedUser.user_is_embedded)
            else:
                is_warm_condition = has_enough_activity & EnrichedUser.user_is_embedded
                stmt = stmt.where(is_warm_condition)

            stmt = stmt.order_by(func.random()).limit(1)

            result = await session.execute(stmt)
            user_id_found = result.scalar()

        await temp_engine.dispose()
        return user_id_found

    # Manually handle the event loop to ensure isolation per Streamlit call
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_get_user_async())
    finally:
        loop.close()


def get_random_offer() -> str:
    """
    Retrieves a random offer ID from the database.

    Returns:
    - str: The offer_id of the randomly selected offer.
    """

    async def _get_offer_async():
        temp_engine = create_async_engine(settings.DATABASE_URL, poolclass=pool.NullPool)
        temp_session_factory = async_sessionmaker(temp_engine, expire_on_commit=False)

        async with temp_session_factory() as session:
            stmt = select(RecommendableOffers.offer_id).order_by(func.random()).limit(1)
            result = await session.execute(stmt)
            offer_id_found = result.scalar()

        await temp_engine.dispose()
        return offer_id_found

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_get_offer_async())
    finally:
        loop.close()


def get_user_metadata(user_id: str) -> dict | None:
    """
    Fetches all EnrichedUser database fields for a given user_id.

    Used by the Streamlit sidebar debug toggle to inspect a user's raw record
    (e.g. subscription latitude/longitude used as a geolocation fallback)
    without having to query BigQuery manually.

    Example:
        >>> get_user_metadata("1234-uuid")
        {
            "user_id": "1234-uuid",
            "booking_cnt": 3,
            "user_subscription_latitude": 44.84,
            "user_subscription_longitude": -0.58,
            ...
        }
        >>> get_user_metadata("unknown-user")
        None

    Parameters:
    - user_id (str): The UUID of the user to look up.

    Returns:
    - dict | None: A dictionary mapping each EnrichedUser field name to its value,
                  or None if no user matches the given user_id.
    """

    async def _fetch_enriched_user_record_async() -> EnrichedUser | None:
        # Using a temporary engine with NullPool to avoid Streamlit event loop errors
        temp_engine = create_async_engine(settings.DATABASE_URL, poolclass=pool.NullPool)
        temp_session_factory = async_sessionmaker(temp_engine, expire_on_commit=False)

        async with temp_session_factory() as session:
            enriched_user_record = await session.get(EnrichedUser, user_id)

        await temp_engine.dispose()
        return enriched_user_record

    # Manually handle the event loop to ensure isolation per Streamlit call
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        enriched_user_record = loop.run_until_complete(_fetch_enriched_user_record_async())
    finally:
        loop.close()

    if enriched_user_record is None:
        return None

    return {
        "user_id": enriched_user_record.user_id,
        "booking_cnt": enriched_user_record.booking_cnt,
        "consult_offer": enriched_user_record.consult_offer,
        "has_added_offer_to_favorites": enriched_user_record.has_added_offer_to_favorites,
        "user_theoretical_remaining_credit": enriched_user_record.user_theoretical_remaining_credit,
        "user_deposit_initial_amount": enriched_user_record.user_deposit_initial_amount,
        "user_birth_date": str(enriched_user_record.user_birth_date) if enriched_user_record.user_birth_date else None,
        "user_deposit_creation_date": (
            str(enriched_user_record.user_deposit_creation_date)
            if enriched_user_record.user_deposit_creation_date
            else None
        ),
        "user_subscription_latitude": enriched_user_record.user_subscription_latitude,
        "user_subscription_longitude": enriched_user_record.user_subscription_longitude,
        "user_is_embedded": enriched_user_record.user_is_embedded,
    }
