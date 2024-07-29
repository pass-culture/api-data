import logging

import pytest
from huggy.crud.recommendable_offer import RecommendableOffer as RecommendableOfferDB
from huggy.schemas.item import RecommendableItem
from huggy.schemas.offer import OfferDistance
from huggy.schemas.recommendable_offer import RecommendableOffer
from huggy.schemas.user import UserContext
from huggy.utils.distance import haversine_distance
from sqlalchemy.ext.asyncio import AsyncSession
from tests.db.schema.iris import (
    iris_marseille_cours_julien,
    iris_marseille_vieux_port,
    iris_paris_chatelet,
)
from tests.db.schema.offer_context import (
    items_all,
    items_books_marseille,
    items_no_geolocated,
    items_paris,
    offers_books_nearest_cours_julien_marseille_distance,
    offers_books_nearest_vieux_port_marseille_distance,
    offers_no_geolocated_distance,
    offers_paris_distance,
)
from tests.db.schema.user_context import (
    user_context_111_cours_julien_marseille,
    user_context_111_paris,
    user_context_111_vieux_port_marseille,
    user_context_null_nok,
    user_context_unknown_paris,
)

logger = logging.getLogger(__name__)

recommendable_offers_test_pool_paris = [
    {
        "description": """
            users: Unknown user, geolocated in Paris.
            items: All items are geolocated in Paris.
            expected: all offers geolocated in Paris.
        """,
        "user": user_context_unknown_paris,
        "items": items_paris,
        "expected_offers": offers_paris_distance,
    },
    {
        "description": """
            users: Unknown user, not geolocated.
            items: All items are geolocated in Paris.
            expected: no results.
        """,
        "user": user_context_null_nok,
        "items": items_paris,
        "expected_offers": [],
    },
    {
        "description": """
            users: 18 YO user 300€ credit, geolocated in Paris.
            items: All items are geolocated in Paris.
            expected: All offers in paris.
        """,
        "user": user_context_111_paris,
        "items": items_paris,
        "expected_offers": offers_paris_distance,
    },
    {
        "description": """
            users: 18 YO user 300€ credit, geolocated in Paris.
            items: Only non geolocated items.
            expected: non geolocated offers
        """,
        "user": user_context_111_paris,
        "items": items_no_geolocated,
        "expected_offers": offers_no_geolocated_distance,
    },
    {
        "description": """
            users: 18 YO user 300€ credit, geolocated in Paris.
            items: All items.
            expected: offers paris + non geolocated.
        """,
        "user": user_context_111_paris,
        "items": items_all,
        "expected_offers": offers_paris_distance + offers_no_geolocated_distance,
    },
]


recommendable_offers_test_pool_marseille = [
    {
        "description": """
            users: geolocated in Vieux Port, Marseille.
            items: all books items in Marseille.
            expected: nearest Bookshop.
        """,
        "user": user_context_111_vieux_port_marseille,
        "items": items_books_marseille,
        "expected_offers": offers_books_nearest_vieux_port_marseille_distance,
    },
    {
        "description": """
            users: geolocated in Cours Julien, Marseille.
            items: all books items in Marseille.
            expected: nearest Bookshop.
        """,
        "user": user_context_111_cours_julien_marseille,
        "items": items_books_marseille,
        "expected_offers": offers_books_nearest_cours_julien_marseille_distance,
    },
]


offers_distance_pool = [
    {
        "user": user_context_111_cours_julien_marseille,
        "offers": ["offer-manga-marseille-vieux-port-1"],
        "expected_offers": [
            OfferDistance(
                item_id="item-manga-marseille-vieux-port-1",
                offer_id="offer-manga-marseille-vieux-port-1",
                user_distance=haversine_distance(
                    iris_marseille_cours_julien.latitude,
                    iris_marseille_cours_julien.longitude,
                    iris_marseille_vieux_port.latitude,
                    iris_marseille_vieux_port.longitude,
                ),
                venue_latitude=iris_marseille_cours_julien.latitude,
                venue_longitude=iris_marseille_cours_julien.longitude,
            )
        ],
    },
    {
        "user": user_context_111_paris,
        "offers": ["offer-manga-marseille-vieux-port-1"],
        "expected_offers": [
            OfferDistance(
                item_id="item-manga-marseille-vieux-port-1",
                offer_id="offer-manga-marseille-vieux-port-1",
                user_distance=haversine_distance(
                    iris_paris_chatelet.latitude,
                    iris_paris_chatelet.longitude,
                    iris_marseille_vieux_port.latitude,
                    iris_marseille_vieux_port.longitude,
                ),
                venue_latitude=iris_paris_chatelet.latitude,
                venue_longitude=iris_paris_chatelet.longitude,
            )
        ],
    },
]


class RecommendableOfferTest:
    @pytest.mark.parametrize(
        "pool",
        recommendable_offers_test_pool_paris + recommendable_offers_test_pool_marseille,
    )
    async def test_get_recommendable_offer(
        self, setup_default_database: AsyncSession, pool: dict
    ):
        user: UserContext = pool["user"]
        items: list[RecommendableItem] = pool["items"]
        expected_offers: list[RecommendableOffer] = pool["expected_offers"]
        description = pool["description"]
        result_offers = await RecommendableOfferDB().get_nearest_offers(
            setup_default_database, user=user, recommendable_items_ids=items
        )
        expected_offers_ids = sorted([x.offer_id for x in expected_offers])
        result_offers_ids = sorted([x.offer_id for x in result_offers])
        assert (
            result_offers_ids == expected_offers_ids
        ), f"""
            {description} should have the same length.
            User details : {user}
            Expected : {expected_offers}
            Result : {result_offers}
        """

    @pytest.mark.parametrize("pool", offers_distance_pool)
    async def test_offer_distance(
        self, setup_default_database: AsyncSession, pool: dict
    ):
        user: UserContext = pool["user"]
        offer_list: list[str] = pool["offers"]
        expected_offers: list[OfferDistance] = pool["expected_offers"]

        result_offers = await RecommendableOfferDB().get_user_offer_distance(
            setup_default_database, user=user, offer_list=offer_list
        )
        result_offers = sorted(result_offers, key=lambda x: x.offer_id, reverse=True)
        expected_offers = sorted(
            expected_offers, key=lambda x: x.offer_id, reverse=True
        )
        assert len(result_offers) == len(
            expected_offers
        ), "list should have the same size."
        for x, y in zip(result_offers, expected_offers):
            assert x.offer_id == x.offer_id, "Offer shoud be the same."
            assert (
                x.user_distance - y.user_distance
            ) // 1000 == 0, "Distance should be the same in KM."
