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
    [
        ("enriched_user", True),
        ("recommendable_offers_raw", True),
        ("iris_france", True),
        ("non_recommendable_items", True),
        ("item_ids_mv", True),
    ],
)
def test_tables_should_exist(
    setup_database: Session, table_name: str, expected_result: bool
):
    result = inspect(setup_database.get_bind()).has_table(table_name)
    # assert result is not None
    assert result is expected_result
