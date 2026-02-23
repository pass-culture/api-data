import sqlalchemy.orm as sa_orm
from sqlalchemy import String

from models.base import Base


# class ItemIds(Base):
#     __tablename__ = "item_ids"
#
#     offer_id = Column(String, primary_key=True)
#
#     booking_number = Column(Float)
#     is_sensitive = Column(Boolean)
#     item_id = Column(String)
#     venue_latitude = Column(Float)
#     venue_longitude = Column(Float)


class NonRecommendableItems(Base):
    __tablename__ = "non_recommendable_items_mv"

    item_id: sa_orm.Mapped[str] = sa_orm.mapped_column(String(256), primary_key=True)
    user_id: sa_orm.Mapped[str] = sa_orm.mapped_column(String(256), primary_key=True)
