import pandas as pd
from sqlalchemy import text


import logging

logger = logging.getLogger(__name__)


# CREATE EXTENSION postgis;
def create_iris_france(engine):
    iris_france = pd.read_csv("./src/tests/static/iris_france_tests.csv")
    iris_france.to_sql("iris_france", con=engine, if_exists="replace", index=False)
    sql = """
        
        ALTER TABLE public.iris_france
        ALTER COLUMN shape TYPE Geometry(GEOMETRY, 4326)
        USING ST_SetSRID(shape::Geometry, 4326);
        """

    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.close()
