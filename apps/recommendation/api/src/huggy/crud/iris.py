from sqlalchemy import func
from sqlalchemy.orm import Session
from geoalchemy2.elements import WKTElement
import typing as t
from huggy.models.iris_france import IrisFrance


def get_iris_from_coordinates(
    db: Session,
    latitude: t.Optional[float],
    longitude: t.Optional[float],
) -> str:
    """Query the database in ORM mode to get iris_id from a set of coordinates."""
    iris_id = None
    if latitude is not None and longitude is not None:
        point = WKTElement(f"POINT({longitude} {latitude})")
        iris_france_db: IrisFrance = (
            db.query(IrisFrance)
            .filter(func.ST_Contains(IrisFrance.shape, point))
            .first()
        )
        if iris_france_db is not None:
            return str(iris_france_db.id)
    return iris_id
