import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import ExitStack
from typing import Any

import pytest
from fastapi.testclient import TestClient
from huggy import init_app
from huggy.database.config import config
from huggy.database.database import sessionmanager
from huggy.database.session import get_db
from huggy.models.enriched_user import (
    EnrichedUserMv,
    EnrichedUserMvOld,
    EnrichedUserMvTmp,
)
from huggy.models.iris_france import (
    IrisFranceMv,
    IrisFranceMvOld,
    IrisFranceMvTmp,
)
from huggy.models.item_ids import ItemIdsMv
from huggy.models.non_recommendable_items import NonRecommendableItemsMv
from huggy.models.recommendable_offers_raw import (
    RecommendableOffersRawMv,
    RecommendableOffersRawMvOld,
    RecommendableOffersRawMvTmp,
)
from sqlalchemy.ext.asyncio import AsyncSession

from tests.db import (
    create_enriched_user_mv,
    create_enriched_user_mv_old,
    create_enriched_user_mv_tmp,
    create_iris_france_mv,
    create_iris_france_mv_old,
    create_iris_france_mv_tmp,
    create_item_ids_mv,
    create_non_recommendable_items,
    create_recommendable_offers_raw,
    create_recommendable_offers_raw_mv,
    create_recommendable_offers_raw_mv_old,
    create_recommendable_offers_raw_mv_tmp,
)
from tests.db.utils import clean_db

logger = logging.getLogger(__name__)


MODELS = [
    ItemIdsMv,
    RecommendableOffersRawMv,
    RecommendableOffersRawMvOld,
    RecommendableOffersRawMvTmp,
    NonRecommendableItemsMv,
    EnrichedUserMv,
    EnrichedUserMvOld,
    EnrichedUserMvTmp,
    IrisFranceMv,
    IrisFranceMvOld,
    IrisFranceMvTmp,
]


@pytest.fixture(autouse=True)
def app():
    with ExitStack():
        yield init_app(init_db=False)


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session", autouse=True)
def app_config() -> dict[str, Any]:
    return {}


@pytest.fixture(scope="session")
def event_loop(request):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def _connection_test(event_loop):
    sessionmanager.init(config.DB_CONFIG)
    async with sessionmanager.session():
        yield
    await sessionmanager.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_default_database(_connection_test):
    async with sessionmanager.session() as session:
        await clean_db(session, models=MODELS)
        await create_recommendable_offers_raw(session)
        await create_recommendable_offers_raw_mv(session)
        await create_recommendable_offers_raw_mv_tmp(session)
        await create_recommendable_offers_raw_mv_old(session)
        await create_enriched_user_mv(session)
        await create_enriched_user_mv_tmp(session)
        await create_enriched_user_mv_old(session)
        await create_non_recommendable_items(session)
        await create_iris_france_mv(session)
        await create_iris_france_mv_tmp(session)
        await create_iris_france_mv_old(session)
        await create_item_ids_mv(session)

        yield session


@pytest.fixture(autouse=True)
async def _session_override(app, _connection_test):
    async def get_db_override():
        async with sessionmanager.session() as session:
            yield session

    app.dependency_overrides[get_db] = get_db_override


@pytest.fixture()
async def drop_mv_database(
    _connection_test, app_config: dict[str, Any]
) -> AsyncGenerator[Any, Any]:
    """Removes the enriched_user_mv and recommendable_offers_raw_mv in order to test the switch."""
    async with sessionmanager.session() as session:
        await clean_db(session, models=[EnrichedUserMv, RecommendableOffersRawMv])
        try:
            yield session
        finally:
            # recreate
            await create_enriched_user_mv(session)
            await create_recommendable_offers_raw_mv(session)


@pytest.fixture()
async def drop_mv_and_tmp_database(
    _connection_test, app_config: dict[str, Any]
) -> AsyncGenerator[Any, Any]:
    """
    Removes the enriched_user_(mv and tmp) and recommendable_offers_raw_(mv and tmp)
        in order to test the switch.
    """
    async with sessionmanager.session() as session:
        await clean_db(
            session,
            models=[
                EnrichedUserMv,
                EnrichedUserMvTmp,
                RecommendableOffersRawMv,
                RecommendableOffersRawMvTmp,
            ],
        )
        try:
            yield session
        finally:
            await create_enriched_user_mv(session)
            await create_recommendable_offers_raw_mv(session)
            await create_enriched_user_mv_tmp(session)
            await create_recommendable_offers_raw_mv_tmp(session)


@pytest.fixture()
async def setup_empty_database(app_config: dict[str, Any]) -> AsyncSession:
    async with sessionmanager.session() as session:
        yield session
