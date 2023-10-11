from datetime import datetime, timedelta
import os
import pytest

import pandas as pd
import pytz
from sqlalchemy import create_engine, text, inspect, insert
from sqlalchemy.orm import sessionmaker, Session
from typing import Any, Dict

from huggy.models.non_recommendable_items import NonRecommendableItems
from huggy.models.recommendable_offers_raw import RecommendableOffersRawMv
from huggy.models.enriched_user import EnrichedUserMv
from huggy.models.item_ids_mv import ItemIdsMv
from huggy.utils.env_vars import DATA_GCP_TEST_POSTGRES_PORT

import logging

logger = logging.getLogger(__name__)

DB_NAME = os.getenv("DB_NAME", "postgres")
DEFAULT_IRIS_ID = "45327"

TEST_DATABASE_CONFIG = {
    "user": "postgres",
    "password": "postgres",
    "host": "0.0.0.0",
    "port": DATA_GCP_TEST_POSTGRES_PORT,
    "database": DB_NAME,
}


@pytest.fixture
def app_config() -> Dict[str, Any]:
    return {
        "NUMBER_OF_RECOMMENDATIONS": 10,
        "MODEL_REGION": "model_region",
    }


def create_non_recommendable_items(engine):
    if inspect(engine).has_table(NonRecommendableItems.__tablename__):
        NonRecommendableItems.__table__.drop(engine)
    NonRecommendableItems.__table__.create(bind=engine)

    with engine.connect() as conn:
        conn.execute(
            insert(NonRecommendableItems),
            [
                {"user_id": "111", "item_id": "isbn-1"},
                {"user_id": "112", "item_id": "isbn-3"},
            ],
        )
        conn.commit()
        conn.close()


