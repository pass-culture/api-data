from datetime import datetime, timedelta

import pytz
from huggy.schemas.user import UserProfileDB

# all values are null
user_profile_null = UserProfileDB(
    user_id="-1",
    age=18,
    bookings_count=0,
    clicks_count=0,
    favorites_count=0,
    user_deposit_remaining_credit=300,
    found=True,
)

# not in database
user_profile_unknown = UserProfileDB(
    user_id="-111",
    age=18,
    bookings_count=0,
    clicks_count=0,
    favorites_count=0,
    user_deposit_remaining_credit=300,
    found=False,
)


user_profile_111 = UserProfileDB(
    user_id="111",
    age=18,
    bookings_count=3,
    clicks_count=1,
    favorites_count=1,
    user_deposit_remaining_credit=300,
    found=True,
)

user_profile_112 = UserProfileDB(
    user_id="112",
    age=18,
    bookings_count=1,
    clicks_count=2,
    favorites_count=2,
    user_deposit_remaining_credit=300,
    found=True,
)

user_profile_113 = UserProfileDB(
    user_id="113",
    age=18,
    bookings_count=1,
    clicks_count=2,
    favorites_count=2,
    user_deposit_remaining_credit=300,
    found=True,
)

user_profile_114 = UserProfileDB(
    user_id="114",
    age=18,
    bookings_count=3,
    clicks_count=3,
    favorites_count=3,
    user_deposit_remaining_credit=300,
    found=True,
)

user_profile_115 = UserProfileDB(
    user_id="115",
    age=15,
    bookings_count=3,
    clicks_count=3,
    favorites_count=3,
    user_deposit_remaining_credit=20,
    found=True,
)

user_profile_116 = UserProfileDB(
    user_id="116",
    age=16,
    bookings_count=4,
    clicks_count=4,
    favorites_count=4,
    user_deposit_remaining_credit=30,
    found=True,
)

user_profile_117 = UserProfileDB(
    user_id="117",
    age=17,
    bookings_count=4,
    clicks_count=4,
    favorites_count=4,
    user_deposit_remaining_credit=30,
    found=True,
)

user_profile_118 = UserProfileDB(
    user_id="118",
    age=18,
    bookings_count=4,
    clicks_count=4,
    favorites_count=4,
    user_deposit_remaining_credit=30,
    found=True,
)

# user should not have -5 years old.
user_profile_wrong_age = UserProfileDB(
    user_id="120",
    age=18,
    bookings_count=0,
    clicks_count=0,
    favorites_count=0,
    user_deposit_remaining_credit=300,
    found=True,
)


