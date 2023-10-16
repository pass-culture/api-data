import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Any, Dict
from huggy.utils.env_vars import DATA_GCP_TEST_POSTGRES_PORT, DB_NAME
from tests.db import (
    create_non_recommendable_items,
    create_enriched_user_mv,
    create_enriched_user_mv_old,
    create_enriched_user_mv_tmp,
    create_item_ids_mv,
    create_recommendable_offers_raw,
    create_recommendable_offers_raw_mv,
    create_recommendable_offers_raw_mv_tmp,
    create_recommendable_offers_raw_mv_old,
    create_iris_france,
)
from sqlalchemy import inspect, text
from huggy.models.item_ids_mv import ItemIdsMv
from huggy.models.recommendable_offers_raw import (
    RecommendableOffersRawMv,
    RecommendableOffersRawMvOld,
    RecommendableOffersRawMvTmp,
)
from huggy.models.non_recommendable_items import NonRecommendableItems
from huggy.models.enriched_user import (
    EnrichedUserMv,
    EnrichedUserMvOld,
    EnrichedUserMvTmp,
)
from huggy.models.iris_france import IrisFrance

import logging

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


def get_engine():
    engine = create_engine(
        f"postgresql+psycopg2://postgres:postgres@127.0.0.1:{DATA_GCP_TEST_POSTGRES_PORT}/{DB_NAME}"
    )
    return engine


def clean_db(engine, models=MODELS):
    logger.debug("Cleaning all tables...")
    for model in models:
        if inspect(engine).has_table(model.__tablename__):
            logger.debug(f"Removing... {model.__tablename__}")
            model.__table__.drop(engine)


@pytest.fixture()
def setup_empty_database(app_config: Dict[str, Any]) -> Session:
    engine = get_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_default_database() -> Session:
    engine = get_engine()
    clean_db(engine)
    create_recommendable_offers_raw(engine)
    create_recommendable_offers_raw_mv(engine)
    create_recommendable_offers_raw_mv_tmp(engine)
    create_recommendable_offers_raw_mv_old(engine)

    create_enriched_user_mv(engine)
    create_enriched_user_mv_tmp(engine)
    create_enriched_user_mv_old(engine)

    create_non_recommendable_items(engine)

    create_iris_france(engine)
    create_item_ids_mv(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def drop_mv_database(app_config: Dict[str, Any]) -> Session:
    """Removes the enriched_user_mv and recommendable_offers_raw_mv in order to test the switch."""
    engine = get_engine()
    clean_db(engine=engine, models=[EnrichedUserMv, RecommendableOffersRawMv])

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    try:
        yield db
    finally:
        # recreate
        create_enriched_user_mv(engine)
        create_recommendable_offers_raw_mv(engine)
        db.close()


@pytest.fixture()
def drop_mv_and_tmp_database(app_config: Dict[str, Any]) -> Session:
    """Removes the enriched_user_(mv and tmp) and recommendable_offers_raw_(mv and tmp) in order to test the switch."""
    engine = get_engine()
    clean_db(
        engine=engine,
        models=[
            EnrichedUserMv,
            EnrichedUserMvTmp,
            RecommendableOffersRawMv,
            RecommendableOffersRawMvTmp,
        ],
    )

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    try:
        yield db
    finally:
        create_enriched_user_mv(engine)
        create_recommendable_offers_raw_mv(engine)
        create_enriched_user_mv_tmp(engine)
        create_recommendable_offers_raw_mv_tmp(engine)
        db.close()
