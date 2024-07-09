import logging
import typing as t

import huggy.models.enriched_user as user_db
import huggy.schemas.user as user_sh
from huggy.crud.iris import Iris
from huggy.utils.exception import log_error
from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class UserContextDB:
    async def get_user_context(
        self, db: AsyncSession, user_id: str, latitude: float, longitude: float
    ) -> user_sh.UserContext:
        """
        Query the database in ORM mode to get additional information about
        an user. (age, number of bookings, number of clicks, number of favorites,
        amount of remaining deposit).

        """

        iris_id = await Iris().get_iris_from_coordinates(
            db, latitude=latitude, longitude=longitude
        )

        user = user_sh.UserContext(
            user_id=user_id,
            age=18,
            longitude=longitude,
            latitude=latitude,
            found=False,
            iris_id=iris_id,
            is_geolocated=iris_id is not None,
        )

        user_profile_db = await self.get_user_profile(db, user_id)

        if user_profile_db is not None:
            user = user_sh.UserContext(
                user_id=user_id,
                longitude=longitude,
                latitude=latitude,
                found=True,
                iris_id=iris_id,
                age=user_profile_db.age,
                bookings_count=user_profile_db.bookings_count,
                clicks_count=user_profile_db.clicks_count,
                favorites_count=user_profile_db.favorites_count,
                user_deposit_remaining_credit=user_profile_db.user_deposit_remaining_credit,
                is_geolocated=iris_id is not None,
            )
        return user

    async def get_user_profile(
        self, db: AsyncSession, user_id: str
    ) -> t.Optional[user_sh.UserProfileDB]:
        if user_id is not None:
            try:
                user_table = await user_db.EnrichedUser().get_available_table(db)

                user_profile = (
                    await db.execute(
                        select(
                            user_table.user_id.label("user_id"),
                            func.date_part(
                                "year", func.age(user_table.user_birth_date)
                            ).label("age"),
                            func.coalesce(user_table.booking_cnt, 0).label(
                                "bookings_count"
                            ),
                            func.coalesce(user_table.consult_offer, 0).label(
                                "clicks_count"
                            ),
                            func.coalesce(
                                user_table.has_added_offer_to_favorites, 0
                            ).label("favorites_count"),
                            func.coalesce(
                                user_table.user_theoretical_remaining_credit,
                                user_table.user_deposit_initial_amount,
                            ).label("user_deposit_remaining_credit"),
                        ).where(user_table.user_id == user_id)
                    )
                ).fetchone()
                if user_profile is not None:
                    return TypeAdapter(user_sh.UserProfileDB).validate_python(
                        user_profile
                    )
            except ProgrammingError as exc:
                log_error(exc, message="Exception error on get_user_profile")

        return None
