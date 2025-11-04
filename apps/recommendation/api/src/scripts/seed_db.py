import asyncio
import logging

from huggy.database.config import config
from huggy.database.database import sessionmanager
from tests.conftest import MODELS
from tests.db import (
    create_enriched_user_mv,
    create_enriched_user_mv_old,
    create_enriched_user_mv_tmp,
    create_iris_france_mv,
    create_iris_france_mv_old,
    create_iris_france_mv_tmp,
    create_item_ids_mv,
    create_non_recommendable_items,
    create_recommendable_offers_raw,
    create_recommendable_offers_raw_mv,
    create_recommendable_offers_raw_mv_old,
    create_recommendable_offers_raw_mv_tmp,
)
from tests.db.utils import clean_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    sessionmanager.init(config.DB_CONFIG)

    async with sessionmanager.session() as session:
        logger.info("Cleaning existing database...")
        await clean_db(session, models=MODELS)

        logger.info("Creating materialized views and inserting data...")
        await create_recommendable_offers_raw(session)
        await create_recommendable_offers_raw_mv(session)
        await create_recommendable_offers_raw_mv_tmp(session)
        await create_recommendable_offers_raw_mv_old(session)
        await create_enriched_user_mv(session)
        await create_enriched_user_mv_tmp(session)
        await create_enriched_user_mv_old(session)
        await create_non_recommendable_items(session)
        await create_iris_france_mv(session)
        await create_iris_france_mv_tmp(session)
        await create_iris_france_mv_old(session)
        await create_item_ids_mv(session)
        logger.info("All tables were created and seeded successfully.")

    await sessionmanager.close()


if __name__ == "__main__":
    asyncio.run(main())