raw_data = [
    {
        "user_id": user_profile_null.user_id,
        "user_deposit_creation_date": datetime.now(pytz.utc),
        "user_birth_date": None,
        "user_deposit_initial_amount": 300,
        "user_theoretical_remaining_credit": None,
        "booking_cnt": None,
        "consult_offer": None,
        "has_added_offer_to_favorites": None,
    },
    {
        "user_id": user_profile_wrong_age.user_id,
        "user_deposit_creation_date": datetime.now(pytz.utc),
        "user_birth_date": (datetime.now() + timedelta(days=5 * 366)),
        "user_deposit_initial_amount": 300,
        "user_theoretical_remaining_credit": None,
        "booking_cnt": None,
        "consult_offer": None,
        "has_added_offer_to_favorites": None,
    },
    {
        "user_id": user_profile_111.user_id,
        "user_deposit_creation_date": datetime.now(pytz.utc),
        "user_birth_date": (
            datetime.now() - timedelta(days=user_profile_111.age * 366)
        ),
        "user_deposit_initial_amount": 300,
        "user_theoretical_remaining_credit": user_profile_111.user_deposit_remaining_credit,
        "booking_cnt": user_profile_111.bookings_count,
        "consult_offer": user_profile_111.clicks_count,
        "has_added_offer_to_favorites": user_profile_111.favorites_count,
    },
    {
        "user_id": user_profile_112.user_id,
        "user_deposit_creation_date": datetime.now(pytz.utc),
        "user_birth_date": (
            datetime.now() - timedelta(days=user_profile_112.age * 366)
        ),
        "user_deposit_initial_amount": 300,
        "user_theoretical_remaining_credit": user_profile_112.user_deposit_remaining_credit,
        "booking_cnt": user_profile_112.bookings_count,
        "consult_offer": user_profile_112.clicks_count,
        "has_added_offer_to_favorites": user_profile_112.favorites_count,
    },
    {
        "user_id": user_profile_113.user_id,
        "user_deposit_creation_date": datetime.now(pytz.utc),
        "user_birth_date": (
            datetime.now() - timedelta(days=user_profile_113.age * 366)
        ),
        "user_deposit_initial_amount": 300,
        "user_theoretical_remaining_credit": user_profile_113.user_deposit_remaining_credit,
        "booking_cnt": user_profile_113.bookings_count,
        "consult_offer": user_profile_113.clicks_count,
        "has_added_offer_to_favorites": user_profile_113.favorites_count,
    },
    {
        "user_id": user_profile_114.user_id,
        "user_deposit_creation_date": datetime.now(pytz.utc),
        "user_birth_date": (
            datetime.now() - timedelta(days=user_profile_114.age * 366)
        ),
        "user_deposit_initial_amount": 300,
        "user_theoretical_remaining_credit": user_profile_114.user_deposit_remaining_credit,
        "booking_cnt": user_profile_114.bookings_count,
        "consult_offer": user_profile_114.clicks_count,
        "has_added_offer_to_favorites": user_profile_114.favorites_count,
    },
    {
        "user_id": user_profile_115.user_id,
        "user_deposit_creation_date": datetime.now(pytz.utc),
        "user_birth_date": (
            datetime.now() - timedelta(days=user_profile_115.age * 366)
        ),
        "user_deposit_initial_amount": 20,
        "user_theoretical_remaining_credit": user_profile_115.user_deposit_remaining_credit,
        "booking_cnt": user_profile_115.bookings_count,
        "consult_offer": user_profile_115.clicks_count,
        "has_added_offer_to_favorites": user_profile_115.favorites_count,
    },
    {
        "user_id": user_profile_116.user_id,
        "user_deposit_creation_date": datetime.now(pytz.utc),
        "user_birth_date": (
            datetime.now() - timedelta(days=user_profile_116.age * 366)
        ),
        "user_deposit_initial_amount": 30,
        "user_theoretical_remaining_credit": user_profile_116.user_deposit_remaining_credit,
        "booking_cnt": user_profile_116.bookings_count,
        "consult_offer": user_profile_116.clicks_count,
        "has_added_offer_to_favorites": user_profile_116.favorites_count,
    },
    {
        "user_id": user_profile_117.user_id,
        "user_deposit_creation_date": datetime.now(pytz.utc),
        "user_birth_date": (
            datetime.now() - timedelta(days=user_profile_117.age * 366)
        ),
        "user_deposit_initial_amount": 30,
        "user_theoretical_remaining_credit": user_profile_117.user_deposit_remaining_credit,
        "booking_cnt": user_profile_117.bookings_count,
        "consult_offer": user_profile_117.clicks_count,
        "has_added_offer_to_favorites": user_profile_117.favorites_count,
    },
    {
        "user_id": user_profile_118.user_id,
        "user_deposit_creation_date": datetime.now(pytz.utc),
        "user_birth_date": (
            datetime.now() - timedelta(days=user_profile_118.age * 366)
        ),
        "user_deposit_initial_amount": 300,
        "user_theoretical_remaining_credit": user_profile_118.user_deposit_remaining_credit,
        "booking_cnt": user_profile_118.bookings_count,
        "consult_offer": user_profile_118.clicks_count,
        "has_added_offer_to_favorites": user_profile_118.favorites_count,
    },
]