def create_recommendable_offers_raw(engine):
    data = [
        {
            "item_id": "isbn-1",
            "offer_id": "1",
            "product_id": "1",
            "category": "A",
            "subcategory_id": "EVENEMENT_CINE",
            "search_group_name": "CINEMA",
            "offer_type_domain": "MOVIE",
            "offer_type_label": "BOOLYWOOD",
            "venue_id": "11",
            "name": "a",
            "is_numerical": False,
            "is_national": True,
            "is_geolocated": False,
            "booking_number": 3,
            "offer_creation_date": "2020-01-01",
            "stock_creation_date": "2020-01-01",
            "stock_price": 10,
            "is_underage_recommendable": False,
            "venue_latitude": None,
            "venue_longitude": None,
            "unique_id": 1,
            "default_max_distance": 100000,
        },
        {
            "item_id": "isbn-2",
            "offer_id": "2",
            "product_id": "2",
            "category": "B",
            "subcategory_id": "EVENEMENT_CINE",
            "search_group_name": "CINEMA",
            "offer_type_domain": "MOVIE",
            "offer_type_label": "BOOLYWOOD",
            "venue_id": "22",
            "name": "b",
            "is_numerical": False,
            "is_national": False,
            "is_geolocated": True,
            "booking_number": 5,
            "offer_creation_date": "2020-01-01",
            "stock_creation_date": "2020-01-01",
            "stock_price": 20,
            "is_underage_recommendable": True,
            "venue_latitude": 48.87004,
            "venue_longitude": 2.3785,
            "unique_id": 2,
            "default_max_distance": 100000,
        },
        {
            "item_id": "movie-3",
            "offer_id": "3",
            "product_id": "3",
            "category": "C",
            "subcategory_id": "EVENEMENT_CINE",
            "search_group_name": "CINEMA",
            "offer_type_domain": "MOVIE",
            "offer_type_label": "BOOLYWOOD",
            "venue_id": "33",
            "name": "c",
            "is_numerical": True,
            "is_national": True,
            "is_geolocated": False,
            "booking_number": 10,
            "offer_creation_date": "2020-01-01",
            "stock_creation_date": "2020-01-01",
            "stock_price": 20,
            "is_underage_recommendable": True,
            "venue_latitude": None,
            "venue_longitude": None,
            "unique_id": 3,
            "default_max_distance": 100000,
        },
        {
            "item_id": "movie-4",
            "offer_id": "4",
            "product_id": "4",
            "category": "D",
            "subcategory_id": "EVENEMENT_CINE",
            "search_group_name": "CINEMA",
            "offer_type_domain": "MOVIE",
            "offer_type_label": "BOOLYWOOD",
            "venue_id": "44",
            "name": "d",
            "is_numerical": True,
            "is_national": True,
            "is_geolocated": False,
            "booking_number": 2,
            "offer_creation_date": "2020-01-01",
            "stock_creation_date": "2020-01-01",
            "stock_price": 30,
            "is_underage_recommendable": False,
            "venue_latitude": None,
            "venue_longitude": None,
            "unique_id": 4,
            "default_max_distance": 100000,
        },
        {
            "item_id": "movie-5",
            "offer_id": "5",
            "product_id": "5",
            "category": "E",
            "subcategory_id": "SPECTACLE_REPRESENTATION",
            "search_group_name": "SPECTACLE",
            "offer_type_domain": "SHOW",
            "offer_type_label": "Cirque",
            "venue_id": "55",
            "name": "e",
            "is_numerical": False,
            "is_national": True,
            "is_geolocated": False,
            "booking_number": 1,
            "offer_creation_date": "2020-01-01",
            "stock_creation_date": "2020-01-01",
            "stock_price": 30,
            "is_underage_recommendable": False,
            "venue_latitude": None,
            "venue_longitude": None,
            "unique_id": 5,
            "default_max_distance": 100000,
        },
        {
            "item_id": "product-6",
            "offer_id": "6",
            "product_id": "6",
            "category": "B",
            "subcategory_id": "SPECTACLE_REPRESENTATION",
            "search_group_name": "SPECTACLE",
            "offer_type_domain": "SHOW",
            "offer_type_label": "Cirque",
            "venue_id": "22",
            "name": "f",
            "is_numerical": False,
            "is_national": False,
            "is_geolocated": True,
            "booking_number": 9,
            "offer_creation_date": "2020-01-01",
            "stock_creation_date": "2020-01-01",
            "stock_price": 30,
            "is_underage_recommendable": False,
            "venue_latitude": 48.87004,
            "venue_longitude": 2.3785,
            "unique_id": 6,
            "default_max_distance": 100000,
        },
        {
            "item_id": "product-7",
            "offer_id": "7",
            "product_id": "7",
            "category": "A",
            "subcategory_id": "SPECTACLE_REPRESENTATION",
            "search_group_name": "SPECTACLE",
            "offer_type_domain": "SHOW",
            "offer_type_label": "Cirque",
            "venue_id": "22",
            "name": "g",
            "is_numerical": False,
            "is_national": False,
            "is_geolocated": True,
            "booking_number": 5,
            "offer_creation_date": "2020-01-01",
            "stock_creation_date": "2020-01-01",
            "stock_price": 30,
            "is_underage_recommendable": False,
            "venue_latitude": 48.830719,
            "venue_longitude": 2.331289,
            "unique_id": 7,
            "default_max_distance": 100000,
        },
        {
            "item_id": "product-8",
            "offer_id": "8",
            "product_id": "8",
            "category": "A",
            "subcategory_id": "EVENEMENT_CINE",
            "search_group_name": "CINEMA",
            "offer_type_domain": "MOVIE",
            "offer_type_label": "COMEDY",
            "venue_id": "22",
            "name": "h",
            "is_numerical": False,
            "is_national": False,
            "is_geolocated": False,
            "booking_number": 5,
            "offer_creation_date": "2020-01-01",
            "stock_creation_date": "2020-01-01",
            "stock_price": 30,
            "is_underage_recommendable": False,
            "venue_latitude": 48.830719,
            "venue_longitude": 2.331289,
            "unique_id": 8,
            "default_max_distance": 100000,
        },
        {
            "item_id": "product-9",
            "offer_id": "9",
            "product_id": "9",
            "category": "D",
            "subcategory_id": "LIVRE_PAPIER",
            "search_group_name": "LIVRE_PAPIER",
            "offer_type_domain": "BOOK",
            "offer_type_label": "Histoire",
            "venue_id": "23",
            "name": "i",
            "is_numerical": False,
            "is_national": True,
            "is_geolocated": False,
            "booking_number": 10,
            "offer_creation_date": "2020-01-01",
            "stock_creation_date": "2020-01-01",
            "stock_price": 10,
            "is_underage_recommendable": True,
            "venue_latitude": None,
            "venue_longitude": None,
            "unique_id": 9,
            "default_max_distance": 100000,
        },
    ]

    if inspect(engine).has_table(RecommendableOffersRawMv.__tablename__):
        RecommendableOffersRawMv.__table__.drop(engine)
    RecommendableOffersRawMv.__table__.create(bind=engine)

    with engine.connect() as conn:
        conn.execute(insert(RecommendableOffersRawMv), data)
        conn.commit()
        conn.close()


