import sqlalchemy.orm as sa_orm
from sqlalchemy import Integer
from sqlalchemy import String

from models.base import Base


class QpiGtlMapping(Base):
    __tablename__ = "qpi_gtl_mapping_mv"

    ux_name: sa_orm.Mapped[str] = sa_orm.mapped_column(String(256), primary_key=True)
    gtl_id: sa_orm.Mapped[str | None] = sa_orm.mapped_column(String(256), nullable=True)
