import pytest

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from huggy.models.enriched_user import EnrichedUser
from huggy.models.recommendable_offers_raw import RecommendableOffersRaw


def test_extensions(setup_empty_database: Session):
    results = setup_empty_database.execute(
        text("SELECT extname FROM pg_extension WHERE extname = 'postgis';")
    ).fetchone()
    assert results is not None


@pytest.mark.parametrize(
    "table_name, expected_result",
    [
        ("enriched_user_mv", True),
        ("recommendable_offers_raw_mv", True),
        ("iris_france", True),
        ("non_recommendable_items", True),
        ("item_ids_mv", True),
    ],
)
def test_tables_should_exist(
    setup_default_database: Session, table_name: str, expected_result: bool
):
    """This test should return all available tables in default context."""
    engine = setup_default_database.get_bind()
    result = inspect(engine).has_table(table_name)
    # assert result is not None
    assert result is expected_result


@pytest.mark.parametrize(
    "table_name, expected_result",
    [
        ("enriched_user_mv", False),
        ("recommendable_offers_raw_mv", False),
        ("enriched_user_mv_tmp", True),
        ("recommendable_offers_raw_mv_tmp", True),
    ],
)
def only_tmp_tables_should_exist(
    setup_tmp_database: Session, table_name: str, expected_result: bool
):
    """This test should return only available tables in tmp database context."""
    engine = setup_tmp_database.get_bind()
    result = inspect(engine).has_table(table_name)
    assert result is expected_result


@pytest.mark.parametrize(
    "base_db, expected_result",
    [
        (EnrichedUser, "enriched_user_mv"),
        (RecommendableOffersRaw, "recommendable_offers_raw_mv"),
    ],
)
def test_materialized_views(setup_default_database: Session, base_db, expected_result):
    """This test should return the default tables."""
    table = base_db().get_available_table(setup_default_database)
    assert table.__tablename__ == expected_result


@pytest.mark.parametrize(
    "base_db, expected_result",
    [
        (EnrichedUser, "enriched_user_mv_tmp"),
        (RecommendableOffersRaw, "recommendable_offers_raw_mv_tmp"),
    ],
)
def test_materialized_tmp_views(
    setup_default_database: Session, drop_mv_database: Session, base_db, expected_result
):
    """This test should return tmp table only."""
    table = base_db().get_available_table(setup_default_database)
    assert table.__tablename__ == expected_result


@pytest.mark.parametrize(
    "base_db, expected_result",
    [
        (EnrichedUser, "enriched_user_mv_old"),
        (RecommendableOffersRaw, "recommendable_offers_raw_mv_old"),
    ],
)
def test_materialized_old_views(
    setup_default_database: Session,
    drop_mv_and_tmp_database: Session,
    base_db,
    expected_result,
):
    """This test shloud return the old tables only."""
    table = base_db().get_available_table(setup_default_database)
    assert table.__tablename__ == expected_result
