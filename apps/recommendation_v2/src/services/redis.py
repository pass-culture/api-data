import json
import logging
from typing import Any

import redis.asyncio as redis

from config import settings


logger = logging.getLogger(__name__)


class RedisCacheService:
    """
    Service responsible for managing interactions with the Redis cache database.

    This service abstracts the complexity of connecting to Redis and handles the
    serialization/deserialization of JSON payloads.
    """

    def __init__(self) -> None:
        """
        Initializes the Redis client connection using settings.

        If caching is disabled or the connection fails, the client is set to None.
        This acts as a failsafe, allowing the API to continue operating normally
        without cache disruption.
        """
        self.redis_client: redis.Redis | None = None

        if settings.REDIS_CACHE_ENABLED:
            try:
                self.redis_client = redis.Redis.from_url(url=settings.REDIS_URL, decode_responses=True)

                logger.info("Redis cache enabled and successfully connected.")

            except Exception as connection_error:
                logger.error(f"Failed to connect to Redis during initialization: {connection_error}")
                self.redis_client = None

    async def get_cached_value(self, cache_key: str) -> Any | None:
        """
        Retrieves a previously stored value from the Redis cache.

        Args:
            cache_key: The unique string identifier.

        Returns:
            Optional[Any]: The parsed JSON object if the key exists, otherwise None.
        """
        if self.redis_client is None:
            return None

        try:
            cached_data_string = await self.redis_client.get(name=cache_key)

            if cached_data_string is not None:
                return json.loads(cached_data_string)

        except Exception as retrieval_error:
            logger.warning(f"Failed to retrieve value from Redis for key '{cache_key}': {retrieval_error}")

        return None

    async def set_cached_value(self, cache_key: str, value_to_cache: Any, time_to_live_in_seconds: int) -> None:
        """
        Serializes and securely stores a value in the Redis cache.

        Args:
            cache_key: The string identifier used to identify the payload.
            value_to_cache: The data to be cached (must be JSON serializable).
            time_to_live_in_seconds: Specific TTL in seconds for the cache key.
        """
        if self.redis_client is None:
            return

        try:
            serialized_value = json.dumps(value_to_cache)

            await self.redis_client.set(name=cache_key, value=serialized_value, ex=time_to_live_in_seconds)

        except Exception as storage_error:
            logger.warning(f"Failed to store value in Redis for key '{cache_key}': {storage_error}")


redis_cache_service = RedisCacheService()
