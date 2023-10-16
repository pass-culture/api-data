import pytest
import os
from sqlalchemy.orm import Session
import typing as t
from huggy.schemas.user import UserContext
from huggy.schemas.recommendable_offer import RecommendableOfferRawDB, OfferDistance
from huggy.crud.recommendable_offer import RecommendableOffer as RecommendableOfferDB
from tests.utils.distance import haversine_distance
from tests.db.schema.iris import (
    iris_marseille_cours_julien,
    iris_marseille_vieux_port,
    iris_paris_chatelet,
)
from tests.db.schema.user_context import (
    user_context_unknown_paris,
    user_context_null_nok,
    user_context_111_paris,
    user_context_111_unknown,
    user_context_118_paris,
    user_context_117_paris,
    user_context_111_vieux_port_marseille,
    user_context_111_cours_julien_marseille,
)
from tests.db.schema.offer_context import (
    items_paris,
    items_all,
    items_no_geolocated,
    items_books_paris_below_30_euros,
    offers_books_paris_30_euros,
    offers_paris,
    offers_below_30_euros,
    offers_no_geolocated,
    offers_underage_and_below_30_euros,
    offers_underage_books_paris_30_euros,
    items_books_marseille,
    offers_books_nearest_vieux_port_marseille,
    offers_books_nearest_cours_julien_marseille,
)

import logging

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
        "expected_offers": offers_paris,
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
        "expected_offers": offers_paris,
    },
    {
        "description": """
            users: 18 YO user 300€ credit, geolocated in Paris.
            items: Only non geolocated items.
            expected: non geolocated offers
        """,
        "user": user_context_111_paris,
        "items": items_no_geolocated,
        "expected_offers": offers_no_geolocated,
    },
    {
        "description": """
            users: 18 YO user 300€ credit, geolocated in Paris.
            items: All items.
            expected: offers paris + non geolocated.
        """,
        "user": user_context_111_paris,
        "items": items_all,
        "expected_offers": offers_paris + offers_no_geolocated,
    },
    {
        "description": """
            users: 18 YO user 300€ credit, not geolocated.
            items: All items.
            expected: non geolocated.
        """,
        "user": user_context_111_unknown,
        "items": items_all,
        "expected_offers": offers_no_geolocated,
    },
    {
        "description": """
            users: 18 YO user 30€ credit, geolocated Paris.
            items: All items.
            expected: all offers below 30€.
        """,
        "user": user_context_118_paris,
        "items": items_all,
        "expected_offers": offers_below_30_euros,
    },
    {
        "description": """
            users: 18 YO user 30€ credit, geolocated Paris.
            items: Geolocated Books items.
            expected: books geolocated.
        """,
        "user": user_context_118_paris,
        "items": items_books_paris_below_30_euros,
        "expected_offers": offers_books_paris_30_euros,
    },
    {
        "description": """
            users: 17 YO user 30€ credit, geolocated Paris.
            items: Geolocated Books items.
            expected: books geolocated.
        """,
        "user": user_context_117_paris,
        "items": items_books_paris_below_30_euros,
        "expected_offers": offers_underage_books_paris_30_euros,
    },
    {
        "description": """
            users: 17 YO user 30€ credit, geolocated Paris.
            items: all items.
            expected: underage + below 30€ .
        """,
        "user": user_context_117_paris,
        "items": items_all,
        "expected_offers": offers_underage_and_below_30_euros,
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
        "expected_offers": offers_books_nearest_vieux_port_marseille,
    },
    {
        "description": """
            users: geolocated in Cours Julien, Marseille.
            items: all books items in Marseille.
            expected: nearest Bookshop.
        """,
        "user": user_context_111_cours_julien_marseille,
        "items": items_books_marseille,
        "expected_offers": offers_books_nearest_cours_julien_marseille,
    },
]


offers_distance_pool = [
    {
        "user": user_context_111_cours_julien_marseille,
        "offers": ["offer-manga-marseille-vieux-port-1"],
        "expected_offers": [
            OfferDistance(
                offer_id="offer-manga-marseille-vieux-port-1",
                user_distance=haversine_distance(
                    iris_marseille_cours_julien.latitude,
                    iris_marseille_cours_julien.longitude,
                    iris_marseille_vieux_port.latitude,
                    iris_marseille_vieux_port.longitude,
                ),
            )
        ],
    },
    {
        "user": user_context_111_paris,
        "offers": ["offer-manga-marseille-vieux-port-1"],
        "expected_offers": [
            OfferDistance(
                offer_id="offer-manga-marseille-vieux-port-1",
                user_distance=haversine_distance(
                    iris_paris_chatelet.latitude,
                    iris_paris_chatelet.longitude,
                    iris_marseille_vieux_port.latitude,
                    iris_marseille_vieux_port.longitude,
                ),
            )
        ],
    },
]


class RecommendableOfferTest:
    @pytest.mark.parametrize(
        "pool",
        recommendable_offers_test_pool_paris + recommendable_offers_test_pool_marseille,
    )
    def test_get_recommendable_offer(self, setup_default_database: Session, pool: dict):
        user: UserContext = pool["user"]
        items: t.List[str] = pool["items"]
        items = {x: 0 for x in items}
        expected_offers: t.List[RecommendableOfferRawDB] = pool["expected_offers"]
        description = pool["description"]
        result_offers = RecommendableOfferDB().get_nearest_offers(
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
    def test_offer_distance(self, setup_default_database: Session, pool: dict):
        user: UserContext = pool["user"]
        offer_list: t.List[str] = pool["offers"]
        expected_offers: t.List[OfferDistance] = pool["expected_offers"]

        result_offers = RecommendableOfferDB().get_user_offer_distance(
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
            ) // 1000 == 0, f"Distance should be the same in KM."
