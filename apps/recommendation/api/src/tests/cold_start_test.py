import pytest
from sqlalchemy.orm import Session

from huggy.core.model_selection.model_configuration import ModelFork
from huggy.core.model_selection import recommendation_endpoints
from huggy.schemas.user import User


@pytest.mark.parametrize(
    ["user", "expected_status"],
    [
        (
            User(
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
            User(
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
            User(
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
    setup_database: Session,
    user: User,
    expected_status: bool,
):
    _, model_status = ModelFork(
        cold_start_model=recommendation_endpoints.retrieval_reco,
        warm_start_model=recommendation_endpoints.retrieval_reco,
    ).get_user_status(user)
    assert model_status == expected_status
