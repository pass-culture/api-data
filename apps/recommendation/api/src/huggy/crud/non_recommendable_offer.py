import typing as t

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from huggy.models.non_recommendable_items import NonRecommendableItems
from huggy.schemas.user import UserContext


async def get_non_recommendable_items(
    db: AsyncSession, user: UserContext
) -> t.List[str]:
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
