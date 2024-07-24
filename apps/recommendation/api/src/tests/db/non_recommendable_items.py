from huggy.models.non_recommendable_items import NonRecommendableItemsMv
from sqlalchemy import insert

from tests.db.utils import create_model


async def create_non_recommendable_items(session):
    await create_model(session, NonRecommendableItemsMv)

    async with session.bind.connect() as conn:
        await conn.execute(
            insert(NonRecommendableItemsMv),
            [
                {"user_id": "111", "item_id": "isbn-1"},
                {"user_id": "112", "item_id": "isbn-3"},
            ],
        )
        await conn.commit()
