import os
from typing import Any
from unittest.mock import patch, Mock
import pytest

from huggy.models.recommendable_offers_raw import get_available_table


@pytest.mark.parametrize(
    "materialized_view_name, expected_result",
    [
        (
            "RecommendableOffersRaw",
            [
                "RecommendableOffersRawMvTemp",
                "RecommendableOffersRawMvOld",
                "RecommendableOffersRawMv",
                " RecommendableOffersRaw",
            ],
        )
    ],
)
def test_should_raise_exception_when_it_does_not_come_from_sql_alchemy(
    setup_database: Any, materialized_view_name: str, expected_result: str
):
    # Given
    with patch("huggy.utils.database.SessionLocal") as connection_mock:
        connection_mock.return_value = setup_database
        # When
        result = get_available_table(connection_mock, materialized_view_name)

        # Then
        assert result is not None
        assert result in expected_result
