import pytest
from sqlalchemy.orm import Session

from huggy.core.model_selection.model_configuration import ModelFork
from huggy.core.model_selection import recommendation_endpoints
from huggy.crud.user import get_user_profile


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
    user = get_user_profile(setup_database, user_id, latitude, longitude)
    _, model_status = ModelFork(
        cold_start_model=recommendation_endpoints.retrieval_reco,
        warm_start_model=recommendation_endpoints.retrieval_reco,
    ).get_user_status(user)
    assert model_status == expected_status
