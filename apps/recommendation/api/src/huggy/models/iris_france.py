from geoalchemy2 import Geometry
from huggy.database.base import Base, MaterializedBase
from sqlalchemy import Column, Integer, String


class IrisFrance(MaterializedBase):
    """Database model of iris_france table.
    This table is used to retrieve iris_id from coordinates (latitude, longitude)."""

    def materialized_tables(self):
        return [
            IrisFranceMv,
            IrisFranceMvOld,
            IrisFranceMvTmp,
        ]

    id = Column(Integer, primary_key=True)
    iriscode = Column(Integer)
    centroid = Column(String(256))
    shape = Column(Geometry("POLYGON"))


class IrisFranceMv(IrisFrance, Base):
    __tablename__ = "iris_france_mv"


class IrisFranceMvTmp(IrisFrance, Base):
    __tablename__ = "iris_france_mv_tmp"


class IrisFranceMvOld(IrisFrance, Base):
    __tablename__ = "iris_france_mv_old"
