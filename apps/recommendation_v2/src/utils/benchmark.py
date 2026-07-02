"""
Benchmarking Utilities for SQL Queries.

This module provides tools to measure and analyze the performance of database interactions.
"""

import time
from functools import wraps

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

from services.logger import logger


def log_execution_time(func):
    """
    Decorator to measure and log the execution time of an asynchronous function.

    Args:
        func (Callable): The asynchronous function to measure.

    Returns:
        Callable: The wrapped function with timing logic.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = await func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time = end_time - start_time

        from_cache = getattr(result, "from_cache", None)
        cache_info = ""
        extra: dict = {"function": func.__name__, "execution_time_seconds": execution_time}

        if from_cache is not None:
            cache_label = "CACHE HIT 🟢" if from_cache else "CACHE MISS 🔴"
            cache_info = f" | {cache_label}"
            extra["from_cache"] = from_cache

        logger.debug(
            f"⏱️ [BENCHMARK] Function '{func.__name__}' executed in {execution_time:.4f} seconds{cache_info}.",
            extra=extra,
        )

        return result

    return wrapper


def instrument_sql_query_timing(async_engine: AsyncEngine) -> None:
    """
    Registers event listeners that log the execution time of every SQL statement.

    The measured duration covers only the database round trip (statement sent,
    executed server-side, and rows fetched by the driver). It excludes the time
    spent waiting for a connection from the pool and asyncio event-loop
    scheduling delays.

    Comparing this per-statement time with the total wall time reported by
    @log_execution_time isolates where latency comes from:
    - high SQL time -> the query itself is slow (database-side problem);
    - low SQL time but high wall time -> the wait is client-side
      (pool exhaustion or CPU contention on the container).

    The pool status logged alongside ("Pool size: 15 Connections in pool: 0
    Current Overflow: 12 ...") shows whether the connection pool is saturated
    at the moment the statement runs.

    Args:
        async_engine (AsyncEngine): The engine to instrument.
    """
    sync_engine = async_engine.sync_engine

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _record_query_start(conn, cursor, statement, parameters, context, executemany):
        context._benchmark_query_start_time = time.perf_counter()

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _log_query_duration(conn, cursor, statement, parameters, context, executemany):
        start_time = getattr(context, "_benchmark_query_start_time", None)
        if start_time is None:
            return

        sql_execution_time = time.perf_counter() - start_time
        pool_status = sync_engine.pool.status()

        logger.debug(
            f"⏱️ [BENCHMARK] SQL statement executed in {sql_execution_time:.4f} seconds | pool: {pool_status}",
            extra={
                "sql_execution_time_seconds": sql_execution_time,
                "sql_statement": statement[:200],
                "pool_status": pool_status,
            },
        )
