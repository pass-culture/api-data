from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String

from models.base import Base


class PastOfferContext(Base):
    __tablename__ = "past_offer_context"

    id = Column(Integer, primary_key=True)

    call_id = Column(String(256))
    context = Column(String(256))
    context_extra_data = Column(JSON)
    date = Column(DateTime(timezone=True))
    offer_booking_number = Column(Float)
    offer_category = Column(String(256))
    offer_creation_date = Column(DateTime)
    offer_extra_data = Column(JSON)
    offer_id = Column(String(256))
    offer_is_geolocated = Column(Boolean)
    offer_item_id = Column(String(256))
    offer_item_rank = Column(Float)
    offer_item_score = Column(Float)
    offer_order = Column(Float)
    offer_stock_beginning_date = Column(DateTime)
    offer_stock_price = Column(Float)
    offer_subcategory_id = Column(String(256))
    offer_user_distance = Column(Float)
    offer_venue_id = Column(String(256))
    user_bookings_count = Column(Float)
    user_clicks_count = Column(Float)
    user_deposit_remaining_credit = Column(Float)
    user_extra_data = Column(JSON)
    user_favorites_count = Column(Float)
    user_id = Column(String(256))
    user_iris_id = Column(String(256))
    user_is_geolocated = Column(Boolean)
    user_latitude = Column(Float)
    user_longitude = Column(Float)
