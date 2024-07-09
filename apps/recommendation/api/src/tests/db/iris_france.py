from huggy.models.iris_france import (
    IrisFranceMv,
    IrisFranceMvOld,
    IrisFranceMvTmp,
)
from sqlalchemy import insert

from tests.db.schema.iris import raw_data
from tests.db.utils import create_model


async def create_iris_france_mv(session):
    await create_model(session, IrisFranceMv)
    await session.execute(insert(IrisFranceMv), raw_data)
    await session.commit()


async def create_iris_france_mv_old(session):
    await create_model(session, IrisFranceMvOld)
    await session.execute(insert(IrisFranceMvOld), raw_data)
    await session.commit()


async def create_iris_france_mv_tmp(session):
    await create_model(session, IrisFranceMvTmp)
    await session.execute(insert(IrisFranceMvTmp), raw_data)
    await session.commit()
