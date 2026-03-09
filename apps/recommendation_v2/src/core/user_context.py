from dataclasses import dataclass
from datetime import UTC
from datetime import datetime

from models.user import EnrichedUser


# Thresholds used to determine if a user has enough history to exit the 'Cold Start' state
THRESHOLD_BOOKINGS = 2
THRESHOLD_CLICKS = 25
THRESHOLD_FAVORITES = 2

DEFAULT_FALLBACK_USER_AGE = 18


def calculate_user_age_from_birthdate(birth_date: datetime | None) -> int:
    """
    Calculates the user's current age based on their birth date.

    Args:
        birth_date (datetime | None): The user's date of birth.

    Returns:
        int: The computed age in years, or 18 by default.
    """
    if not birth_date:
        return DEFAULT_FALLBACK_USER_AGE

    try:
        today = datetime.now(UTC).date()
        user_born_date = birth_date.date()

        # Check if the user's birthday has already passed this year
        has_had_birthday_this_year = (today.month, today.day) >= (user_born_date.month, user_born_date.day)

        # Subtract 1 year if the birthday hasn't occurred yet in the current year
        age = today.year - user_born_date.year - (0 if has_had_birthday_this_year else 1)
        return age

    except Exception:
        return DEFAULT_FALLBACK_USER_AGE


@dataclass
class UserContext:
    """
    Standardizes and encapsulates user data for the recommendation pipeline.

    This object replaces the complex SQL logic from API V1 (UserContextDB.get_user_profile).
    It serves as the single source of truth for user state (authentication, geolocation,
    activity history, and ML features) during a single API request lifecycle.
    """

    user_id: str
    is_authenticated: bool = False

    # --- Ranking & ML Features ---
    age: int = DEFAULT_FALLBACK_USER_AGE
    bookings_count: int = 0
    clicks_count: int = 0  # Mapped from 'consult_offer'
    favorites_count: int = 0  # Mapped from 'has_added_offer_to_favorites'
    remaining_credit: float = 150.0  # Business logic: theoretical OR initial
    # TODO: is 150.0 the right default value here? It were 300.0 in the previous code

    # --- Geographical Context ---
    latitude: float | None = None
    longitude: float | None = None
    iris_id: str | None = None

    @property
    def is_cold_start(self) -> bool:
        """
        Determines if the user is in a 'Cold Start' scenario.

        A user is considered 'Cold Start' if they are either unauthenticated (guest)
        OR if they haven't interacted enough with the app (not enough clicks,
        favorites, or bookings) to generate meaningful collaborative filtering recommendations.

        Returns:
            bool: True if the user lacks interaction history, False otherwise (Warm user).
        """
        if not self.is_authenticated:
            return True

        has_enough_bookings = self.bookings_count >= THRESHOLD_BOOKINGS
        has_enough_clicks = self.clicks_count >= THRESHOLD_CLICKS
        has_enough_favorites = self.favorites_count >= THRESHOLD_FAVORITES

        is_warm = has_enough_bookings or has_enough_clicks or has_enough_favorites

        return not is_warm

    @property
    def is_geolocated(self) -> bool:
        """Checks if valid GPS coordinates are present in the current context."""
        return self.latitude is not None and self.longitude is not None

    @classmethod
    def build_from_database_record(
        cls,
        user_id: str,
        database_user_record: EnrichedUser | None,
        latitude: float | None = None,
        longitude: float | None = None,
        iris_id: str | None = None,
    ) -> "UserContext":
        """
        Factory method to build a UserContext from an SQLAlchemy model instance.

        Applies business rules for missing data, unauthenticated users, and
        financial credit fallbacks.

        Args:
            user_id (str): The requested user ID.
            database_user_record (EnrichedUser | None): The database record, if found.
            latitude (float | None): GPS latitude provided by the client.
            longitude (float | None): GPS longitude provided by the client.
            iris_id (str | None): The resolved geographical IRIS zone ID.

        Returns:
            UserContext: A fully initialized context object.
        """

        # --- 1. Handle Unauthenticated / Unknown Users ---
        if not database_user_record:
            return cls(
                user_id=user_id,
                is_authenticated=False,
                latitude=latitude,
                longitude=longitude,
            )

        # --- 2. Apply Credit Business Logic ---
        # Prioritize theoretical remaining credit, fallback to initial deposit, then to a default 300.0
        computed_credit = database_user_record.user_theoretical_remaining_credit

        if computed_credit is None:
            computed_credit = database_user_record.user_deposit_initial_amount

        if computed_credit is None or computed_credit < 0:
            computed_credit = 150.0

        # --- 3. Instantiate the Context ---
        return cls(
            user_id=user_id,
            is_authenticated=True,
            age=calculate_user_age_from_birthdate(database_user_record.user_birth_date),
            bookings_count=database_user_record.booking_cnt or 0,
            clicks_count=database_user_record.consult_offer or 0,
            favorites_count=database_user_record.has_added_offer_to_favorites or 0,
            remaining_credit=float(computed_credit),
            latitude=latitude,
            longitude=longitude,
            iris_id=iris_id,
        )
