import typing as t

from huggy.schemas.recommendable_offer import RecommendableOfferRawDB
from tests.db.schema.iris import (
    iris_marseille_cours_julien,
    iris_marseille_vieux_port,
    iris_nok,
    iris_paris_chatelet,
)
from tests.db.schema.offer import (
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


def to_items(offers: RecommendableOfferRawDB) -> t.List[str]:
    return list(set([x.item_id for x in offers]))


offers_paris = [
    movie_offer_paris.to_context(iris_context=iris_paris_chatelet),
    movie_offer_underage_paris.to_context(iris_context=iris_paris_chatelet),
    movie_offer_high_price_paris.to_context(iris_context=iris_paris_chatelet),
    spectacle_offer_paris.to_context(iris_context=iris_paris_chatelet),
    book_offer_paris.to_context(iris_context=iris_paris_chatelet),
    manga_book_offer_paris.to_context(iris_context=iris_paris_chatelet),
]

offers_below_30_euros = [
    movie_offer_no_geolocated.to_context(iris_context=iris_paris_chatelet),
    movie_offer_paris.to_context(iris_context=iris_paris_chatelet),
    movie_offer_underage_paris.to_context(iris_context=iris_paris_chatelet),
    book_offer_paris.to_context(iris_context=iris_paris_chatelet),
    manga_book_offer_paris.to_context(iris_context=iris_paris_chatelet),
]

offers_books_paris_30_euros = [
    book_offer_paris.to_context(iris_context=iris_paris_chatelet),
    manga_book_offer_paris.to_context(iris_context=iris_paris_chatelet),
]

offers_underage_books_paris_30_euros = [
    manga_book_offer_paris.to_context(iris_context=iris_paris_chatelet),
]


offers_no_geolocated = [
    movie_offer_no_geolocated.to_context(iris_context=iris_nok),
]

offers_underage_and_below_30_euros = [
    movie_offer_underage_paris.to_context(iris_context=iris_paris_chatelet),
    manga_book_offer_paris.to_context(iris_context=iris_paris_chatelet),
]

offers_books_nearest_vieux_port_marseille = [
    manga_book_offer_vieux_port_marseille.to_context(
        iris_context=iris_marseille_vieux_port
    ),
    book_offer_marseille_cours_julien.to_context(
        iris_context=iris_marseille_vieux_port
    ),
]
offers_books_nearest_cours_julien_marseille = [
    book_offer_marseille_cours_julien.to_context(
        iris_context=iris_marseille_cours_julien
    ),
    manga_book_offer_cours_julien_marseille.to_context(
        iris_context=iris_marseille_cours_julien
    ),
]

items_paris = to_items(offers_paris)
items_no_geolocated = to_items(offers_no_geolocated)
items_books_paris_below_30_euros = to_items(offers_books_paris_30_euros)
items_below_30_euros = to_items(offers_below_30_euros)
items_books_marseille = to_items(
    offers_books_nearest_vieux_port_marseille
    + offers_books_nearest_cours_julien_marseille
)


items_all = list(
    set(
        items_paris
        + items_no_geolocated
        + items_books_paris_below_30_euros
        + items_below_30_euros
        + items_books_marseille
    )
)
