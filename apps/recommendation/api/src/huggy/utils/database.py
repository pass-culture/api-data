from sqlalchemy import create_engine, engine, inspect
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.orm import Session
import typing as t
from abc import abstractmethod

from huggy.utils.env_vars import (
    SQL_BASE_USER,
    SQL_BASE_PASSWORD,
    SQL_BASE,
    SQL_HOST,
    SQL_PORT,
    API_LOCAL,
    DATA_GCP_TEST_POSTGRES_PORT,
    DB_NAME,
)


query = {}


def get_engine():
    if API_LOCAL is True:
        return create_engine(
            f"postgresql+psycopg2://postgres:postgres@localhost:{DATA_GCP_TEST_POSTGRES_PORT}/{DB_NAME}"
        )

    else:
        return create_engine(
            engine.url.URL(
                drivername="postgresql+psycopg2",
                username=SQL_BASE_USER,
                password=SQL_BASE_PASSWORD,
                database=SQL_BASE,
                host=SQL_HOST,
                port=SQL_PORT,
                query=query,
            ),
            pool_size=3,
            max_overflow=15,
            pool_timeout=30,
            pool_recycle=1800,
            client_encoding="utf8",
        )


Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


class MaterializedBase:
    @abstractmethod
    def materialized_tables(self) -> t.List[Base]:
        pass

    def get_available_table(self, session: Session) -> Base:
        engine = session.get_bind()
        table_names = []
        for obj in self.materialized_tables():
            try:
                table_name = obj.__tablename__
                table_names.append(table_name)
                if inspect(engine).has_table(table_name):
                    return obj
            except NameError:
                print(f"Model {obj} is not defined")
        raise Exception(f"Tables :  {', '.join(table_names)} not found.")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
