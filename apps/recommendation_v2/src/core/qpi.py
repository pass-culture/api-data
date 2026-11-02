from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.qpi_gtl_mapping import QpiGtlMapping


async def resolve_gtl_ids_from_ux_names(db: AsyncSession, ux_names: list[str]) -> list[str]:
    """
    Resolves the Titelive GTL identifiers associated with a list of QPI UX category names.

    Used to translate the UX category names selected by the user during the QPI
    (Quiz de Préférences Initial) onboarding flow (e.g. "Mangas ou BD", "Romance")
    into the `gtl_id` values expected by the Vertex AI retrieval filters.

    Args:
        db (AsyncSession): The active asynchronous database session (recommendation DB).
        ux_names (list[str]): UX category names to resolve.

    Returns:
        list[str]: The distinct, resolved `gtl_id` values matching the given `ux_names`.
            UX names with no resolved GTL id are silently skipped.
    """
    if not ux_names:
        return []

    statement = (
        select(QpiGtlMapping.gtl_id)
        .where(QpiGtlMapping.ux_name.in_(ux_names))
        .where(QpiGtlMapping.gtl_id.is_not(None))
        .distinct()
    )
    result = await db.execute(statement)
    return [gtl_id for (gtl_id,) in result.all()]
