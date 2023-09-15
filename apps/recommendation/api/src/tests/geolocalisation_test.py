import os
import pytest

from huggy.crud.iris import (
    get_iris_from_coordinates,
)
from sqlalchemy.orm import Session

DATA_GCP_TEST_POSTGRES_PORT = os.getenv("DATA_GCP_TEST_POSTGRES_PORT")
DB_NAME = os.getenv("DB_NAME", "postgres")

TEST_DATABASE_CONFIG = {
    "user": "postgres",
    "password": "postgres",
    "host": "127.0.0.1",
    "port": DATA_GCP_TEST_POSTGRES_PORT,
    "database": DB_NAME,
}


@pytest.mark.parametrize(
    ["longitude", "latitude", "expected_iris_id"],
    [
        (2.33294778256192, 48.831930605740254, 45327),
        (None, None, None),
        # (-122.1639346, 37.4449422, None)
    ],
)
def test_get_iris_from_coordinates(
    setup_database: Session, longitude, latitude, expected_iris_id
):
    iris_id = get_iris_from_coordinates(setup_database, longitude, latitude)

    # Then
    assert iris_id == expected_iris_id
