import sqlalchemy.orm as sa_orm
from sqlalchemy import String

from models.base import Base


class NonRecommendableItems(Base):
    __tablename__ = "non_recommendable_items_mv"

    item_id: sa_orm.Mapped[str] = sa_orm.mapped_column(String(256), primary_key=True)
    user_id: sa_orm.Mapped[str] = sa_orm.mapped_column(String(256), primary_key=True)
