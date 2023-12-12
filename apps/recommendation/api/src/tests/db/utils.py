from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession


async def drop_restore_db(session, db_name: str):
    drop_sql = f"""DROP DATABASE IF EXISTS {db_name} ; """
    create_sql = f"""CREATE DATABSE {db_name} ;"""
    async with session.bind.connect() as connection:
        await connection.execute(text(drop_sql))
        await connection.execute(text(create_sql))


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
