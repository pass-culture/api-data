from datetime import datetime

import sqlalchemy.orm as sa_orm
from geoalchemy2 import Geography
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String

from models.base import Base


class RecommendableOffers(Base):
    __tablename__ = "recommendable_offers_raw_mv"

    unique_id = Column(String(256), primary_key=True)

    booking_number: sa_orm.Mapped[int] = sa_orm.mapped_column(Integer)
    default_max_distance: sa_orm.Mapped[int] = sa_orm.mapped_column(Integer)
    # h3_index = Column(String(16), index=True)
    item_id: sa_orm.Mapped[str] = sa_orm.mapped_column(String(256))
    offer_creation_date: sa_orm.Mapped[datetime] = sa_orm.mapped_column(DateTime)
    offer_id: sa_orm.Mapped[str] = sa_orm.mapped_column(String(256))
    stock_beginning_date: sa_orm.Mapped[datetime | None] = sa_orm.mapped_column(DateTime)
    venue_geo = Column(Geography(geometry_type="POINT", srid=4326))
    venue_latitude: sa_orm.Mapped[float] = sa_orm.mapped_column(Float)
    venue_longitude: sa_orm.Mapped[float] = sa_orm.mapped_column(Float)
