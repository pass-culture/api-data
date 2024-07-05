import typing as t

from huggy.models.non_recommendable_items import NonRecommendableItems
from huggy.schemas.user import UserContext
from huggy.utils.exception import log_error
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession


async def get_non_recommendable_items(
    db: AsyncSession, user: UserContext
) -> t.List[str]:
    try:
        non_recommendable_items_table: NonRecommendableItems = (
            await NonRecommendableItems().get_available_table(db)
        )
        non_recommendable_items = (
            await db.execute(
                select(non_recommendable_items_table.item_id.label("item_id")).where(
                    non_recommendable_items_table.user_id == user.user_id
                )
            )
        ).fetchall()

        return [
            recommendable_item.item_id for recommendable_item in non_recommendable_items
        ]
    except ProgrammingError as exc:
        log_error(exc, message="Exception error on get_non_recommendable_items")
    return []
