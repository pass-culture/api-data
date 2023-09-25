import pytest
from sqlalchemy.orm import Session

from huggy.core.model_selection.model_configuration import ModelFork
from huggy.core.model_selection import recommendation_endpoints
from huggy.schemas.user import User


@pytest.mark.parametrize(
    ["user_id", "expected_status"],
    [
        ("111", "algo"),
        ("112", "cold_start"),
        ("113", "cold_start"),
        ("000", "unknown"),
    ],
)
def test_get_cold_start_status(
    setup_database: Session,
    user_id: str,
    expected_status: bool,
):
    latitude = None
    longitude = None
    user = User(
        user_id=user_id,
        longitude=longitude,
        latitude=latitude,
        found=True,
        iris_id="",
        age=18,
        bookings_count=2,
        clicks_count=3,
        favorites_count=1,
        user_deposit_remaining_credit=250,
    )
    _, model_status = ModelFork(
        cold_start_model=recommendation_endpoints.retrieval_reco,
        warm_start_model=recommendation_endpoints.retrieval_reco,
    ).get_user_status(user)
    assert model_status == expected_status
