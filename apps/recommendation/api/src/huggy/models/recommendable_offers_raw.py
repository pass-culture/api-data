from geoalchemy2 import Geography
from huggy.database.base import Base, MaterializedBase
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String


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
    new_offer_is_geolocated = Column(Boolean)
    new_offer_creation_days = Column(Integer)
    new_offer_stock_price = Column(Float)
    new_offer_stock_beginning_days = Column(Integer)
    new_offer_centroid_x = Column(Float)
    new_offer_centroid_y = Column(Float)


class RecommendableOffersRawMv(RecommendableOffersRaw, Base):
    __tablename__ = "recommendable_offers_raw_mv"


class RecommendableOffersRawMvTmp(RecommendableOffersRaw, Base):
    __tablename__ = "recommendable_offers_raw_mv_tmp"


class RecommendableOffersRawMvOld(RecommendableOffersRaw, Base):
    __tablename__ = "recommendable_offers_raw_mv_old"
