import logging
import os
from typing import Any, Dict

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from huggy.database.database import sessionmanager
from huggy.database.session import get_db
from huggy.database.config import config
from huggy.models.enriched_user import (
    EnrichedUserMv,
    EnrichedUserMvOld,
    EnrichedUserMvTmp,
)
from huggy.models.iris_france import IrisFrance
from huggy.models.item_ids_mv import ItemIdsMv
from huggy.models.non_recommendable_items import NonRecommendableItems
from huggy.models.recommendable_offers_raw import (
    RecommendableOffersRawMv,
    RecommendableOffersRawMvOld,
    RecommendableOffersRawMvTmp,
)

import asyncio
from contextlib import ExitStack
import pytest
from fastapi.testclient import TestClient
from huggy import init_app
from tests.db.utils import clean_db

logger = logging.getLogger(__name__)

import asyncio

from tests.db import (
    create_enriched_user_mv,
    create_enriched_user_mv_old,
    create_enriched_user_mv_tmp,
    create_iris_france,
    create_item_ids_mv,
    create_non_recommendable_items,
    create_recommendable_offers_raw,
    create_recommendable_offers_raw_mv,
    create_recommendable_offers_raw_mv_old,
    create_recommendable_offers_raw_mv_tmp,
)

MODELS = [
    ItemIdsMv,
    RecommendableOffersRawMv,
    RecommendableOffersRawMvOld,
    RecommendableOffersRawMvTmp,
    NonRecommendableItems,
    EnrichedUserMv,
    EnrichedUserMvOld,
    EnrichedUserMvTmp,
    IrisFrance,
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
def app_config() -> Dict[str, Any]:
    return {}


@pytest.fixture(scope="session")
def event_loop(request):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def connection_test(event_loop):
    sessionmanager.init(config.DB_CONFIG)
    yield
    await sessionmanager.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_default_database(connection_test):
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
        await create_iris_france(session)
        await create_item_ids_mv(session)
        yield session


@pytest.fixture(scope="function", autouse=True)
async def session_override(app, connection_test):
    async def get_db_override():
        async with sessionmanager.session() as session:
            yield session

    app.dependency_overrides[get_db] = get_db_override


@pytest.fixture()
async def drop_mv_database(connection_test, app_config: Dict[str, Any]) -> AsyncSession:
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
    connection_test, app_config: Dict[str, Any]
) -> AsyncSession:
    """Removes the enriched_user_(mv and tmp) and recommendable_offers_raw_(mv and tmp) in order to test the switch."""
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
async def setup_empty_database(app_config: Dict[str, Any]) -> AsyncSession:
    async with sessionmanager.session() as session:
        yield session
