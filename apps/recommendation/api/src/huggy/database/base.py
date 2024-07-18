from abc import abstractmethod

from huggy.database.utils import check_table_exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class MaterializedBase:
    @abstractmethod
    def materialized_tables(self) -> list[Base]:
        pass

    async def get_available_table(self, session: AsyncSession) -> Base:
        table_names = []
        for obj in self.materialized_tables():
            try:
                table_name = obj.__tablename__
                table_names.append(table_name)
                if await check_table_exists(session, table_name):
                    return obj
            except NameError:
                print(f"Model {obj} is not defined")
        raise Exception(f"Tables :  {', '.join(table_names)} not found.")
