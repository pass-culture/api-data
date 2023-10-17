import logging

import pandas as pd
from sqlalchemy import text

from tests.db.utils import create_table_from_df

logger = logging.getLogger(__name__)


async def create_iris_france(session):
    iris_france = pd.read_csv("./src/tests/static/iris_france_tests.csv")
    await create_table_from_df(session, iris_france, "iris_france")
    sql = """
        
        ALTER TABLE public.iris_france
        ALTER COLUMN shape TYPE Geometry(GEOMETRY, 4326)
        USING ST_SetSRID(shape::Geometry, 4326);
        """

    async with session.bind.connect() as conn:
        await conn.execute(text(sql))
        await conn.close()
