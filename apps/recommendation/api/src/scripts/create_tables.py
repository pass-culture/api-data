import asyncio
import logging

from huggy.database.base import Base
from huggy.database.config import config
from huggy.database.database import sessionmanager
from huggy.models.enriched_user import (
    EnrichedUserMv,
    EnrichedUserMvOld,
    EnrichedUserMvTmp,
)
from huggy.models.iris_france import (
    IrisFranceMv,
    IrisFranceMvOld,
    IrisFranceMvTmp,
)
from huggy.models.item_ids import ItemIdsMv, ItemIdsMvOld, ItemIdsMvTmp
from huggy.models.non_recommendable_items import (
    NonRecommendableItemsMv,
    NonRecommendableItemsMvTmp,
    NonRecommendableItemsMvTmpOld,
)
from huggy.models.past_recommended_offers import PastOfferContext
from huggy.models.recommendable_offers_raw import (
    RecommendableOffersRawMv,
    RecommendableOffersRawMvOld,
    RecommendableOffersRawMvTmp,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODELS_TO_CREATE = [
    EnrichedUserMv,
    EnrichedUserMvOld,
    EnrichedUserMvTmp,
    IrisFranceMv,
    IrisFranceMvOld,
    IrisFranceMvTmp,
    ItemIdsMv,
    ItemIdsMvOld,
    ItemIdsMvTmp,
    NonRecommendableItemsMv,
    NonRecommendableItemsMvTmp,
    NonRecommendableItemsMvTmpOld,
    PastOfferContext,
    RecommendableOffersRawMv,
    RecommendableOffersRawMvOld,
    RecommendableOffersRawMvTmp,
]


async def main():
    sessionmanager.init(config.DB_CONFIG)

    tables_to_create = [model.__table__ for model in MODELS_TO_CREATE]
    async with sessionmanager._engine.begin() as conn:
        logger.info(f"Creating {len(tables_to_create)} tables explicitly...")
        await conn.run_sync(Base.metadata.create_all, tables=tables_to_create)
        logger.info("Schema created successfully.")

    await sessionmanager.close()


if __name__ == "__main__":
    asyncio.run(main())
