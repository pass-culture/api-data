import sqlalchemy.orm as sa_orm
from sqlalchemy import Boolean
from sqlalchemy import String

from models.base import Base


class Artist(Base):
    __tablename__ = "artist_mv"

    artist_id: sa_orm.Mapped[str] = sa_orm.mapped_column(String(256), primary_key=True)
    main_search_group_name: sa_orm.Mapped[str | None] = sa_orm.mapped_column(String(256), nullable=True)

    # This field is used to indicate whether the artist has a bookable offer in the main search group.
    main_search_group_name_has_bookable_offer: sa_orm.Mapped[bool | None] = sa_orm.mapped_column(Boolean, nullable=True)