def create_enriched_user(engine):
    data = [
        {
            "user_id": "111",
            "user_deposit_creation_date": datetime.now(pytz.utc),
            "user_birth_date": (datetime.now() - timedelta(days=18 * 366)),
            "user_deposit_initial_amount": 300,
            "user_theoretical_remaining_credit": 300,
            "booking_cnt": 3,
            "consult_offer": 1,
            "has_added_offer_to_favorites": 1,
        },
        {
            "user_id": "112",
            "user_deposit_creation_date": datetime.now(pytz.utc),
            "user_birth_date": (datetime.now() - timedelta(days=18 * 366)),
            "user_deposit_initial_amount": 300,
            "user_theoretical_remaining_credit": 300,
            "booking_cnt": 1,
            "consult_offer": 2,
            "has_added_offer_to_favorites": 2,
        },
        {
            "user_id": "113",
            "user_deposit_creation_date": datetime.now(pytz.utc),
            "user_birth_date": (datetime.now() - timedelta(days=18 * 366)),
            "user_deposit_initial_amount": 300,
            "user_theoretical_remaining_credit": 300,
            "booking_cnt": 1,
            "consult_offer": 2,
            "has_added_offer_to_favorites": 2,
        },
        {
            "user_id": "114",
            "user_deposit_creation_date": datetime.now(pytz.utc),
            "user_birth_date": (datetime.now() - timedelta(days=18 * 366)),
            "user_deposit_initial_amount": 300,
            "user_theoretical_remaining_credit": 300,
            "booking_cnt": 3,
            "consult_offer": 3,
            "has_added_offer_to_favorites": 3,
        },
        {
            "user_id": "115",
            "user_deposit_creation_date": datetime.now(pytz.utc),
            "user_birth_date": (datetime.now() - timedelta(days=15 * 366)),
            "user_deposit_initial_amount": 20,
            "user_theoretical_remaining_credit": 20,
            "booking_cnt": 3,
            "consult_offer": 3,
            "has_added_offer_to_favorites": 3,
        },
        {
            "user_id": "116",
            "user_deposit_creation_date": datetime.now(pytz.utc),
            "user_birth_date": (datetime.now() - timedelta(days=16 * 366)),
            "user_deposit_initial_amount": 30,
            "user_theoretical_remaining_credit": 30,
            "booking_cnt": 4,
            "consult_offer": 4,
            "has_added_offer_to_favorites": 4,
        },
        {
            "user_id": "117",
            "user_deposit_creation_date": datetime.now(pytz.utc),
            "user_birth_date": (datetime.now() - timedelta(days=17 * 366)),
            "user_deposit_initial_amount": 30,
            "user_theoretical_remaining_credit": 30,
            "booking_cnt": 4,
            "consult_offer": 4,
            "has_added_offer_to_favorites": 4,
        },
        {
            "user_id": "118",
            "user_deposit_creation_date": datetime.now(pytz.utc),
            "user_birth_date": (datetime.now() - timedelta(days=18 * 366)),
            "user_deposit_initial_amount": 300,
            "user_theoretical_remaining_credit": 300,
            "booking_cnt": 4,
            "consult_offer": 4,
            "has_added_offer_to_favorites": 4,
        },
    ]
    if inspect(engine).has_table(EnrichedUserMv.__tablename__):
        EnrichedUserMv.__table__.drop(engine)
    EnrichedUserMv.__table__.create(bind=engine)

    with engine.connect() as conn:
        conn.execute(insert(EnrichedUserMv), data)
        conn.commit()
        conn.close()


