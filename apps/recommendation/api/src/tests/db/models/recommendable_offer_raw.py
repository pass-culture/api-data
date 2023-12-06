from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.types import Boolean

from huggy.database.base import Base


class FakeRecommendableOffersRaw(Base):
    """
    Fake Database model of recommendable_offers table.
    """

    __tablename__ = "recommendable_offer_raw"

    offer_id = Column(String(256))
    item_id = Column(String(256))
    product_id = Column(String(256))
    category = Column(String(256))
    subcategory_id = Column(String(256))
    search_group_name = Column(String(256))
    venue_id = Column(String(256))
    name = Column(String(256))
    gtl_id = Column(String(256))
    gtl_l1 = Column(String(256))
    gtl_l2 = Column(String(256))
    gtl_l3 = Column(String(256))
    gtl_l4 = Column(String(256))
    is_numerical = Column(Boolean)
    is_national = Column(Boolean)
    is_geolocated = Column(Boolean)
    is_sensitive = Column(Boolean)
    offer_creation_date = Column(DateTime)
    stock_beginning_date = Column(DateTime)
    stock_price = Column(Float)
    is_duo = Column(Boolean)
    offer_type_domain = Column(String(256))
    offer_type_label = Column(String(256))
    booking_number = Column(Integer)
    total_offers = Column(Integer)
    is_underage_recommendable = Column(Boolean)
    venue_latitude = Column(Float)
    venue_longitude = Column(Float)
    default_max_distance = Column(Integer)
    unique_id = Column(String(256), primary_key=True)
