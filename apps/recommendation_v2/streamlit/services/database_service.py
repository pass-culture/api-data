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
from core.user_context import THRESHOLD_BOOKINGS
from core.user_context import THRESHOLD_CLICKS
from core.user_context import THRESHOLD_FAVORITES
from models.offer import RecommendableOffers
from models.user import EnrichedUser


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

            # Apply cold start logic based on given thresholds
            if is_cold_start:
                stmt = stmt.where(
                    (EnrichedUser.booking_cnt < THRESHOLD_BOOKINGS)
                    & (EnrichedUser.consult_offer < THRESHOLD_CLICKS)
                    & (EnrichedUser.has_added_offer_to_favorites < THRESHOLD_FAVORITES)
                )
            else:
                stmt = stmt.where(
                    (EnrichedUser.booking_cnt >= THRESHOLD_BOOKINGS)
                    | (EnrichedUser.consult_offer >= THRESHOLD_CLICKS)
                    | (EnrichedUser.has_added_offer_to_favorites >= THRESHOLD_FAVORITES)
                )

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
    }
