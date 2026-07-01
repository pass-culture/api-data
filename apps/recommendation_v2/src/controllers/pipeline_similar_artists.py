import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.similar_artists import SimilarArtist
from schemas.similar_artists import MatchedArtist
from schemas.similar_artists import SimilarArtistsParams
from schemas.similar_artists import SimilarArtistsResponse
from services.logger import call_id_context
from services.logger import logger


async def get_similar_artists_from_db(
    db: AsyncSession,
    artist_id: str,
) -> SimilarArtistsResponse:
    # Initialization
    call_id = str(uuid.uuid4())
    call_id_context.set(call_id)

    logger.info("🚀 Starting similar_artists pipeline.", extra={"artist_id": artist_id})

    # Fetch similar artists from the database
    result = await db.execute(select(SimilarArtist.similar_artists_json).where(SimilarArtist.artist_id == artist_id))
    similar_artist_record = result.scalar_one_or_none()

    if similar_artist_record is None:
        logger.warning(
            "No similar artists found for the given artist_id.",
            extra={"artist_id": artist_id},
        )
        return SimilarArtistsResponse(
            similar_artists=[],
            params=SimilarArtistsParams(
                artist_id=artist_id,
                call_id=call_id,
            ),
        )

    similar_artists = [MatchedArtist(**item) for item in similar_artist_record]
    logger.info(
        "✅ Similar artists found.",
        extra={"artist_id": artist_id, "similar_artists_count": len(similar_artists)},
    )

    return SimilarArtistsResponse(
        similar_artists=similar_artists,
        params=SimilarArtistsParams(
            artist_id=artist_id,
            call_id=call_id,
        ),
    )
