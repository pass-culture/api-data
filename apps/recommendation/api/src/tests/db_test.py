import pytest
from huggy.database.utils import check_table_exists
from huggy.models.enriched_user import EnrichedUser
from huggy.models.recommendable_offers_raw import RecommendableOffersRaw
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def test_extensions(setup_empty_database: AsyncSession):
    async with setup_empty_database.bind.connect() as conn:
        results = await conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'postgis';")
        )
        results.fetchone()
    assert results is not None


@pytest.mark.parametrize(
    ("table_name", "expected_result"),
    [
        ("enriched_user_mv", True),
        ("recommendable_offers_raw_mv", True),
        ("iris_france_mv", True),
        ("non_recommendable_items_mv", True),
        ("item_ids_mv", True),
    ],
)
async def test_tables_should_exist(
    setup_default_database: AsyncSession,
    table_name: str,
    expected_result: bool,  # noqa: FBT001
):
    """This test should return all available tables in default context."""
    result = await check_table_exists(setup_default_database, table_name)

    # assert result is not None
    assert result is expected_result


@pytest.mark.parametrize(
    ("table_name", "expected_result"),
    [
        ("enriched_user_mv", False),
        ("recommendable_offers_raw_mv", False),
        ("enriched_user_mv_tmp", True),
        ("recommendable_offers_raw_mv_tmp", True),
    ],
)
async def only_tmp_tables_should_exist(
    setup_tmp_database: AsyncSession,
    table_name: str,
    expected_result: bool,  # noqa: FBT001
):
    """This test should return only available tables in tmp database context."""
    result = await check_table_exists(setup_tmp_database, table_name)
    assert result is expected_result


@pytest.mark.parametrize(
    ("base_db", "expected_result"),
    [
        (EnrichedUser, "enriched_user_mv"),
        (RecommendableOffersRaw, "recommendable_offers_raw_mv"),
    ],
)
async def test_materialized_views(
    setup_default_database: AsyncSession, base_db, expected_result
):
    """This test should return the default tables."""
    table = await base_db().get_available_table(setup_default_database)
    assert table.__tablename__ == expected_result


# @pytest.mark.parametrize(
#     "base_db, expected_result",
#     [
#         (EnrichedUser, "enriched_user_mv_tmp"),
#         (RecommendableOffersRaw, "recommendable_offers_raw_mv_tmp"),
#     ],
# )
# async def test_materialized_tmp_views(
#     setup_default_database: AsyncSession,
#     drop_mv_database: AsyncSession,
#     base_db,
#     expected_result,
# ):
#     """This test should return tmp table only."""
#     table = await base_db().get_available_table(setup_default_database)
#     assert table.__tablename__ == expected_result


# @pytest.mark.parametrize(
#     "base_db, expected_result",
#     [
#         (EnrichedUser, "enriched_user_mv_old"),
#         (RecommendableOffersRaw, "recommendable_offers_raw_mv_old"),
#     ],
# )
# async def test_materialized_old_views(
#     setup_default_database: AsyncSession,
#     drop_mv_and_tmp_database: AsyncSession,
#     base_db,
#     expected_result,
# ):
#     """This test shloud return the old tables only."""
#     table = await base_db().get_available_table(setup_default_database)
#     assert table.__tablename__ == expected_result
