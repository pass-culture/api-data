import pytest
from huggy.core.model_selection import RECOMMENDATION_ENDPOINTS
from huggy.schemas.user import UserContext


@pytest.mark.parametrize(
    ("user", "expected_status"),
    [
        (
            UserContext(
                user_id="111",
                longitude=None,
                latitude=None,
                found=True,
                iris_id="",
                age=18,
                bookings_count=3,
                clicks_count=1,
                favorites_count=1,
                user_deposit_remaining_credit=300,
            ),
            "algo",
        ),
        (
            UserContext(
                user_id="112",
                longitude=None,
                latitude=None,
                found=True,
                iris_id="",
                age=18,
                bookings_count=1,
                clicks_count=2,
                favorites_count=2,
                user_deposit_remaining_credit=300,
            ),
            "cold_start",
        ),
        (
            UserContext(
                user_id="113",
                longitude=None,
                latitude=None,
                found=True,
                iris_id="",
                age=18,
                bookings_count=1,
                clicks_count=2,
                favorites_count=2,
                user_deposit_remaining_credit=300,
            ),
            "cold_start",
        ),
    ],
)
def test_get_cold_start_status(
    user: UserContext,
    expected_status: bool,  # noqa: FBT001
):
    model_fork = RECOMMENDATION_ENDPOINTS["default"].generate()
    model_status = model_fork.get_user_status(user, "test")
    assert model_status.reco_origin == expected_status
