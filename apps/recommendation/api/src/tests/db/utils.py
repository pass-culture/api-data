from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession


def create_db(session: AsyncSession, db_name: str):
    sql = f"""CREATE IF NOT EXISTS DATABSE {db_name} ; """
    with session as conn:
        conn.execute(text(sql))
        conn.commit()


async def create_model(session: AsyncSession, model):
    def __exec(conn):
        inspector = inspect(conn)
        if inspector.has_table(model.__tablename__):
            model.__table__.drop(conn)
            conn.commit()
        model.__table__.create(bind=conn)
        conn.commit()

    async with session.bind.connect() as connection:
        return await connection.run_sync(__exec)


async def create_table_from_df(session: AsyncSession, df, table_name: str):
    def __exec(conn):
        df.to_sql(table_name, con=conn, if_exists="replace", index=False)
        conn.commit()

    async with session.bind.connect() as connection:
        return await connection.run_sync(__exec)


async def drop_model(session: AsyncSession, model):
    def __exec(conn):
        inspector = inspect(conn)
        if inspector.has_table(model.__tablename__):
            model.__table__.drop(conn)
        conn.commit()

    async with session.bind.connect() as connection:
        return await connection.run_sync(__exec)


async def clean_db(session, models):
    def __exec(conn):
        inspector = inspect(conn)
        for model in models:
            if inspector.has_table(model.__tablename__):
                model.__table__.drop(conn)
                conn.commit()

    async with session.bind.connect() as connection:
        return await connection.run_sync(__exec)
