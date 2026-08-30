"""
Benchmarking Utilities for SQL Queries.

This module provides tools to measure and analyze the performance of database interactions.
"""

import enum
import time
from functools import wraps

from services.logger import logger


class LogLevel(enum.Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


def log_execution_time(_func=None, *, level: LogLevel = LogLevel.DEBUG):
    """
    Decorator to measure and log the execution time of an asynchronous function.

    Args:
        func (Callable): The asynchronous function to measure.
        level (LogLevel): The log level to use. Defaults to DEBUG.

    Returns:
        Callable: The wrapped function with timing logic.
    """

    def decorator(func):
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

            log_fn = getattr(logger, level.value)
            log_fn(
                f"⏱️ [BENCHMARK] Function '{func.__name__}' executed in {execution_time:.4f} seconds{cache_info}.",
                extra=extra,
            )

            return result

        return wrapper

    # Support both @log_execution_time(level=LogLevel.INFO) and @log_execution_time without parenthesis
    if _func is not None:
        return decorator(_func)
    return decorator
