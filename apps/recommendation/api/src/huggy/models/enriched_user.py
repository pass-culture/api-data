from huggy.database.base import Base, MaterializedBase
from sqlalchemy import Column, DateTime, Float, Integer, String


class EnrichedUser(MaterializedBase):
    """
    Database model of enriched_user table.
    This table is used to get informations about the user calling the API.

    """

    def materialized_tables(self):
        return [EnrichedUserMv, EnrichedUserMvOld, EnrichedUserMvTmp]

    user_id = Column(String(256), primary_key=True)
    user_deposit_creation_date = Column(DateTime(timezone=True))
    user_birth_date = Column(DateTime(timezone=True))
    user_deposit_initial_amount = Column(Float)
    user_theoretical_remaining_credit = Column(Float)
    booking_cnt = Column(Integer)
    consult_offer = Column(Integer)
    has_added_offer_to_favorites = Column(Integer)


class EnrichedUserMv(EnrichedUser, Base):
    __tablename__ = "enriched_user_mv"


class EnrichedUserMvTmp(EnrichedUser, Base):
    __tablename__ = "enriched_user_mv_tmp"


class EnrichedUserMvOld(EnrichedUser, Base):
    __tablename__ = "enriched_user_mv_old"
