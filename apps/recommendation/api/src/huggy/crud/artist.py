import json

from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from huggy.models.similar_artist import SimilarArtist
from huggy.utils.exception import log_error


class Artist:
    async def get_similar_artists_from_db(
        self,
        db: AsyncSession,
        artist_id: str,
    ) -> list[str]:
        try:
            similar_artist_table = await SimilarArtist().get_available_table(db)

            similar_artist_result = (
                await db.execute(
                    similar_artist_table.__table__.select().where(
                        similar_artist_table.artist_id == artist_id
                    )
                )
                .scalars()
                .first()
            )
            return (
                json.loads(similar_artist_result.similar_artists_json_string)
                if similar_artist_result
                else []
            )

        except ProgrammingError as exc:
            log_error(exc, message="Exception error on get_similar_artists_from_db")
            return []
