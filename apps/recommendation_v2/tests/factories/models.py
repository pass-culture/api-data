from contextvars import ContextVar
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from random import randint
from typing import Any

from geoalchemy2 import Geography
from geoalchemy2 import Geometry
from polyfactory.factories.sqlalchemy_factory import SQLAlchemyFactory
from sqlalchemy.ext.asyncio import AsyncSession

from models.iris import IrisFrance
from models.items import NonRecommendableItems
from models.offer import RecommendableOffers
from models.past_offer_context import PastOfferContext
from models.similar_artists import SimilarArtist
from models.user import EnrichedUser
from models.venue import Venue


factory_session: ContextVar[AsyncSession] = ContextVar("factory_session")


class BaseModelFactory[T](SQLAlchemyFactory):
    """Base factory for all SQLAlchemy models.

    Extends ``SQLAlchemyFactory`` to:
    - Support GeoAlchemy2 spatial types (``Geography``, ``Geometry``).
    - Resolve the active ``AsyncSession`` from the ``factory_session`` context
      variable when no session is passed explicitly.

    Subclass this factory and set ``__model__`` to your target SQLAlchemy model.
    """

    __is_base_factory__ = True

    @classmethod
    def get_sqlalchemy_types(cls) -> dict[Any, Any]:
        """Return a mapping of SQLAlchemy column types to factory value generators.

        Adds support for GeoAlchemy2 spatial types on top of the default mapping.
        """
        return {**super().get_sqlalchemy_types(), Geography: Any, Geometry: Any}

    @classmethod
    async def create_async(cls, **kwargs: Any) -> Any:
        """Build a model instance, persist it, and return the refreshed object.

        Args:
            **kwargs: Field overrides forwarded to ``cls.build()``.
                      Pass ``session`` to override the context-var session.

        Returns:
            The persisted and refreshed model instance.
        """
        session: AsyncSession = kwargs.pop("session", None) or factory_session.get()

        instance = cls.build(**kwargs)

        session.add(instance)
        await session.commit()
        await session.refresh(instance)

        return instance


class RecommendableOffersFactory(BaseModelFactory[RecommendableOffers]):
    __model__ = RecommendableOffers

    venue_geo = None


class EnrichedUserFactory(BaseModelFactory[EnrichedUser]):
    """Factory for :class:`models.user.EnrichedUser`.

    Provides convenience constructors for the two main user profiles used in
    recommendation tests:

    - **Cold-start**: a new user with no activity (no bookings, no consults).
    - **Warm**: an engaged user with meaningful activity signals.

    Both profiles default to a random birth date yielding an age between 16 and
    20 years old, which corresponds to the target demographic for recommendations.
    """

    __model__ = EnrichedUser

    @classmethod
    def _generate_birth_date_for_age_range(cls, min_age: int, max_age: int) -> datetime:
        """Return a random birth date resulting in an age within [min_age, max_age].

        Args:
            min_age: Minimum age in years (inclusive).
            max_age: Maximum age in years (exclusive).

        Returns:
            A timezone-aware ``datetime`` in UTC representing the birth date.
        """
        days_in_year = 365.25

        random_age_in_days = randint(
            int(min_age * days_in_year),
            int(max_age * days_in_year) - 1,
        )

        return datetime.now(UTC) - timedelta(days=random_age_in_days)

    @classmethod
    async def create_cold_start(cls, **kwargs: Any) -> EnrichedUser:
        """Create and persist a cold-start user (no prior activity).

        A cold-start user has zero bookings, zero offer consults, and has never
        added an offer to their favourites.

        Args:
            **kwargs: Additional field overrides. ``user_birth_date`` defaults to
                      a random date in the 16-20 age range if not provided.

        Returns:
            The persisted :class:`~models.user.EnrichedUser` instance.
        """
        if "user_birth_date" not in kwargs:
            kwargs["user_birth_date"] = cls._generate_birth_date_for_age_range(16, 20)

        return await cls.create_async(
            booking_cnt=0,
            consult_offer=0,
            has_added_offer_to_favorites=0,
            **kwargs,
        )

    @classmethod
    async def create_warm(cls, **kwargs: Any) -> EnrichedUser:
        """Create and persist a warm user (active engagement signals).

        A warm user has a meaningful number of bookings, offer consults, and
        favourites, making them eligible for personalised recommendations.

        Args:
            **kwargs: Additional field overrides. ``user_birth_date`` defaults to
                      a random date in the 16-20 age range if not provided.

        Returns:
            The persisted :class:`~models.user.EnrichedUser` instance.
        """
        if "user_birth_date" not in kwargs:
            kwargs["user_birth_date"] = cls._generate_birth_date_for_age_range(16, 20)

        return await cls.create_async(
            booking_cnt=5,
            consult_offer=30,
            has_added_offer_to_favorites=5,
            **kwargs,
        )


class VenueFactory(BaseModelFactory[Venue]):
    __model__ = Venue

    venue_geo = None


class IrisFranceFactory(BaseModelFactory[IrisFrance]):
    __model__ = IrisFrance

    shape = None


class NonRecommendableItemsFactory(BaseModelFactory[NonRecommendableItems]):
    __model__ = NonRecommendableItems


class PastOfferContextFactory(BaseModelFactory[PastOfferContext]):
    __model__ = PastOfferContext


class SimilarArtistFactory(BaseModelFactory[SimilarArtist]):
    __model__ = SimilarArtist
