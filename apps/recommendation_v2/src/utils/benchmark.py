"""
Benchmarking Utilities for SQL Queries.

This module provides tools to measure and analyze the performance of database interactions.
"""

import json
import time
from functools import wraps
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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
        try:
            return await func(*args, **kwargs)
        finally:
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            logger.debug(
                f"⏱️ [BENCHMARK] Function '{func.__name__}' executed in {execution_time:.4f} seconds.",
                extra={"function": func.__name__, "execution_time_seconds": execution_time},
            )

    return wrapper


async def analyze_query_performance(
    db: AsyncSession, query_statement: Any, query_name: str = "Query Analysis"
) -> dict[str, Any] | None:
    """
    Executes a SQL query with EXPLAIN (ANALYZE, FORMAT JSON) to retrieve strict performance metrics.

    This function provides deep insights into how the database executes a query,
    including costs, buffer usage (RAM/Disk), and actual execution time.

    WARNING: This executes the query! Do not use with DELETE/UPDATE unless intended.

    Args:
        db (AsyncSession): The active database session.
        query_statement (Any): The SQLAlchemy selection statement to analyze.
        query_name (str, optional): A label for the query in the logs. Defaults to "Query Analysis".

    Returns:
        dict[str, Any] | None: A dictionary containing performance metrics (cost, ram_mb, disk_mb, exec_ms)
    """
    try:
        # Compile the query with literal parameters to ensure EXPLAIN can run it exactly as intended.
        compiled_sql = query_statement.compile(dialect=db.bind.dialect, compile_kwargs={"literal_binds": True})
        explain_stmt = text(f"EXPLAIN (ANALYZE, VERBOSE, BUFFERS, FORMAT JSON) {compiled_sql}")

        result = await db.execute(explain_stmt)
        plan_output = result.scalar()

        plan_data = json.loads(plan_output) if isinstance(plan_output, str) else plan_output
        root_node = plan_data[0]
        plan_details = root_node.get("Plan", {})

        # Extract specific metrics
        # Shared Hit Blocks: Pages found in RAM (buffer cache)
        hit_blocks = plan_details.get("Shared Hit Blocks", 0)
        # Shared Read Blocks: Pages read from Disk (OS cache or physical disk)
        read_blocks = plan_details.get("Shared Read Blocks", 0)

        metrics = {
            "query_name": query_name,
            "total_cost": plan_details.get("Total Cost", 0),
            "ram_usage_mb": (hit_blocks * 8) / 1024,  # Convert 8KB blocks to MB
            "disk_read_mb": (read_blocks * 8) / 1024,  # Convert 8KB blocks to MB
            "execution_time_ms": root_node.get("Execution Time", 0),
        }

        logger.info(
            f"📊 [EXPLAIN] {query_name}: {metrics['execution_time_ms']:.2f}ms | "
            f"Cost: {metrics['total_cost']:.2f} | "
            f"RAM: {metrics['ram_usage_mb']:.2f}MB | Disk: {metrics['disk_read_mb']:.2f}MB",
            extra={"metrics": metrics, "query_name": query_name},
        )

        return metrics

    except Exception as e:
        logger.error(f"❌ Error during EXPLAIN ANALYZE for '{query_name}': {e}")
        return None
