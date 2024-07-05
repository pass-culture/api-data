import os

from huggy.schemas.recommendable_offer import RankedOffer
from huggy.utils.mixing import order_offers_by_score_and_diversify_features
from numpy.testing import assert_array_equal

mock_scored_offers = [
    RankedOffer(
        offer_id="item_1",
        item_id="item_1",
        venue_id="123",
        user_distance=None,
        booking_number=0,
        booking_number_last_7_days=0,
        booking_number_last_14_days=0,
        booking_number_last_28_days=0,
        semantic_emb_mean=1.0,
        category="LIVRES",
        subcategory_id="LIVRE_PAPIER",
        stock_price=12.99,
        offer_creation_date=None,
        stock_beginning_date=None,
        search_group_name="LIVRES",
        gtl_id="01020500",
        gtl_l1="Littérature",
        gtl_l2="Littérature Europééne",
        gtl_l3="Policier",
        gtl_l4="Policier noir",
        venue_latitude=None,
        venue_longitude=None,
        is_geolocated=0,
        item_rank=1,
        item_score=1,
        offer_score=1,
        offer_rank=1,
        item_origin="default",
        item_cluster_id="default",
        item_topic_id="default",
        total_offers=1,
        example_offer_id="default",
        example_venue_latitude=None,
        example_venue_longitude=None,
        offer_origin="default",
    ),
    RankedOffer(
        offer_id="item_2",
        item_id="item_2",
        venue_id="123",
        user_distance=None,
        booking_number=0,
        booking_number_last_7_days=0,
        booking_number_last_14_days=0,
        booking_number_last_28_days=0,
        semantic_emb_mean=1.0,
        category="LIVRES",
        subcategory_id="LIVRE_PAPIER",
        stock_price=12.99,
        offer_creation_date=None,
        stock_beginning_date=None,
        search_group_name="LIVRES",
        gtl_id="01010000",
        gtl_l1="Droits",
        gtl_l2="Droits internationale",
        gtl_l3="Droits du travail",
        gtl_l4="Droits du travail Français",
        venue_latitude=None,
        venue_longitude=None,
        is_geolocated=0,
        item_rank=2,
        item_score=2,
        offer_score=2,
        offer_rank=2,
        item_origin="default",
        item_cluster_id="default",
        item_topic_id="default",
        total_offers=1,
        example_offer_id="default",
        example_venue_latitude=None,
        example_venue_longitude=None,
        offer_origin="default",
    ),
    RankedOffer(
        offer_id="item_3",
        item_id="item_3",
        venue_id="123",
        user_distance=None,
        booking_number=0,
        booking_number_last_7_days=0,
        booking_number_last_14_days=0,
        booking_number_last_28_days=0,
        semantic_emb_mean=1.0,
        category="LIVRE",
        subcategory_id="LIVRE_PAPIER",
        stock_price=12.99,
        offer_creation_date=None,
        stock_beginning_date=None,
        search_group_name="LIVRE",
        gtl_id="01020501",
        gtl_l1="Littérature",
        gtl_l2="Littérature Europééne",
        gtl_l3="Policier",
        gtl_l4="Policier hard boil",
        venue_latitude=None,
        venue_longitude=None,
        is_geolocated=0,
        item_rank=3,
        item_score=3,
        offer_score=3,
        offer_rank=3,
        item_origin="default",
        item_cluster_id="default",
        item_topic_id="default",
        total_offers=1,
        example_offer_id="default",
        example_venue_latitude=None,
        example_venue_longitude=None,
        offer_origin="default",
    ),
    RankedOffer(
        offer_id="item_4",
        item_id="item_4",
        venue_id="123",
        user_distance=None,
        booking_number=0,
        booking_number_last_7_days=0,
        booking_number_last_14_days=0,
        booking_number_last_28_days=0,
        semantic_emb_mean=1.0,
        category="SPECTACLE",
        subcategory_id="SPECTACLE",
        stock_price=12.99,
        offer_creation_date=None,
        stock_beginning_date=None,
        search_group_name="SPECTACLE",
        gtl_id=None,
        gtl_l1=None,
        gtl_l2=None,
        gtl_l3=None,
        gtl_l4=None,
        venue_latitude=None,
        venue_longitude=None,
        is_geolocated=0,
        item_rank=4,
        item_score=4,
        offer_score=4,
        offer_rank=4,
        item_origin="default",
        item_cluster_id="default",
        item_topic_id="default",
        total_offers=1,
        example_offer_id="default",
        example_venue_latitude=None,
        example_venue_longitude=None,
        offer_origin="default",
    ),
    RankedOffer(
        offer_id="item_5",
        item_id="item_5",
        venue_id="123",
        user_distance=None,
        booking_number=0,
        booking_number_last_7_days=0,
        booking_number_last_14_days=0,
        booking_number_last_28_days=0,
        semantic_emb_mean=1.0,
        category="CINEMA",
        subcategory_id="CINEMA",
        stock_price=12.99,
        offer_creation_date=None,
        stock_beginning_date=None,
        search_group_name="CINEMA",
        gtl_id=None,
        gtl_l1=None,
        gtl_l2=None,
        gtl_l3=None,
        gtl_l4=None,
        venue_latitude=None,
        venue_longitude=None,
        is_geolocated=0,
        item_rank=5,
        item_score=5,
        offer_score=5,
        offer_rank=5,
        item_origin="default",
        item_cluster_id="default",
        item_topic_id="default",
        total_offers=1,
        example_offer_id="default",
        example_venue_latitude=None,
        example_venue_longitude=None,
        offer_origin="default",
    ),
]
## Reminder on diversification rule
# output list is order by top score of the category, picking one in each category until reaching NbofRecommendations
mock_expected_diversification_output = [
    "item_5",
    "item_4",
    "item_3",
    "item_2",
    "item_1",
]
mock_expected_submixing_output = ["item_5", "item_4", "item_3", "item_2", "item_1"]


class DiversificationTest:
    def test_diversification(
        self,
    ):
        offers = order_offers_by_score_and_diversify_features(
            mock_scored_offers,
            score_column="offer_score",
            score_order_ascending=False,
            shuffle_recommendation=None,
            feature="subcategory_id",
            nb_reco_display=20,
        )
        ids = [x.offer_id for x in offers]
        assert_array_equal(
            mock_expected_diversification_output,
            ids,
        )

    def test_diversification_custom_submixing_feature(
        self,
    ):
        offers = order_offers_by_score_and_diversify_features(
            mock_scored_offers,
            score_column="offer_score",
            score_order_ascending=False,
            shuffle_recommendation=None,
            feature="subcategory_id",
            nb_reco_display=20,
            submixing_feature_dict={"LIVRE_PAPIER": "gtl_id", "CINEMA": "stock_price"},
        )
        ids = [x.offer_id for x in offers]
        assert_array_equal(
            mock_expected_submixing_output,
            ids,
        )
