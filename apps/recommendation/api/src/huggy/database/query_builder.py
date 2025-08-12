from typing import Any, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select


class QueryBuilder:
    """A fluent query builder for complex SQLAlchemy queries"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._query: Optional[Select] = None
        self._subqueries = {}

    def select(self, *columns) -> "QueryBuilder":
        """Start a new select query"""
        self._query = select(*columns)
        return self

    def from_table(self, table) -> "QueryBuilder":
        """Set the FROM clause"""
        if self._query is None:
            self._query = select().select_from(table)
        else:
            self._query = self._query.select_from(table)
        return self

    def join(self, table, condition=None) -> "QueryBuilder":
        """Add a JOIN clause"""
        if condition is None:
            self._query = self._query.join(table)
        else:
            self._query = self._query.join(table, condition)
        return self

    def left_join(self, table, condition) -> "QueryBuilder":
        """Add a LEFT JOIN clause"""
        self._query = self._query.outerjoin(table, condition)
        return self

    def where(self, *conditions) -> "QueryBuilder":
        """Add WHERE conditions"""
        if len(conditions) == 1:
            self._query = self._query.where(conditions[0])
        else:
            self._query = self._query.where(and_(*conditions))
        return self

    def order_by(self, *columns) -> "QueryBuilder":
        """Add ORDER BY clause"""
        self._query = self._query.order_by(*columns)
        return self

    def group_by(self, *columns) -> "QueryBuilder":
        """Add GROUP BY clause"""
        self._query = self._query.group_by(*columns)
        return self

    def having(self, condition) -> "QueryBuilder":
        """Add HAVING clause"""
        self._query = self._query.having(condition)
        return self

    def limit(self, count: int) -> "QueryBuilder":
        """Add LIMIT clause"""
        self._query = self._query.limit(count)
        return self

    def offset(self, count: int) -> "QueryBuilder":
        """Add OFFSET clause"""
        self._query = self._query.offset(count)
        return self

    def subquery(self, name: str) -> "QueryBuilder":
        """Convert current query to a subquery and store it"""
        if self._query is None:
            raise ValueError("No query to convert to subquery")
        self._subqueries[name] = self._query.subquery(name=name)
        return self

    def get_subquery(self, name: str):
        """Get a previously created subquery"""
        return self._subqueries.get(name)

    def window_function(self, func_expr, partition_by=None, order_by=None):
        """Add a window function"""
        window_expr = func_expr
        if partition_by is not None or order_by is not None:
            window_expr = window_expr.over(partition_by=partition_by, order_by=order_by)
        return window_expr

    def row_number(self, partition_by=None, order_by=None, label: str = "row_number"):
        """Add ROW_NUMBER() window function"""
        return (
            func.row_number()
            .over(partition_by=partition_by, order_by=order_by)
            .label(label)
        )

    async def execute(self):
        """Execute the query"""
        if self._query is None:
            raise ValueError("No query to execute")
        result = await self.session.execute(self._query)
        return result

    async def fetch_all(self):
        """Execute and fetch all results"""
        result = await self.execute()
        return result.fetchall()

    async def fetch_one(self):
        """Execute and fetch one result"""
        result = await self.execute()
        return result.fetchone()

    async def scalar(self):
        """Execute and return scalar result"""
        result = await self.execute()
        return result.scalar()

    def build(self) -> Select:
        """Return the built query without executing"""
        if self._query is None:
            raise ValueError("No query to build")
        return self._query


class GeospatialQueryBuilder(QueryBuilder):
    """Extended query builder with geospatial functions"""

    def st_distance(self, geom1, geom2, use_spheroid: bool = True) -> Any:
        """Calculate distance between two geometries"""
        if use_spheroid:
            return func.ST_Distance(geom1, geom2, True).label("distance")
        return func.ST_Distance(geom1, geom2).label("distance")

    def st_dwithin(self, geom1, geom2, distance: float) -> Any:
        """Check if geometries are within distance"""
        return func.ST_DWithin(geom1, geom2, distance)

    def st_point(self, longitude: float, latitude: float, srid: int = 4326) -> Any:
        """Create a point geometry"""
        return func.ST_SetSRID(func.ST_Point(longitude, latitude), srid)

    def add_distance_filter(
        self, geom_column, user_point, max_distance: float
    ) -> "GeospatialQueryBuilder":
        """Add a distance-based filter"""
        distance_condition = func.ST_DWithin(geom_column, user_point, max_distance)
        return self.where(distance_condition)
