import pytest

from huggy.core.model_selection import recommendation_endpoints
from huggy.core.model_selection.model_configuration import ModelFork
from huggy.schemas.user import UserContext


@pytest.mark.parametrize(
    ["user", "expected_status"],
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
            "algo_v2",
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
            "cold_start_v2",
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
            "cold_start_v2",
        ),
    ],
)
def test_get_cold_start_status(
    user: UserContext,
    expected_status: bool,
):
    _, model_status = ModelFork(
        cold_start_model=recommendation_endpoints.retrieval_reco,
        warm_start_model=recommendation_endpoints.retrieval_reco,
    ).get_user_status(user)
    assert model_status == expected_status
