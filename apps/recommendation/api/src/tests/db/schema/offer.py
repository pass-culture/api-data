import random
import typing as t
from datetime import datetime, timedelta
from uuid import uuid4

from pydantic import BaseModel, Field, validator
from tests.db.schema.iris import (
    iris_marseille_cours_julien,
    iris_marseille_vieux_port,
    iris_nok,
    iris_paris_chatelet,
)


class RecommendableOffersRawExample(BaseModel):
    item_id: str
    offer_id: str
    product_id: t.Optional[str]
    category: str
    subcategory_id: str
    search_group_name: str
    offer_type_domain: str
    offer_type_label: str
    venue_id: str
    name: str
    gtl_id: str = None
    gtl_l1: str = None
    gtl_l2: str = None
    gtl_l3: str = None
    gtl_l4: str = None
    is_numerical: bool = False
    is_national: bool = False
    is_geolocated: bool = False
    is_sensitive: bool = False
    booking_number: int = 0
    total_offers: int = 1
    offer_creation_date: datetime = datetime.now() - timedelta(days=5 * 366)
    stock_beginning_date: datetime = datetime.now() - timedelta(days=5 * 366)
    stock_price: float = 10
    is_underage_recommendable: bool = False
    venue_latitude: t.Optional[float] = None
    venue_longitude: t.Optional[float] = None
    item_topic_id: str = Field(default_factory=lambda: str(uuid4()))
    item_cluster_id: str = Field(default_factory=lambda: str(uuid4()))
    unique_id: str = Field(default_factory=lambda: str(uuid4()))
    default_max_distance: float = 50_000  # 50 KM


movie_offer_no_geolocated = RecommendableOffersRawExample(
    item_id="item-movie-1",
    offer_id="offer-movie-1",
    product_id="item-movie-1",
    category="CINEMA",
    subcategory_id="EVENEMENT_CINE",
    search_group_name="CINEMA",
    offer_type_domain="MOVIE",
    offer_type_label="BOOLYWOOD",
    venue_id="venue-movie-1",
    name="Mystère à Venise",
)

movie_offer_paris = RecommendableOffersRawExample(
    item_id="item-movie-2",
    offer_id="offer-movie-2",
    product_id="item-movie-2",
    category="CINEMA",
    subcategory_id="EVENEMENT_CINE",
    search_group_name="CINEMA",
    offer_type_domain="MOVIE",
    offer_type_label="Sci-Fi Adventure",
    venue_id="venue-movie-2",
    name="The Cosmic Quest",
    is_geolocated=True,
    booking_number=5,
    venue_latitude=iris_paris_chatelet.latitude,
    venue_longitude=iris_paris_chatelet.longitude,
)


movie_offer_underage_paris = RecommendableOffersRawExample(
    item_id="item-movie-3",
    offer_id="offer-movie-3",
    product_id="item-movie-3",
    category="CINEMA",
    subcategory_id="EVENEMENT_CINE",
    search_group_name="CINEMA",
    offer_type_domain="MOVIE",
    offer_type_label="Family Adventure",
    venue_id="venue-movie-3",
    name="The Enchanted Galaxy",
    is_geolocated=True,
    booking_number=4,
    venue_latitude=iris_paris_chatelet.latitude,
    venue_longitude=iris_paris_chatelet.longitude,
    is_underage_recommendable=True,
    offer_creation_date=datetime.strptime("2023-03-03", "%Y-%m-%d"),
    stock_beginning_date=datetime.strptime("2023-03-03", "%Y-%m-%d"),
    stock_price=12.5,
)

movie_offer_high_price_paris = RecommendableOffersRawExample(
    item_id="item-movie-4",
    offer_id="offer-movie-4",
    product_id="item-movie-4",
    category="CINEMA",
    subcategory_id="EVENEMENT_CINE",
    search_group_name="CINEMA",
    offer_type_domain="MOVIE",
    offer_type_label="Action Thriller",
    venue_id="venue-movie-4",
    name="Danger Zone",
    is_geolocated=True,
    booking_number=7,
    venue_latitude=iris_paris_chatelet.latitude,
    venue_longitude=iris_paris_chatelet.longitude,
    is_underage_recommendable=False,
    offer_creation_date=datetime.strptime("2023-04-03", "%Y-%m-%d"),
    stock_beginning_date=datetime.strptime("2023-04-03", "%Y-%m-%d"),
    stock_price=50.0,
)


spectacle_offer_paris = RecommendableOffersRawExample(
    item_id="item-spectacle-1",
    offer_id="offer-spectacle-1",
    product_id="item-spectacle-1",
    category="SPECTACLE_VIVANT",
    subcategory_id="SPECTACLE_REPRESENTATION",
    search_group_name="SPECTACLE",
    offer_type_domain="SHOW",
    offer_type_label="Magical Extravaganza",
    venue_id="venue-spectacle-1",
    name="The Enchanted Evening",
    is_geolocated=True,
    booking_number=6,
    venue_latitude=iris_paris_chatelet.latitude,
    venue_longitude=iris_paris_chatelet.longitude,
    is_underage_recommendable=False,
    offer_creation_date=datetime.strptime("2023-05-05", "%Y-%m-%d"),
    stock_beginning_date=datetime.strptime("2023-05-05", "%Y-%m-%d"),
    stock_price=45.0,
)

