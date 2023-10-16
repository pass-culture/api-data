from sqlalchemy import inspect, insert, text
from huggy.models.recommendable_offers_raw import (
    RecommendableOffersRawMv,
    RecommendableOffersRawMvTmp,
    RecommendableOffersRawMvOld,
)
from tests.db.models.recommendable_offer_raw import FakeRecommendableOffersRaw
from huggy.models.item_ids_mv import ItemIdsMv
from tests.db.schema.offer import raw_data
import logging
from huggy.utils.database import Base

logger = logging.getLogger(__name__)


def create_fake_mv(engine, table_name):
    raw_table_name = FakeRecommendableOffersRaw.__tablename__
    sql = f"""
        CREATE TABLE {table_name} AS
        SELECT *, ST_SetSRID(ST_MakePoint(ro.venue_longitude, ro.venue_latitude), 4326)::geography as venue_geo  
        FROM {raw_table_name} ro;
    """
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
        conn.close()


def create_recommendable_offers_raw(engine):
    if inspect(engine).has_table(FakeRecommendableOffersRaw.__tablename__):
        FakeRecommendableOffersRaw.__table__.drop(engine)
    FakeRecommendableOffersRaw.__table__.create(bind=engine)

    with engine.connect() as conn:
        conn.execute(insert(FakeRecommendableOffersRaw), raw_data)
        conn.commit()
        conn.close()


def create_recommendable_offers_raw_mv(engine):
    table_name = RecommendableOffersRawMv.__tablename__
    if inspect(engine).has_table(table_name):
        RecommendableOffersRawMv.__table__.drop(engine)
    create_fake_mv(engine, table_name)


def create_recommendable_offers_raw_mv_tmp(engine):
    table_name = RecommendableOffersRawMvTmp.__tablename__
    if inspect(engine).has_table(table_name):
        RecommendableOffersRawMvTmp.__table__.drop(engine)
    create_fake_mv(engine, table_name)


def create_recommendable_offers_raw_mv_old(engine):
    table_name = RecommendableOffersRawMvOld.__tablename__
    if inspect(engine).has_table(table_name):
        RecommendableOffersRawMvOld.__table__.drop(engine)
    create_fake_mv(engine, table_name)


def create_item_ids_mv(engine):
    item_ids = [
        {
            "item_id": x["item_id"],
            "offer_id": x["offer_id"],
            "booking_number": x["booking_number"],
        }
        for x in raw_data
    ]
    if inspect(engine).has_table(ItemIdsMv.__tablename__):
        ItemIdsMv.__table__.drop(engine)
    ItemIdsMv.__table__.create(bind=engine)

    with engine.connect() as conn:
        conn.execute(insert(ItemIdsMv), item_ids)
        conn.commit()
        conn.close()
