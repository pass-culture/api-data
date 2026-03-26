from sqlalchemy import insert

from huggy.models.similar_artist import (
    SimilarArtistMv,
    SimilarArtistMvOld,
    SimilarArtistMvTmp,
)
from tests.db.schema.artist import raw_data
from tests.db.utils import create_model


async def create_similar_artist_mv(session):
    await create_model(session, SimilarArtistMv)
    await session.execute(insert(SimilarArtistMv), raw_data)
    await session.commit()


async def create_similar_artist_mv_old(session):
    await create_model(session, SimilarArtistMvOld)
    await session.execute(insert(SimilarArtistMvOld), raw_data)
    await session.commit()


async def create_similar_artist_mv_tmp(session):
    await create_model(session, SimilarArtistMvTmp)
    await session.execute(insert(SimilarArtistMvTmp), raw_data)
    await session.commit()
