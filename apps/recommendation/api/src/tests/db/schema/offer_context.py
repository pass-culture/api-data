import typing as t

from huggy.schemas.item import RecommendableItem
from huggy.schemas.offer import OfferDistance
from huggy.utils.distance import haversine_distance

from tests.db.schema.iris import (
    IrisTestExample,
    iris_marseille_cours_julien,
    iris_marseille_vieux_port,
    iris_nok,
    iris_paris_chatelet,
)
from tests.db.schema.offer import (
    RecommendableOffersRawExample,
    book_offer_marseille_cours_julien,
    book_offer_paris,
    manga_book_offer_cours_julien_marseille,
    manga_book_offer_paris,
    manga_book_offer_vieux_port_marseille,
    movie_offer_high_price_paris,
    movie_offer_no_geolocated,
    movie_offer_paris,
    movie_offer_underage_paris,
    spectacle_offer_paris,
)


def to_items(
    offers: list[RecommendableOffersRawExample],
) -> list[RecommendableItem]:
    items: t.dict[str, RecommendableOffersRawExample] = {x.item_id: x for x in offers}

    return [
        RecommendableItem(
            item_id=v.item_id,
            item_rank=1,
            item_score=1,
            item_origin="default",
            item_cluster_id=v.item_cluster_id,
            item_topic_id=v.item_topic_id,
            is_geolocated=v.is_geolocated,
            booking_number=v.booking_number,
            booking_number_last_7_days=v.booking_number_last_7_days,
            booking_number_last_14_days=v.booking_number_last_14_days,
            booking_number_last_28_days=v.booking_number_last_28_days,
            semantic_emb_mean=v.semantic_emb_mean,
            stock_price=v.stock_price,
            category=v.category,
            subcategory_id=v.subcategory_id,
            search_group_name=v.search_group_name,
            offer_creation_date=v.offer_creation_date,
            stock_beginning_date=v.stock_beginning_date,
            gtl_id=v.gtl_id,
            gtl_l3=v.gtl_l3,
            gtl_l4=v.gtl_l4,
            total_offers=v.total_offers,
            example_offer_id=v.offer_id,
            example_venue_latitude=v.venue_latitude,
            example_venue_longitude=v.venue_longitude,
        )
        for _, v in items.items()
    ]


def to_offer_distance(
    offers: list[RecommendableOffersRawExample], iris_context: IrisTestExample
) -> list[OfferDistance]:
    offer_distances = []
    for o in offers:
        user_distance = haversine_distance(
            o.venue_latitude,
            o.venue_longitude,
            iris_context.latitude,
            iris_context.longitude,
        )
        offer_distances.append(
            OfferDistance(
                offer_id=o.offer_id,
                item_id=o.item_id,
                user_distance=user_distance,
                venue_latitude=o.venue_latitude,
                venue_longitude=o.venue_longitude,
            )
        )
    return offer_distances


offers_paris = [
    movie_offer_paris,
    movie_offer_underage_paris,
    movie_offer_high_price_paris,
    spectacle_offer_paris,
    book_offer_paris,
    manga_book_offer_paris,
]


offers_below_30_euros = [
    movie_offer_no_geolocated,
    movie_offer_paris,
    movie_offer_underage_paris,
    book_offer_paris,
    manga_book_offer_paris,
]

offers_books_paris_30_euros = [book_offer_paris, manga_book_offer_paris]

offers_underage_books_paris_30_euros = [manga_book_offer_paris]


offers_no_geolocated = [movie_offer_no_geolocated]

offers_underage_and_below_30_euros = [
    movie_offer_underage_paris,
    manga_book_offer_paris,
]

offers_books_nearest_vieux_port_marseille = [
    manga_book_offer_vieux_port_marseille,
    book_offer_marseille_cours_julien,
]
offers_books_nearest_cours_julien_marseille = [
    book_offer_marseille_cours_julien,
    manga_book_offer_cours_julien_marseille,
]

offers_paris_distance = to_offer_distance(
    offers_paris, iris_context=iris_paris_chatelet
)
offers_below_30_euros_distance = to_offer_distance(
    offers_below_30_euros, iris_context=iris_paris_chatelet
)
offers_books_paris_30_euros_distance = to_offer_distance(
    offers_books_paris_30_euros, iris_context=iris_paris_chatelet
)
offers_underage_books_paris_30_euros_distance = to_offer_distance(
    offers_underage_books_paris_30_euros, iris_context=iris_paris_chatelet
)
offers_no_geolocated_distance = to_offer_distance(
    offers_no_geolocated, iris_context=iris_nok
)
offers_underage_and_below_30_euros_distance = to_offer_distance(
    offers_underage_and_below_30_euros, iris_context=iris_nok
)
offers_books_nearest_vieux_port_marseille_distance = to_offer_distance(
    offers_books_nearest_vieux_port_marseille,
    iris_context=iris_marseille_vieux_port,
)
offers_books_nearest_cours_julien_marseille_distance = to_offer_distance(
    offers_books_nearest_cours_julien_marseille,
    iris_context=iris_marseille_cours_julien,
)

items_paris = to_items(offers_paris)
items_no_geolocated = to_items(offers_no_geolocated)
items_books_paris_below_30_euros = to_items(offers_books_paris_30_euros)
items_below_30_euros = to_items(offers_below_30_euros)
items_books_marseille = to_items(
    offers_books_nearest_vieux_port_marseille
    + offers_books_nearest_cours_julien_marseille
)


items_all = list(
    items_paris
    + items_no_geolocated
    + items_books_paris_below_30_euros
    + items_below_30_euros
    + items_books_marseille
)
