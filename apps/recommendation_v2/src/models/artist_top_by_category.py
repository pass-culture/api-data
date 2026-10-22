import sqlalchemy.orm as sa_orm
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String

from models.base import Base


class ArtistTopByCategory(Base):
    __tablename__ = "artist_top_by_category_mv"

    artist_id: sa_orm.Mapped[str] = sa_orm.mapped_column(String(256), primary_key=True)
    search_group_name: sa_orm.Mapped[str] = sa_orm.mapped_column(String(256), primary_key=True)
    score_name: sa_orm.Mapped[str] = sa_orm.mapped_column(String(256), primary_key=True)
    score_value: sa_orm.Mapped[float] = sa_orm.mapped_column(Float)
    category_rank: sa_orm.Mapped[int] = sa_orm.mapped_column(Integer)
