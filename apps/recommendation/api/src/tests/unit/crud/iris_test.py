import logging

import pytest
from huggy.crud.iris import Iris
from sqlalchemy.ext.asyncio import AsyncSession
from tests.db.schema.iris import (
    IrisTestExample,
    iris_marseille_cours_julien,
    iris_marseille_vieux_port,
    iris_nok,
    iris_paris_chatelet,
    iris_unknown,
)

logger = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "irises",
    [
        iris_paris_chatelet,  # default
        iris_nok,  # none
        iris_unknown,  # unknown
        iris_marseille_cours_julien,
        iris_marseille_vieux_port,
    ],
)
async def test_get_iris_from_coordinates(
    setup_default_database: AsyncSession, irises: IrisTestExample
):
    """This test should return the right expected_iris_id given a latitude and longitude."""
    iris_id = await Iris().get_iris_from_coordinates(
        setup_default_database,
        latitude=irises.latitude,
        longitude=irises.longitude,
    )
    assert iris_id == irises.iris_id
