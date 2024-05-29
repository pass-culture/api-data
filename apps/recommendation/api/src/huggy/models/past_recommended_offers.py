from sqlalchemy import JSON, Column, DateTime, Float, Integer, String
from sqlalchemy.types import Boolean
from huggy.database.base import Base


class PastOfferContext(Base):
    """Database model of offer_context table.
    This table is used to log the context of the offer when it is recommended to an user.
    """

    __tablename__ = "past_offer_context"
    id = Column(Integer, primary_key=True)
    user_id = Column(String(256))
    offer_id = Column(String(256))
    call_id = Column(String(256))
    context = Column(String(256))
    context_extra_data = Column(JSON)
    date = Column(DateTime(timezone=True))
    user_bookings_count = Column(Float)
    user_clicks_count = Column(Float)
    user_favorites_count = Column(Float)
    user_deposit_remaining_credit = Column(Float)
    user_iris_id = Column(String(256))
    user_is_geolocated = Column(Boolean)
    user_latitude = Column(Float)
    user_longitude = Column(Float)
    user_extra_data = Column(JSON)
    offer_user_distance = Column(Float)
    offer_is_geolocated = Column(Boolean)
    offer_item_id = Column(String(256))
    offer_booking_number = Column(Float)
    offer_stock_price = Column(Float)
    offer_creation_date = Column(DateTime)
    offer_stock_beginning_date = Column(DateTime)
    offer_category = Column(String(256))
    offer_subcategory_id = Column(String(256))
    offer_item_rank = Column(Float)
    offer_item_score = Column(Float)
    offer_order = Column(Float)
    offer_venue_id = Column(String(256))
    offer_extra_data = Column(JSON)
