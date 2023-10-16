from sqlalchemy.orm import Session
from huggy.schemas.user import UserContext
from huggy.models.non_recommendable_items import NonRecommendableItems
import typing as t


def get_non_recommendable_items(db: Session, user: UserContext) -> t.List[str]:
    non_recommendable_items = db.query(
        NonRecommendableItems.item_id.label("item_id")
    ).filter(NonRecommendableItems.user_id == user.user_id)

    return [
        recommendable_item.item_id for recommendable_item in non_recommendable_items
    ]
