from huggy.database.repository import MaterializedViewRepository
from huggy.models.non_recommendable_items import (
    NonRecommendableItems,
    NonRecommendableItemsMv,
    NonRecommendableItemsMvOld,
    NonRecommendableItemsMvTmp,
)
from huggy.schemas.user import UserContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class NonRecommendableOfferService:
    """Service for handling non-recommendable offers"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = MaterializedViewRepository(
            session,
            NonRecommendableItems,
            fallback_tables=[
                NonRecommendableItemsMv,
                NonRecommendableItemsMvOld,
                NonRecommendableItemsMvTmp,
            ],
        )

    async def get_non_recommendable_items(self, user: UserContext) -> list[str]:
        """
        Get list of item IDs that should not be recommended to the user
        """
        if not user or not user.user_id:
            return []

        try:
            non_recommendable_table = await self.repository.get_available_model()

            query = select(non_recommendable_table.item_id.label("item_id")).where(
                non_recommendable_table.user_id == user.user_id
            )

            result = await self.session.execute(query)
            return [row.item_id for row in result.fetchall()]

        except Exception as exc:
            from huggy.utils.exception import log_error

            log_error(exc, message="Exception error on get_non_recommendable_items")
            return []

    async def is_item_non_recommendable(self, user: UserContext, item_id: str) -> bool:
        """
        Check if a specific item is non-recommendable for the user
        """
        if not user or not user.user_id or not item_id:
            return False

        try:
            non_recommendable_table = await self.repository.get_available_model()

            query = (
                select(non_recommendable_table.item_id)
                .where(
                    non_recommendable_table.user_id == user.user_id,
                    non_recommendable_table.item_id == item_id,
                )
                .limit(1)
            )

            result = await self.session.execute(query)
            return result.scalar_one_or_none() is not None

        except Exception as exc:
            from huggy.utils.exception import log_error

            log_error(exc, message="Exception error on is_item_non_recommendable")
            return False

    async def filter_recommendable_items(
        self, user: UserContext, item_ids: list[str]
    ) -> list[str]:
        """
        Filter out non-recommendable items from a list
        """
        if not user or not user.user_id or not item_ids:
            return item_ids

        non_recommendable_items = await self.get_non_recommendable_items(user)
        non_recommendable_set = set(non_recommendable_items)

        return [item_id for item_id in item_ids if item_id not in non_recommendable_set]

    async def get_non_recommendable_count(self, user: UserContext) -> int:
        """
        Get the count of non-recommendable items for a user
        """
        if not user or not user.user_id:
            return 0

        try:
            non_recommendable_table = await self.repository.get_available_model()

            query = select(non_recommendable_table.item_id).where(
                non_recommendable_table.user_id == user.user_id
            )

            result = await self.session.execute(query)
            return len(result.fetchall())

        except Exception as exc:
            from huggy.utils.exception import log_error

            log_error(exc, message="Exception error on get_non_recommendable_count")
            return 0

    async def bulk_check_non_recommendable(
        self, user: UserContext, item_ids: list[str]
    ) -> dict[str, bool]:
        """
        Efficiently check multiple items for non-recommendable status
        """
        result = {item_id: False for item_id in item_ids}

        if not user or not user.user_id or not item_ids:
            return result

        try:
            non_recommendable_table = await self.repository.get_available_model()

            query = select(non_recommendable_table.item_id).where(
                non_recommendable_table.user_id == user.user_id,
                non_recommendable_table.item_id.in_(item_ids),
            )

            db_result = await self.session.execute(query)
            non_recommendable_items = {row.item_id for row in db_result.fetchall()}

            # Update result with non-recommendable status
            for item_id in item_ids:
                result[item_id] = item_id in non_recommendable_items

        except Exception as exc:
            from huggy.utils.exception import log_error

            log_error(exc, message="Exception error on bulk_check_non_recommendable")

        return result
