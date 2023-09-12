import pytest

from huggy.models.recommendable_offers_raw import (
    get_available_table,
    RecommendableOffersRaw,
    RecommendableOffersRawMvTemp,
    RecommendableOffersRawMvOld,
    RecommendableOffersRawMv,
)
from huggy.utils.database import bind_engine


@pytest.mark.parametrize(
    "materialized_view_name, expected_result",
    [
        (
            "RecommendableOffersRaw",
            [
                RecommendableOffersRawMvTemp,
                RecommendableOffersRawMvOld,
                RecommendableOffersRawMv,
                RecommendableOffersRaw,
            ],
        )
    ],
)
def test_should_raise_exception_when_it_does_not_come_from_sql_alchemy(
    materialized_view_name: str, expected_result: str, engine=bind_engine
):
    result = get_available_table(engine, materialized_view_name)
    assert result is not None
    assert result in expected_result
