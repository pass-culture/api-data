import os

from numpy.testing import assert_array_equal

from huggy.schemas.recommendable_offer import RankedOffer
from huggy.utils.mixing import order_offers_by_score_and_diversify_features

mock_scored_offers = [
    RankedOffer(
        offer_id="item_1",
        item_id="item_1",
        venue_id="123",
        user_distance=None,
        booking_number=0,
        category="LIVRES",
        subcategory_id="LIVRES",
        stock_price=12.99,
        offer_creation_date=None,
        stock_beginning_date=None,
        search_group_name="LIVRES",
        venue_latitude=None,
        venue_longitude=None,
        is_geolocated=0,
        item_rank=1,
        offer_score=1,
        offer_output=1,
    ),
    RankedOffer(
        offer_id="item_2",
        item_id="item_2",
        venue_id="123",
        user_distance=None,
        booking_number=0,
        category="LIVRES",
        subcategory_id="LIVRES",
        stock_price=12.99,
        offer_creation_date=None,
        stock_beginning_date=None,
        search_group_name="LIVRES",
        venue_latitude=None,
        venue_longitude=None,
        is_geolocated=0,
        item_rank=2,
        offer_score=2,
        offer_output=2,
    ),
    RankedOffer(
        offer_id="item_3",
        item_id="item_3",
        venue_id="123",
        user_distance=None,
        booking_number=0,
        category="LIVRE",
        subcategory_id="LIVRE",
        stock_price=12.99,
        offer_creation_date=None,
        stock_beginning_date=None,
        search_group_name="LIVRE",
        venue_latitude=None,
        venue_longitude=None,
        is_geolocated=0,
        item_rank=3,
        offer_score=3,
        offer_output=3,
    ),
    RankedOffer(
        offer_id="item_4",
        item_id="item_4",
        venue_id="123",
        user_distance=None,
        booking_number=0,
        category="SPECTACLE",
        subcategory_id="SPECTACLE",
        stock_price=12.99,
        offer_creation_date=None,
        stock_beginning_date=None,
        search_group_name="SPECTACLE",
        venue_latitude=None,
        venue_longitude=None,
        is_geolocated=0,
        item_rank=4,
        offer_score=4,
        offer_output=4,
    ),
    RankedOffer(
        offer_id="item_5",
        item_id="item_5",
        venue_id="123",
        user_distance=None,
        booking_number=0,
        category="CINEMA",
        subcategory_id="CINEMA",
        stock_price=12.99,
        offer_creation_date=None,
        stock_beginning_date=None,
        search_group_name="CINEMA",
        venue_latitude=None,
        venue_longitude=None,
        is_geolocated=0,
        item_rank=5,
        offer_score=5,
        offer_output=5,
    ),
]
## Reminder on diversification rule
# output list is order by top score of the category, picking one in each category until reaching NbofRecommendations
mock_expected_output = ["item_5", "item_4", "item_3", "item_2", "item_1"]


class DiversificationTest:
    def test_diversification(
        self,
    ):
        offers = order_offers_by_score_and_diversify_features(
            mock_scored_offers,
            score_column="item_rank",
            score_order_ascending=False,
            shuffle_recommendation=None,
            feature="subcategory_id",
            nb_reco_display=20,
        )
        ids = [x.offer_id for x in offers]
        assert_array_equal(
            mock_expected_output,
            ids,
        )
