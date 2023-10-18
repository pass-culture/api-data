from sqlalchemy import insert

from huggy.models.enriched_user import (
    EnrichedUserMv,
    EnrichedUserMvOld,
    EnrichedUserMvTmp,
)
from tests.db.schema.user import raw_data
from tests.db.utils import create_model


async def create_enriched_user_mv(session):
    await create_model(session, EnrichedUserMv)

    async with session.bind.connect() as conn:
        await conn.execute(insert(EnrichedUserMv), raw_data)
        await conn.commit()


async def create_enriched_user_mv_old(session):
    await create_model(session, EnrichedUserMvOld)

    async with session.bind.connect() as conn:
        await conn.execute(insert(EnrichedUserMvOld), raw_data)
        await conn.commit()


async def create_enriched_user_mv_tmp(session):
    await create_model(session, EnrichedUserMvTmp)

    async with session.bind.connect() as conn:
        await conn.execute(insert(EnrichedUserMvTmp), raw_data)
        await conn.commit()
