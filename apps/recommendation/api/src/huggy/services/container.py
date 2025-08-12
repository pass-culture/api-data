from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from huggy.database.database import sessionmanager
from huggy.services.iris_service import IrisService
from huggy.services.non_recommendable_offer_service import NonRecommendableOfferService
from huggy.services.offer_service import OfferService
from huggy.services.recommendable_offer_service import RecommendableOfferService
from huggy.services.user_service import UserService
from sqlalchemy.ext.asyncio import AsyncSession


class ServiceContainer:
    """Dependency injection container for services"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._services = {}

    def get_recommendable_offer_service(self) -> RecommendableOfferService:
        """Get or create RecommendableOfferService instance"""
        if "recommendable_offer" not in self._services:
            self._services["recommendable_offer"] = RecommendableOfferService(
                self.session
            )
        return self._services["recommendable_offer"]

    def get_user_service(self) -> UserService:
        """Get or create UserService instance"""
        if "user" not in self._services:
            self._services["user"] = UserService(self.session)
        return self._services["user"]

    def get_iris_service(self) -> IrisService:
        """Get or create IrisService instance"""
        if "iris" not in self._services:
            self._services["iris"] = IrisService(self.session)
        return self._services["iris"]

    def get_offer_service(self) -> OfferService:
        """Get or create OfferService instance"""
        if "offer" not in self._services:
            self._services["offer"] = OfferService(self.session)
        return self._services["offer"]

    def get_non_recommendable_offer_service(self) -> NonRecommendableOfferService:
        """Get or create NonRecommendableOfferService instance"""
        if "non_recommendable_offer" not in self._services:
            self._services["non_recommendable_offer"] = NonRecommendableOfferService(
                self.session
            )
        return self._services["non_recommendable_offer"]


@asynccontextmanager
async def get_services() -> AsyncIterator[ServiceContainer]:
    """Get a service container with a database session"""
    async with sessionmanager.session() as session:
        container = ServiceContainer(session)
        yield container
