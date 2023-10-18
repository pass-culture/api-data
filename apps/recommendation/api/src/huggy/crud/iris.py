import typing as t

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from huggy.models.iris_france import IrisFrance


class Iris:
    async def get_iris_from_coordinates(
        self,
        db: AsyncSession,
        latitude: t.Optional[float],
        longitude: t.Optional[float],
    ) -> str:
        """Query the database in ORM mode to get iris_id from a set of coordinates."""
        iris_id = None
        if latitude is not None and longitude is not None:
            point = WKTElement(f"POINT({longitude} {latitude})")
            iris_france_db: IrisFrance = (
                (
                    await db.execute(
                        select(IrisFrance).where(
                            func.ST_Contains(IrisFrance.shape, point)
                        )
                    )
                )
                .scalars()
                .first()
            )

            if iris_france_db is not None:
                return str(iris_france_db.id)
        return iris_id
