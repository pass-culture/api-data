from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.qpi_gtl_mapping import QpiGtlMapping


async def resolve_gtl_labels_from_backend_names(db: AsyncSession, backend_names: list[str]) -> list[str]:
    """
    Resolves the Titelive GTL labels associated with a list of backend names.

    Used to translate the backend names into the `gtl_label` values expected by the Vertex AI retrieval filters.

    Args:
        db (AsyncSession): The active asynchronous database session (recommendation DB).
        backend_names (list[str]): Backend names to resolve.

    Returns:
        list[str]: The distinct, resolved `gtl_label` values matching the given `backend_names`.
            Backend names with no resolved GTL label are silently skipped.
    """
    if not backend_names:
        return []

    statement = (
        select(QpiGtlMapping.gtl_label)
        .where(QpiGtlMapping.backend_name.in_(backend_name for backend_name in backend_names))
        .where(QpiGtlMapping.gtl_label.is_not(None))
        .distinct()
    )
    result = await db.execute(statement)
    return [gtl_label for (gtl_label,) in result.all()]

