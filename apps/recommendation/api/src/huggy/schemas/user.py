import typing as t

from pydantic import BaseModel, field_validator
from pydantic_core.core_schema import ValidationInfo


class UserInput(BaseModel):
    """UserContext input from the API endpoint."""

    user_id: str
    longitude: float = None
    latitude: float = None


class UserProfileDB(BaseModel):
    """ORM model from the crud.enriched_user base."""

    user_id: t.Optional[str] = "-1"
    age: t.Optional[float] = 18
    bookings_count: t.Optional[int] = 0
    clicks_count: t.Optional[int] = 0
    favorites_count: t.Optional[int] = 0
    user_deposit_remaining_credit: t.Optional[float] = 300

    class Config:
        validate_assignment = True
        from_attributes = True

    @field_validator("user_deposit_remaining_credit")
    def set_user_deposit_remaining_credit(cls, var, info: ValidationInfo) -> int:
        if var is None:
            return 300
        if var < 0:
            return 300
        return var

    @field_validator("favorites_count", "bookings_count", "clicks_count")
    def set_count(cls, var, info: ValidationInfo) -> int:
        return var or 0

    @field_validator("age")
    def set_age(cls, var, info: ValidationInfo) -> int:
        if var is None:
            return 18
        if var < 0:
            return 18
        return var

    @field_validator("user_id")
    def set_user_id(cls, var, info: ValidationInfo) -> int:
        if var is None:
            return "-1"
        return var


class UserContext(UserProfileDB):
    """Characteristics of the user and the context to recommend."""

    longitude: t.Optional[float] = None
    latitude: t.Optional[float] = None
    iris_id: t.Optional[str] = None
    found: bool = False
    is_geolocated: bool = False
