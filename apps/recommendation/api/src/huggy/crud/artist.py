import json

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from huggy.models.similar_artist import SimilarArtist
from huggy.utils.exception import log_error


async def get_similar_artists_from_db(
    db: AsyncSession,
    artist_id: str,
) -> list[dict]:
    try:
        model = await SimilarArtist().get_available_table(db)
        query = select(model.similar_artists_json).where(model.artist_id == artist_id)
        similar_artists = await db.scalar(query)

        return similar_artists or []

    except ProgrammingError as exc:
        log_error(exc, message="Exception error on get_similar_artists_from_db")
        return []
    except json.JSONDecodeError as exc:
        log_error(
            exc,
            message="Exception error on JSON decoding in get_similar_artists_from_db",
        )
        return []
