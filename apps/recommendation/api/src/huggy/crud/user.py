from sqlalchemy.orm import Session
from sqlalchemy import func

from huggy.schemas.user import User
from huggy.crud.iris import get_iris_from_coordinates
import huggy.models.enriched_user as enriched_user

# from huggy.models.enriched_user import get_available_table
from huggy.utils.database import bind_engine


def get_user_profile(
    db: Session, user_id: str, latitude: float, longitude: float
) -> User:
    """Query the database in ORM mode to get additional information about
    an user. (age, number of bookings, number of clicks, number of favorites,
    amount of remaining deposit).
    """

    if latitude and longitude:
        iris_id = get_iris_from_coordinates(db, latitude, longitude)
    else:
        iris_id = None

    if user_id is not None:
        # engine = db.get_bind()  # --> None

        user_table = enriched_user.UserMv
        # user_table = get_available_table(engine, "User")

        user_profile = (
            db.query(
                user_table.user_deposit_creation_date - user_table.user_birth_date,
                func.coalesce(user_table.booking_cnt, 0),
                func.coalesce(user_table.consult_offer, 0),
                func.coalesce(user_table.has_added_offer_to_favorites, 0),
                func.coalesce(
                    user_table.user_theoretical_remaining_credit,
                    user_table.user_deposit_initial_amount,
                ),
            )
            .filter(user_table.user_id == user_id)
            .first()
        )

        if user_profile is not None:
            user = User(
                user_id=user_id,
                longitude=longitude,
                latitude=latitude,
                found=True,
                iris_id=iris_id,
                age=int(user_profile[0].days / 365) if user_profile[0] else None,
                bookings_count=user_profile[1],
                clicks_count=user_profile[2],
                favorites_count=user_profile[3],
                user_deposit_remaining_credit=user_profile[4],
            )

        else:
            user = User(
                user_id=user_id,
                longitude=longitude,
                latitude=latitude,
                found=False,
                iris_id=iris_id,
            )
    # TODO: add case where user_id is none
    return user
