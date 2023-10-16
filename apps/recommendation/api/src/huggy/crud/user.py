from sqlalchemy.orm import Session
from sqlalchemy import func

import huggy.schemas.user as user_sh
from huggy.crud.iris import get_iris_from_coordinates
import huggy.models.enriched_user as user_db
from pydantic import parse_obj_as
from huggy.utils.cloud_logging import logger
import typing as t


class UserContextDB:
    def get_user_context(
        self, db: Session, user_id: str, latitude: float, longitude: float
    ) -> user_sh.UserContext:
        """Query the database in ORM mode to get additional information about
        an user. (age, number of bookings, number of clicks, number of favorites,
        amount of remaining deposit).
        """

        iris_id = get_iris_from_coordinates(db, latitude=latitude, longitude=longitude)

        user = user_sh.UserContext(
            user_id=user_id,
            age=18,
            longitude=longitude,
            latitude=latitude,
            found=False,
            iris_id=iris_id,
            is_geolocated=iris_id is not None,
        )

        user_profile_db = self.get_user_profile(db, user_id)

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

    def get_user_profile(
        self, db: Session, user_id: str
    ) -> t.Optional[user_sh.UserProfileDB]:
        if user_id is not None:
            user_table = user_db.EnrichedUser().get_available_table(db)

            user_profile = (
                db.query(
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
                )
                .filter(user_table.user_id == user_id)
                .first()
            )
            if user_profile is not None:
                return parse_obj_as(user_sh.UserProfileDB, user_profile)
        return None
