from sqlalchemy import Column, String

from huggy.database.base import Base
from huggy.database.base import Base, MaterializedBase


class NonRecommendableItems(MaterializedBase):
    def materialized_tables(self):
        return [
            NonRecommendableItemsMv,
            NonRecommendableItemsMvTmpOld,
            NonRecommendableItemsMvTmp,
        ]

    item_id = Column(String(256), primary_key=True)
    user_id = Column(String(256), primary_key=True)


class NonRecommendableItemsMv(NonRecommendableItems, Base):
    __tablename__ = "non_recommendable_items_mv"


class NonRecommendableItemsMvTmp(NonRecommendableItems, Base):
    __tablename__ = "non_recommendable_items_mv_tmp"


class NonRecommendableItemsMvTmpOld(NonRecommendableItems, Base):
    __tablename__ = "non_recommendable_items_mv_tmp_old"
