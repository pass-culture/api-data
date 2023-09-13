import pytest

from sqlalchemy import inspect
from sqlalchemy.orm import Session

# from huggy.models.recommendable_offers_raw import (
#     get_available_table,
#     RecommendableOffersRaw,
#     RecommendableOffersRawMvTmp,
#     RecommendableOffersRawMvOld,
#     RecommendableOffersRawMv,
# )
from huggy.utils.database import bind_engine


@pytest.mark.parametrize(
    "table_name, expected_result",
    [("enriched_user", True)],
)
def test_should_raise_exception_when_it_does_not_come_from_sql_alchemy(
    setup_database: Session, table_name: str, expected_result: bool
):
    result = inspect(setup_database.get_bind()).has_table(table_name)
    # assert result is not None
    assert result is expected_result