def create_qpi_answers_mv(engine):
    qpi_answers = pd.DataFrame(
        {
            "user_id": ["111", "111", "112", "113", "114"],
            "subcategories": [
                "SUPPORT_PHYSIQUE_FILM",
                "JEU_EN_LIGNE",
                "SUPPORT_PHYSIQUE_FILM",
                "LIVRE_PAPIER",
                "LIVRE_PAPIER",
            ],
            "catch_up_user_id": [None, None, None, None, None],
        }
    )
    qpi_answers.to_sql("qpi_answers_mv", con=engine, if_exists="replace")


def create_past_recommended_offers(engine):
    past_recommended_offers = pd.DataFrame(
        {
            "userid": [1],
            "offerid": [1],
            "date": [datetime.now(pytz.utc)],
            "reco_origin": "algo",
        }
    )
    past_recommended_offers.to_sql(
        "past_recommended_offers", con=engine, if_exists="replace"
    )


def create_iris_france(engine):
    iris_france = pd.read_csv("./src/tests/iris_france_tests.csv")
    iris_france.to_sql("iris_france", con=engine, if_exists="replace", index=False)
    sql = """ALTER TABLE public.iris_france
            ALTER COLUMN shape TYPE Geometry(GEOMETRY, 4326)
            USING ST_SetSRID(shape::Geometry, 4326);
        """

    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.close()


def create_item_ids_mv(engine):
    data = [
        {
            "item_id": "isbn-1",
            "offer_id": "1",
            "booking_number": 3,
        },
        {
            "item_id": "isbn-2",
            "offer_id": "2",
            "booking_number": 5,
        },
        {
            "item_id": "movie-3",
            "offer_id": "3",
            "booking_number": 10,
        },
        {
            "item_id": "movie-4",
            "offer_id": "4",
            "booking_number": 2,
        },
        {
            "item_id": "movie-5",
            "offer_id": "5",
            "booking_number": 1,
        },
        {
            "item_id": "product-6",
            "offer_id": "6",
            "booking_number": 9,
        },
        {
            "item_id": "product-7",
            "offer_id": "7",
            "booking_number": 5,
        },
        {
            "item_id": "product-8",
            "offer_id": "8",
            "booking_number": 5,
        },
        {
            "item_id": "product-9",
            "offer_id": "9",
            "booking_number": 10,
        },
    ]

    if inspect(engine).has_table(ItemIdsMv.__tablename__):
        ItemIdsMv.__table__.drop(engine)
    ItemIdsMv.__table__.create(bind=engine)

    with engine.connect() as conn:
        conn.execute(insert(ItemIdsMv), data)
        conn.commit()
        conn.close()


def get_engine():
    return create_engine(
        f"postgresql+psycopg2://postgres:postgres@127.0.0.1:{DATA_GCP_TEST_POSTGRES_PORT}/{DB_NAME}"
    )


@pytest.fixture
def setup_database(app_config: Dict[str, Any]) -> Session:
    engine = get_engine()
    try:
        from huggy.utils.database import Base

        Base.metadata.drop_all(engine)
    except:
        pass

    create_recommendable_offers_raw(engine)
    create_non_recommendable_items(engine)
    create_enriched_user(engine)
    create_qpi_answers_mv(engine)
    create_past_recommended_offers(engine)
    create_iris_france(engine)
    create_item_ids_mv(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
