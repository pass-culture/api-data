from typing import Any

import sqlalchemy.orm as sa_orm
from geoalchemy2 import Geometry
from sqlalchemy import Integer
from sqlalchemy import String

from models.base import Base


class IrisFrance(Base):
    __tablename__ = "iris_france"

    id: sa_orm.Mapped[str] = sa_orm.mapped_column(String(256), primary_key=True)

    centroid: sa_orm.Mapped[str] = sa_orm.mapped_column(String(256), nullable=True)
    iriscode: sa_orm.Mapped[int] = sa_orm.mapped_column(Integer)
    shape: sa_orm.Mapped[Any] = sa_orm.mapped_column(Geometry("POLYGON"))
