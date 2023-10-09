from sqlalchemy import Column, String, Integer, Float, DateTime
from sqlalchemy.types import Boolean

from huggy.utils.database import MaterializedBase, Base


class RecommendableOffersRaw(MaterializedBase):
    """
    Database model of recommendable_offers table.
    """

    def materialized_tables(self):
        return [
            RecommendableOffersRawMv,
            RecommendableOffersRawMvTmp,
            RecommendableOffersRawMvOld,
        ]

    offer_id = Column(String(256), primary_key=True)
    item_id = Column(String(256))
    product_id = Column(String(256))
    category = Column(String(256))
    subcategory_id = Column(String(256))
    search_group_name = Column(String(256))
    gtl_id = Column(String(256))
    gtl_l1 = Column(String(256))
    gtl_l2 = Column(String(256))
    gtl_l3 = Column(String(256))
    gtl_l4 = Column(String(256))
    venue_id = Column(String(256))
    name = Column(String(256))
    is_numerical = Column(Boolean)
    is_national = Column(Boolean)
    is_geolocated = Column(Boolean)
    offer_creation_date = Column(DateTime)
    stock_beginning_date = Column(DateTime)
    stock_price = Column(Float)
    is_duo = Column(Boolean)
    offer_type_domain = Column(String(256))
    offer_type_label = Column(String(256))
    booking_number = Column(Integer)
    is_underage_recommendable = Column(Boolean)
    venue_latitude = Column(Float)
    venue_longitude = Column(Float)
    default_max_distance = Column(Integer)
    unique_id = Column(String(256))


class RecommendableOffersRawMv(RecommendableOffersRaw, Base):
    __tablename__ = "recommendable_offers_raw_mv"


class RecommendableOffersRawMvTmp(RecommendableOffersRaw, Base):
    __tablename__ = "recommendable_offers_raw_mw_tmp"


class RecommendableOffersRawMvOld(RecommendableOffersRaw, Base):
    __tablename__ = "recommendable_offers_raw_mv_old"