book_offer_paris = RecommendableOffersRawExample(
    item_id="item-book-1",
    offer_id="offer-book-1",
    product_id="item-book-1",
    category="LIVRE",
    subcategory_id="LIVRE_PAPIER",
    search_group_name="LIVRE_PAPIER",
    offer_type_domain="BOOK",
    offer_type_label="Histoire",
    venue_id="venue-book-1",
    name="L'Héritage de l'Histoire",
    is_geolocated=True,
    booking_number=2,
    venue_latitude=iris_paris_chatelet.latitude,
    venue_longitude=iris_paris_chatelet.longitude,
    is_underage_recommendable=False,
    offer_creation_date=datetime.strptime("2023-06-06", "%Y-%m-%d"),
    stock_beginning_date=datetime.strptime("2023-06-06", "%Y-%m-%d"),
    stock_price=20.0,
)


manga_book_offer_paris = RecommendableOffersRawExample(
    item_id="item-manga-1",
    offer_id="offer-manga-1",
    product_id="item-manga-1",
    category="LIVRE",
    subcategory_id="MANGA",
    search_group_name="LIVRE_MANGA",
    offer_type_domain="BOOK",
    offer_type_label="Manga",
    venue_id="venue-manga-1",
    name="Naruto: The Ninja Saga",
    is_geolocated=True,
    booking_number=2,
    venue_latitude=iris_paris_chatelet.latitude,
    venue_longitude=iris_paris_chatelet.longitude,
    is_underage_recommendable=True,
    offer_creation_date=datetime.strptime("2023-03-03", "%Y-%m-%d"),
    stock_beginning_date=datetime.strptime("2023-03-03", "%Y-%m-%d"),
    stock_price=15.0,
)

manga_book_offer_vieux_port_marseille = RecommendableOffersRawExample(
    item_id="item-manga-1",
    offer_id="offer-manga-marseille-vieux-port-1",
    product_id="item-manga-1",
    category="LIVRE",
    subcategory_id="MANGA",
    search_group_name="LIVRE_MANGA",
    offer_type_domain="BOOK",
    offer_type_label="Manga",
    venue_id="venue-marseille-1",
    name="Naruto: The Ninja Saga",
    is_geolocated=True,
    booking_number=2,
    venue_latitude=iris_marseille_vieux_port.latitude,
    venue_longitude=iris_marseille_vieux_port.longitude,
    is_underage_recommendable=True,
    offer_creation_date=datetime.strptime("2023-03-03", "%Y-%m-%d"),
    stock_beginning_date=datetime.strptime("2023-03-03", "%Y-%m-%d"),
    stock_price=15.0,
)

manga_book_offer_cours_julien_marseille = RecommendableOffersRawExample(
    item_id="item-manga-1",
    offer_id="offer-manga-marseille-cours-julien-1",
    product_id="item-manga-1",
    category="LIVRE",
    subcategory_id="MANGA",
    search_group_name="LIVRE_MANGA",
    offer_type_domain="BOOK",
    offer_type_label="Manga",
    venue_id="venue-marseille-2",
    name="Naruto: The Ninja Saga",
    is_geolocated=True,
    booking_number=2,
    venue_latitude=iris_marseille_cours_julien.latitude,
    venue_longitude=iris_marseille_cours_julien.longitude,
    is_underage_recommendable=True,
    offer_creation_date=datetime.strptime("2023-03-03", "%Y-%m-%d"),
    stock_beginning_date=datetime.strptime("2023-03-03", "%Y-%m-%d"),
    stock_price=15.0,
)

book_offer_marseille_cours_julien = RecommendableOffersRawExample(
    item_id="item-book-3",
    offer_id="offer-book-marseille-cours-julien-3",
    product_id="item-book-3",
    category="LIVRE",
    subcategory_id="LIVRE_PAPIER",
    search_group_name="LIVRE_PAPIER",
    offer_type_domain="BOOK",
    offer_type_label="Histoire",
    venue_id="venue-marseille-2",
    name="L'Histoire du Street Art",
    is_geolocated=True,
    booking_number=2,
    venue_latitude=iris_marseille_cours_julien.latitude,
    venue_longitude=iris_marseille_cours_julien.longitude,
    is_underage_recommendable=True,
    offer_creation_date=datetime.strptime("2023-06-06", "%Y-%m-%d"),
    stock_beginning_date=datetime.strptime("2023-06-06", "%Y-%m-%d"),
    stock_price=20.0,
)

data_classes = [
    movie_offer_no_geolocated,
    movie_offer_paris,
    movie_offer_underage_paris,
    movie_offer_high_price_paris,
    spectacle_offer_paris,
    book_offer_paris,
    manga_book_offer_paris,
    book_offer_marseille_cours_julien,
    manga_book_offer_cours_julien_marseille,
    manga_book_offer_vieux_port_marseille,
]


raw_data = [x.model_dump() for x in data_classes]
