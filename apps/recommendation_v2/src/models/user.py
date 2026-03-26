from datetime import datetime

import sqlalchemy.orm as sa_orm
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String

from models.base import Base


class EnrichedUser(Base):
    __tablename__ = "enriched_user_mv"

    user_id: sa_orm.Mapped[str] = sa_orm.mapped_column(String(256), primary_key=True)

    booking_cnt: sa_orm.Mapped[int] = sa_orm.mapped_column(Integer)
    consult_offer: sa_orm.Mapped[int] = sa_orm.mapped_column(Integer)
    has_added_offer_to_favorites: sa_orm.Mapped[int] = sa_orm.mapped_column(Integer)
    user_birth_date: sa_orm.Mapped[datetime | None] = sa_orm.mapped_column(DateTime(timezone=True))
    user_deposit_creation_date: sa_orm.Mapped[datetime | None] = sa_orm.mapped_column(DateTime(timezone=True))
    user_deposit_initial_amount: sa_orm.Mapped[float] = sa_orm.mapped_column(Float)
    user_theoretical_remaining_credit: sa_orm.Mapped[float] = sa_orm.mapped_column(Float)
