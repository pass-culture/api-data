import typing as t

from geoalchemy2.elements import WKTElement
from huggy.models.iris_france import IrisFrance
from huggy.utils.cloud_logging import logger
from huggy.utils.exception import log_error
from sqlalchemy import func, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession


class Iris:
    async def get_iris_from_coordinates(
        self,
        db: AsyncSession,
        latitude: t.Optional[float],
        longitude: t.Optional[float],
    ) -> str:
        """Query the database in ORM mode to get iris_id from a set of coordinates."""
        iris_id = None
        try:
            if latitude is not None and longitude is not None:
                iris_france: IrisFrance = await IrisFrance().get_available_table(db)
                point = WKTElement(f"POINT({longitude} {latitude})", srid=0)
                iris_france_db: IrisFrance = (
                    (
                        await db.execute(
                            select(iris_france.id.label("id")).where(
                                func.ST_Contains(iris_france.shape, point)
                            )
                        )
                    )
                    .scalars()
                    .first()
                )

                if iris_france_db is not None:
                    return str(iris_france_db)
        except ProgrammingError as exc:
            log_error(exc, message="Exception error on get_iris_from_coordinates")

        return iris_id
