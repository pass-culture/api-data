import logging
import os
from typing import Any, Dict

import pytest
from sqlalchemy import engine, insert, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from huggy.database.utils import get_engine
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
from tests.db.utils import clean_db, create_db

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

logger = logging.getLogger(__name__)

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


@pytest.fixture
def app_config() -> Dict[str, Any]:
    return {}


def get_session():
    conn = get_engine(local=True)
    AsyncSessionLocal = sessionmaker(conn, expire_on_commit=False, class_=AsyncSession)
    return AsyncSessionLocal()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_default_database() -> AsyncSession:
    session = get_session()
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
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture()
async def drop_mv_database(app_config: Dict[str, Any]) -> AsyncSession:
    """Removes the enriched_user_mv and recommendable_offers_raw_mv in order to test the switch."""
    session = get_session()
    await clean_db(session, models=[EnrichedUserMv, RecommendableOffersRawMv])
    try:
        yield session
    finally:
        # recreate
        await create_enriched_user_mv(session)
        await create_recommendable_offers_raw_mv(session)
        await session.close()


@pytest.fixture()
async def drop_mv_and_tmp_database(app_config: Dict[str, Any]) -> AsyncSession:
    """Removes the enriched_user_(mv and tmp) and recommendable_offers_raw_(mv and tmp) in order to test the switch."""
    session = get_session()
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
    session = get_session()
    try:
        yield session
    finally:
        await session.close()
