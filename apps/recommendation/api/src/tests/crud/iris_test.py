import pytest

from huggy.crud.iris import get_iris_from_coordinates
from sqlalchemy.orm import Session
from tests.db.schema.iris import (
    iris_paris_chatelet,
    iris_nok,
    iris_unknown,
    iris_marseille_cours_julien,
    iris_marseille_vieux_port,
    IrisTestExample,
)
import logging

logger = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "irises",
    [
        iris_paris_chatelet,  # default
        iris_nok,  # none
        iris_unknown,  # unknown
        iris_marseille_cours_julien,
        iris_marseille_cours_julien,
    ],
)
def test_get_iris_from_coordinates(
    setup_default_database: Session, irises: IrisTestExample
):
    """This test should return the right expected_iris_id given a latitude and longitude."""
    iris_id = get_iris_from_coordinates(
        setup_default_database,
        latitude=irises.latitude,
        longitude=irises.longitude,
    )
    assert iris_id == irises.iris_id
