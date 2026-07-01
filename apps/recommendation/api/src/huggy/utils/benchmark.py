"""
Benchmarking Utilities.

This module provides tools to measure and analyze the performance of functions and endpoints.
"""

import time
from functools import wraps

from huggy.utils.cloud_logging import logger


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

        logger.info(
            f"⏱️ [BENCHMARK] Function '{func.__name__}' executed in {execution_time:.4f} seconds.",
            extra={"function": func.__name__, "execution_time_seconds": execution_time},
        )

        return result

    return wrapper
