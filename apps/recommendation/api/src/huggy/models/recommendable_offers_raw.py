from geoalchemy2 import Geography
from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.types import Boolean

from huggy.database.base import Base, MaterializedBase


class RecommendableOffersRaw(MaterializedBase):
    """
    Database model of recommendable_offers table.
    """

    def materialized_tables(self):
        return [
            RecommendableOffersRawMv,
            RecommendableOffersRawMvOld,
            RecommendableOffersRawMvTmp,
        ]

    offer_id = Column(String(256))
    item_id = Column(String(256))
    offer_creation_date = Column(DateTime)
    stock_beginning_date = Column(DateTime)
    booking_number = Column(Integer)
    venue_latitude = Column(Float)
    venue_longitude = Column(Float)
    venue_geo = Column(Geography(geometry_type="POINT", srid=4326))
    default_max_distance = Column(Integer)
    unique_id = Column(String(256), primary_key=True)


class RecommendableOffersRawMv(RecommendableOffersRaw, Base):
    __tablename__ = "recommendable_offers_raw_mv"


class RecommendableOffersRawMvTmp(RecommendableOffersRaw, Base):
    __tablename__ = "recommendable_offers_raw_mv_tmp"


class RecommendableOffersRawMvOld(RecommendableOffersRaw, Base):
    __tablename__ = "recommendable_offers_raw_mv_old"
