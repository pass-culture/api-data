import pytest

from sqlalchemy import inspect
from sqlalchemy.orm import Session
from huggy.models.user import User
from huggy.models.recommendable_offers_raw import RecommendableOffersRaw


@pytest.mark.parametrize(
    "table_name, expected_result",
    [
        ("enriched_user", False),
        ("enriched_user_mv", True),
        ("recommendable_offers_raw", False),
        ("recommendable_offers_raw_mv", True),
        ("iris_france", True),
        ("non_recommendable_items", True),
        ("item_ids_mv", True),
    ],
)
def test_tables_should_exist(
    setup_database: Session, table_name: str, expected_result: bool
):
    engine = setup_database.get_bind()
    result = inspect(engine).has_table(table_name)
    # assert result is not None
    assert result is expected_result


@pytest.mark.parametrize(
    "base_db, expected_result",
    [
        (User, "enriched_user_mv"),
        (RecommendableOffersRaw, "recommendable_offers_raw_mv"),
    ],
)
def test_materialized_views(setup_database: Session, base_db, expected_result):
    """This test return the available table. In our case"""
    table = base_db().get_available_table(setup_database)
    assert table.__tablename__ == expected_result
