import pytest
import os
from sqlalchemy.orm import Session
from huggy.crud.user import UserContextDB
from huggy.schemas.user import UserProfileDB
from tests.db.schema.iris import iris_paris_chatelet, iris_nok, IrisTestExample
from tests.db.schema.user import (
    user_profile_unknown,
    user_profile_null,
    user_profile_111,
    user_profile_112,
    user_profile_113,
    user_profile_118,
    user_profile_117,
)

import logging

logger = logging.getLogger(__name__)


class UserTest:
    @pytest.mark.parametrize(
        ["user", "found"],
        [
            (user_profile_111, True),
            (user_profile_112, True),
            (user_profile_113, True),
            (user_profile_118, True),
            (user_profile_117, True),
            (user_profile_unknown, False),
            (user_profile_null, True),
        ],
    )
    def test_get_user_profile(
        self, setup_default_database: Session, user: UserProfileDB, found: bool
    ):
        result_user = UserContextDB().get_user_profile(
            setup_default_database, user.user_id
        )
        result_found = result_user is not None
        assert found == result_found, "user was found in DB"
        if found:
            assert result_user.age == user.age, f"age is right"
            assert (
                result_user.user_deposit_remaining_credit
                == user.user_deposit_remaining_credit
            ), f"user_deposit_remaining_credit is right"
            assert (
                result_user.clicks_count == user.clicks_count
            ), f"clicks_count is right"
            assert (
                result_user.bookings_count == user.bookings_count
            ), f"bookings_count is right"
            assert (
                result_user.favorites_count == user.favorites_count
            ), f"favorites_count is right"
            assert result_user.user_id == user.user_id, f"user_id is right"

    @pytest.mark.parametrize(
        ["user", "iris", "found"],
        [
            (user_profile_117, iris_paris_chatelet, True),
            (user_profile_112, iris_nok, True),
            (user_profile_null, iris_nok, True),
            (user_profile_unknown, iris_paris_chatelet, False),
        ],
    )
    def test_get(
        self,
        setup_default_database: Session,
        user: UserProfileDB,
        iris: IrisTestExample,
        found: bool,
    ):
        geolocated = iris.iris_id is not None
        result_user = UserContextDB().get_user_context(
            setup_default_database,
            user_id=user.user_id,
            latitude=iris.latitude,
            longitude=iris.longitude,
        )
        assert result_user.age == user.age, f"age is right"
        assert (
            result_user.user_deposit_remaining_credit
            == user.user_deposit_remaining_credit
        ), f"user_deposit_remaining_credit is right"
        assert result_user.clicks_count == user.clicks_count, f"clicks_count is right"
        assert (
            result_user.bookings_count == user.bookings_count
        ), f"bookings_count is right"
        assert (
            result_user.favorites_count == user.favorites_count
        ), f"favorites_count is right"
        assert result_user.user_id == user.user_id, f"user_id is right"
        assert result_user.longitude == iris.longitude, f"longitude is right"
        assert result_user.latitude == iris.latitude, f"latitude is right"
        assert result_user.iris_id == iris.iris_id, f"iris_id is right"
        assert result_user.found == found, f"found is right"
        assert result_user.is_geolocated == geolocated, f"is_geolocated is right"
