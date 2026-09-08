from typing import Any

import sqlalchemy.orm as sa_orm
from geoalchemy2 import Geography
from geoalchemy2 import Geometry
from sqlalchemy import Integer

from models.base import Base


class IrisFrance(Base):
    __tablename__ = "iris_france_mv"

    id: sa_orm.Mapped[int] = sa_orm.mapped_column(Integer, primary_key=True)

    iriscode: sa_orm.Mapped[int] = sa_orm.mapped_column(Integer)
    centroid: sa_orm.Mapped[Any | None] = sa_orm.mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )
    shape: sa_orm.Mapped[Any] = sa_orm.mapped_column(Geometry("POLYGON", srid=0))
