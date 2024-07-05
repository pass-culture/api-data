from huggy.models.enriched_user import (
    EnrichedUserMv,
    EnrichedUserMvOld,
    EnrichedUserMvTmp,
)
from sqlalchemy import insert

from tests.db.schema.user import raw_data
from tests.db.utils import create_model


async def create_enriched_user_mv(session):
    await create_model(session, EnrichedUserMv)
    await session.execute(insert(EnrichedUserMv), raw_data)
    await session.commit()


async def create_enriched_user_mv_old(session):
    await create_model(session, EnrichedUserMvOld)
    await session.execute(insert(EnrichedUserMvOld), raw_data)
    await session.commit()


async def create_enriched_user_mv_tmp(session):
    await create_model(session, EnrichedUserMvTmp)
    await session.execute(insert(EnrichedUserMvTmp), raw_data)
    await session.commit()
