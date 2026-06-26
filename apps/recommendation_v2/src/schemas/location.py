from typing import Self

from fastapi import Query
from pydantic import BaseModel
from pydantic import model_validator

from utils.location_presets import PresetLocation


class LocationParams(BaseModel):
    """
    Groups GPS-related query parameters and enforces that latitude and longitude
    are always provided together or not at all.
    Used as a FastAPI dependency via Depends().
    """

    latitude: float | None = Query(
        default=None,
        description="The user's GPS latitude, if provided by the mobile app.",
    )
    longitude: float | None = Query(
        default=None,
        description="The user's GPS longitude, if provided by the mobile app.",
    )
    preset_location: PresetLocation | None = Query(
        default=None,
        description="[DEV/TEST] Overrides latitude and longitude with a preset city based on population density.",
    )

    @model_validator(mode="after")
    def check_lat_lon_together(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("'latitude' and 'longitude' must be provided together or not at all.")
        return self
