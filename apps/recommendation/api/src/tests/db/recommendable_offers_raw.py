import logging

from sqlalchemy import insert, inspect, text

from huggy.models.item_ids import ItemIdsMv
from huggy.models.recommendable_offers_raw import (
    RecommendableOffersRawMv,
    RecommendableOffersRawMvOld,
    RecommendableOffersRawMvTmp,
)
from tests.db.models.recommendable_offer_raw import FakeRecommendableOffersRaw
from tests.db.schema.offer import raw_data
from tests.db.utils import create_model

logger = logging.getLogger(__name__)


async def create_fake_mv(session, table_name):
    raw_table_name = FakeRecommendableOffersRaw.__tablename__
    sql = f"""
        CREATE TABLE {table_name} AS
        SELECT *, ST_SetSRID(ST_MakePoint(ro.venue_longitude, ro.venue_latitude), 4326)::geography as venue_geo  
        FROM {raw_table_name} ro;
    """

    await session.execute(text(sql))
    await session.commit()


async def create_recommendable_offers_raw(session):
    await create_model(session, FakeRecommendableOffersRaw)
    await session.execute(insert(FakeRecommendableOffersRaw), raw_data)
    await session.commit()


async def create_recommendable_offers_raw_mv(session):
    table_name = RecommendableOffersRawMv.__tablename__
    await create_fake_mv(session, table_name)


async def create_recommendable_offers_raw_mv_tmp(session):
    table_name = RecommendableOffersRawMvTmp.__tablename__
    await create_fake_mv(session, table_name)


async def create_recommendable_offers_raw_mv_old(session):
    table_name = RecommendableOffersRawMvOld.__tablename__
    await create_fake_mv(session, table_name)


async def create_item_ids_mv(session):
    await create_model(session, ItemIdsMv)
    item_ids = [
        {
            "item_id": x["item_id"],
            "offer_id": x["offer_id"],
            "booking_number": x["booking_number"],
        }
        for x in raw_data
    ]

    await session.execute(insert(ItemIdsMv), item_ids)
    await session.commit()
