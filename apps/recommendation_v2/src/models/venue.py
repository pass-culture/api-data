import sqlalchemy.orm as sa_orm
from geoalchemy2 import Geography
from sqlalchemy import Column
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String

from models.base import Base


class Venue(Base):
    __tablename__ = "venue_h3_mapping_mv"

    venue_id = Column(Integer, primary_key=True)

    latitude: sa_orm.Mapped[float] = sa_orm.mapped_column(Float)
    longitude: sa_orm.Mapped[float] = sa_orm.mapped_column(Float)
    venue_geo = Column(Geography(geometry_type="POINT", srid=4326))

    # H3 resolution columns available in the materialized view.
    # Only resolutions 5-9 are materialised; using any other value in geo.py would
    # produce an AttributeError at query time (see H3Resolution in geo.py).
    h3_res5: sa_orm.Mapped[str | None] = sa_orm.mapped_column(String, index=True)
    h3_res6: sa_orm.Mapped[str | None] = sa_orm.mapped_column(String, index=True)
    h3_res7: sa_orm.Mapped[str | None] = sa_orm.mapped_column(String, index=True)
    h3_res8: sa_orm.Mapped[str | None] = sa_orm.mapped_column(String, index=True)
    h3_res9: sa_orm.Mapped[str | None] = sa_orm.mapped_column(String, index=True)
