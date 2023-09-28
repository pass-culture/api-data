import pytest
import os
from sqlalchemy.orm import Session

from huggy.crud.user import get_user_profile

ENV_SHORT_NAME = os.getenv("ENV_SHORT_NAME")


class UserTest:
    @pytest.mark.parametrize(
        ["user_id", "expected_age", "expected_deposit"],
        [("115", 15, 20), ("116", 16, 30), ("117", 17, 30), ("118", 18, 300)],
    )
    def test_get_user_profile(
        self, setup_database: Session, user_id, expected_age, expected_deposit
    ):
        latitude = None
        longitude = None
        user = get_user_profile(setup_database, user_id, latitude, longitude)
        assert user.age == expected_age, f"age is right"
        assert (
            user.user_deposit_remaining_credit == expected_deposit
        ), f"remaining credit is right"
