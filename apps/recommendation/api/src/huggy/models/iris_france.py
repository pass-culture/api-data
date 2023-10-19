from geoalchemy2 import Geometry
from sqlalchemy import Column, Integer, String

from huggy.database.base import Base


class IrisFrance(Base):
    """Database model of iris_france table.
    This table is used to retrieve iris_id from coordinates (latitude, longitude)."""

    __tablename__ = "iris_france"
    id = Column(Integer, primary_key=True)
    iriscode = Column(Integer)
    centroid = Column(String(256))
    shape = Column(Geometry("POLYGON"))
