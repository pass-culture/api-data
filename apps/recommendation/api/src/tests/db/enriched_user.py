from datetime import datetime, timedelta
import os
import pytest

import pandas as pd
import pytz
from sqlalchemy import create_engine, text, inspect, insert
from sqlalchemy.orm import sessionmaker, Session
from typing import Any, Dict

from huggy.models.enriched_user import (
    EnrichedUserMv,
    EnrichedUserMvOld,
    EnrichedUserMvTmp,
)
from tests.db.schema.user import (
    raw_data,
)
import logging

logger = logging.getLogger(__name__)


def create_enriched_user_mv(engine):
    if inspect(engine).has_table(EnrichedUserMv.__tablename__):
        EnrichedUserMv.__table__.drop(engine)
    EnrichedUserMv.__table__.create(bind=engine)

    with engine.connect() as conn:
        conn.execute(insert(EnrichedUserMv), raw_data)
        conn.commit()
        conn.close()


def create_enriched_user_mv_old(engine):
    if inspect(engine).has_table(EnrichedUserMvOld.__tablename__):
        EnrichedUserMvOld.__table__.drop(engine)
    EnrichedUserMvOld.__table__.create(bind=engine)

    with engine.connect() as conn:
        conn.execute(insert(EnrichedUserMvOld), raw_data)
        conn.commit()
        conn.close()


def create_enriched_user_mv_tmp(engine):
    if inspect(engine).has_table(EnrichedUserMvTmp.__tablename__):
        EnrichedUserMvTmp.__table__.drop(engine)
    EnrichedUserMvTmp.__table__.create(bind=engine)

    with engine.connect() as conn:
        conn.execute(insert(EnrichedUserMvTmp), raw_data)
        conn.commit()
        conn.close()
