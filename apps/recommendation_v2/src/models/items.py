import sqlalchemy.orm as sa_orm
from sqlalchemy import String, Float, Boolean

from models.base import Base


class ItemIds(Base):
    __tablename__ = "item_ids_mv"

    offer_id: sa_orm.Mapped[str] = sa_orm.mapped_column(String(256), primary_key=True)
    item_id: sa_orm.Mapped[str] = sa_orm.mapped_column(String(256))
    booking_number: sa_orm.Mapped[float] = sa_orm.mapped_column(Float, default=0.0)
    is_sensitive: sa_orm.Mapped[bool] = sa_orm.mapped_column(Boolean)
    venue_latitude: sa_orm.Mapped[float | None] = sa_orm.mapped_column(Float)
    venue_longitude: sa_orm.Mapped[float | None] = sa_orm.mapped_column(Float)


class NonRecommendableItems(Base):
    __tablename__ = "non_recommendable_items_mv"

    item_id: sa_orm.Mapped[str] = sa_orm.mapped_column(String(256), primary_key=True)
    user_id: sa_orm.Mapped[str] = sa_orm.mapped_column(String(256), primary_key=True)
