from sqlalchemy import JSON, Column, DateTime, Float, Integer, String

from huggy.database.base import Base


class PastRecommendedOffers(Base):
    """Database model of past_recommendable_offers table.
    This table is used to log the offers recommended to an user."""

    __tablename__ = "past_recommended_offers"
    id = Column(Integer, primary_key=True)
    call_id = Column(String(256))
    userid = Column(Integer)
    offerid = Column(Integer)
    date = Column(DateTime(timezone=True))
    group_id = Column(String(256))
    reco_origin = Column(String(256))
    model_name = Column(String(256))
    model_version = Column(String(256))
    reco_filters = Column(JSON)
    user_iris_id = Column(String(256))


class PastSimilarOffers(Base):
    """Database model of past_recommendable_offers table.
    This table is used to log the offers recommended to an user."""

    __tablename__ = "past_similar_offers"
    id = Column(Integer, primary_key=True)
    call_id = Column(String(256))
    user_id = Column(Integer)
    offer_id = Column(Integer)
    origin_offer_id = Column(Integer)
    date = Column(DateTime(timezone=True))
    group_id = Column(String(256))
    model_name = Column(String(256))
    model_version = Column(String(256))
    reco_filters = Column(JSON)
    venue_iris_id = Column(String(256))


class OfferContext(Base):
    """Database model of offer_context table.
    This table is used to log the context of the offer when it is recommended to an user.
    """

    __tablename__ = "offer_context"
    id = Column(Integer, primary_key=True)
    user_id = Column(String(256))
    offer_id = Column(String(256))
    call_id = Column(String(256))
    context = Column(String(256))
    date = Column(DateTime(timezone=True))
    user_bookings_count = Column(Float)
    user_clicks_count = Column(Float)
    user_favorites_count = Column(Float)
    user_deposit_remaining_credit = Column(Float)
    user_iris_id = Column(String(256))
    user_latitude = Column(Float)
    user_longitude = Column(Float)
    offer_user_distance = Column(Float)
    offer_item_id = Column(String(256))
    offer_booking_number = Column(Float)
    offer_stock_price = Column(Float)
    offer_creation_date = Column(DateTime)
    offer_stock_beginning_date = Column(DateTime)
    offer_category = Column(String(256))
    offer_subcategory_id = Column(String(256))
    offer_item_score = Column(Float)
    offer_order = Column(Float)
    offer_venue_id = Column(String(256))
