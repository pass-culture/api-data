import sqlalchemy.orm as sa_orm
from sqlalchemy import JSON
from sqlalchemy import String

from models.base import Base


class SimilarArtist(Base):
    __tablename__ = "similar_artist_mv"

    artist_id: sa_orm.Mapped[str] = sa_orm.mapped_column(String(256), primary_key=True)
    similar_artists_json: sa_orm.Mapped[list] = sa_orm.mapped_column(JSON)
