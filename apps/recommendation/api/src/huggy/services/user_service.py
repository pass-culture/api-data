from typing import Optional

from huggy.database.repository import MaterializedViewRepository
from huggy.models.enriched_user import EnrichedUser, EnrichedUserMv, EnrichedUserMvTmp
from huggy.schemas.user import UserContext, UserProfileDB
from huggy.services.iris_service import IrisService
from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class UserService:
    """Service for handling user-related operations"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = MaterializedViewRepository(
            session,
            EnrichedUser,
            fallback_tables=[EnrichedUserMv, EnrichedUserMvTmp],
        )
        self.iris_service = IrisService(session)

    async def get_user_context(
        self, user_id: str, latitude: float, longitude: float
    ) -> UserContext:
        """
        Get comprehensive user context including location and profile data
        """
        # Get IRIS location info
        iris_id = await self.iris_service.get_iris_from_coordinates(
            latitude=latitude, longitude=longitude
        )

        # Create base user context
        user = UserContext(
            user_id=user_id,
            age=18,  # Default age
            longitude=longitude,
            latitude=latitude,
            found=False,
            iris_id=iris_id,
            is_geolocated=iris_id is not None,
        )

        # Try to get enriched user profile
        user_profile = await self.get_user_profile(user_id)

        if user_profile is not None:
            user = UserContext(
                user_id=user_id,
                longitude=longitude,
                latitude=latitude,
                found=True,
                iris_id=iris_id,
                age=user_profile.age,
                bookings_count=user_profile.bookings_count,
                clicks_count=user_profile.clicks_count,
                favorites_count=user_profile.favorites_count,
                user_deposit_remaining_credit=user_profile.user_deposit_remaining_credit,
                is_geolocated=iris_id is not None,
            )

        return user

    async def get_user_profile(self, user_id: str) -> Optional[UserProfileDB]:
        """
        Get detailed user profile from enriched user data
        """
        if not user_id:
            return None

        try:
            user_table = await self.repository.get_available_model()

            query = select(
                user_table.user_id.label("user_id"),
                func.date_part("year", func.age(user_table.user_birth_date)).label(
                    "age"
                ),
                func.coalesce(user_table.booking_cnt, 0).label("bookings_count"),
                func.coalesce(user_table.consult_offer, 0).label("clicks_count"),
                func.coalesce(user_table.has_added_offer_to_favorites, 0).label(
                    "favorites_count"
                ),
                func.coalesce(
                    user_table.user_theoretical_remaining_credit,
                    user_table.user_deposit_initial_amount,
                ).label("user_deposit_remaining_credit"),
            ).where(user_table.user_id == user_id)

            result = await self.session.execute(query)
            user_profile = result.fetchone()

            if user_profile is not None:
                return TypeAdapter(UserProfileDB).validate_python(user_profile)

        except Exception as exc:
            # Log error but don't raise to allow graceful degradation
            from huggy.utils.exception import log_error

            log_error(exc, message="Exception error on get_user_profile")

        return None

    async def user_exists(self, user_id: str) -> bool:
        """Check if user exists in the system"""
        try:
            user_table = await self.repository.get_available_model()
            query = (
                select(user_table.user_id).where(user_table.user_id == user_id).limit(1)
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none() is not None
        except Exception:
            return False

    async def get_user_deposit_info(self, user_id: str) -> Optional[dict]:
        """Get user's deposit information"""
        try:
            user_table = await self.repository.get_available_model()

            query = select(
                user_table.user_deposit_initial_amount.label("initial_amount"),
                user_table.user_theoretical_remaining_credit.label("remaining_credit"),
                user_table.user_deposit_creation_date.label("creation_date"),
            ).where(user_table.user_id == user_id)

            result = await self.session.execute(query)
            deposit_info = result.fetchone()

            if deposit_info:
                return {
                    "initial_amount": deposit_info.initial_amount,
                    "remaining_credit": deposit_info.remaining_credit,
                    "creation_date": deposit_info.creation_date,
                }

        except Exception as exc:
            from huggy.utils.exception import log_error

            log_error(exc, message="Exception error on get_user_deposit_info")

        return None

    async def get_user_activity_stats(self, user_id: str) -> Optional[dict]:
        """Get user's activity statistics"""
        try:
            user_table = await self.repository.get_available_model()

            query = select(
                user_table.booking_cnt.label("bookings_count"),
                user_table.consult_offer.label("clicks_count"),
                user_table.has_added_offer_to_favorites.label("favorites_count"),
            ).where(user_table.user_id == user_id)

            result = await self.session.execute(query)
            stats = result.fetchone()

            if stats:
                return {
                    "bookings_count": stats.bookings_count or 0,
                    "clicks_count": stats.clicks_count or 0,
                    "favorites_count": stats.favorites_count or 0,
                }

        except Exception as exc:
            from huggy.utils.exception import log_error

            log_error(exc, message="Exception error on get_user_activity_stats")

        return None
