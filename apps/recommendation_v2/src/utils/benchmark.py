"""
Benchmarking Utilities for SQL Queries.

This module provides tools to measure and analyze the performance of database interactions.
"""

import time
from functools import wraps

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
