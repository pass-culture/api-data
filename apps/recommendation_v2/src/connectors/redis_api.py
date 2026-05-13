import hashlib
import json
from datetime import UTC
from datetime import datetime
from datetime import time
from datetime import timedelta
from typing import Any

from pydantic import BaseModel

from config import settings
from services.redis import redis_cache_service


class RedisAPI:
    """
    Connector responsible for generic cache operations across different API endpoints.

    It standardizes how cache keys are generated (using MD5 hashes of request parameters)
    and abstracts the retrieval and storage of Pydantic models in Redis.

    Business Rule:
    The database is repopulated every night.
    To ensure users always retrieve fresh and accurately weighted recommendations
    after the daily batch, all cached data automatically expires at the upcoming reset hour (configurable).
    """

    @staticmethod
    def calculate_seconds_until_next_database_population_time() -> int:
        """
        Calculates the time to live (TTL) in seconds until the next configured reset hour.

        This guarantees the cache memory will be completely flushed and refreshed
        daily to align with the new data ingested overnight.

        Returns:
            int: The number of seconds remaining until the next reset hour.
        """
        current_datetime = datetime.now(UTC)

        next_population_datetime = datetime.combine(
            current_datetime.date(), time(hour=settings.REDIS_CACHE_RESET_HOUR, minute=0), tzinfo=UTC
        )

        if current_datetime >= next_population_datetime:
            next_population_datetime += timedelta(days=1)

        time_difference = next_population_datetime - current_datetime

        return int(time_difference.total_seconds())

    @staticmethod
    def generate_cache_key(namespace_prefix: str, request_signature_data: dict[str, Any]) -> str:
        """
        Generates a standardized and unique cache key using an MD5 hash.

        Args:
            namespace_prefix: A string representing the domain/feature (e.g., 'playlist_recommendation').
            request_signature_data: A dictionary containing the parameters making the request unique.

        Returns:
            str: The final unique cache key.
        """
        serialized_signature = json.dumps(request_signature_data, sort_keys=True)

        signature_hash = hashlib.md5(serialized_signature.encode("utf-8")).hexdigest()

        final_cache_key = f"{namespace_prefix}:{signature_hash}"

        return final_cache_key

    @staticmethod
    async def fetch_cached_response(
        namespace_prefix: str, request_signature_data: dict[str, Any], response_model_class: type[BaseModel]
    ) -> BaseModel | None:
        """
        Checks if a cached response exists for the given signature and returns an instantiated model.

        Args:
            namespace_prefix: A string representing the domain/feature.
            request_signature_data: A dictionary containing all the unique request parameters.
            response_model_class: The Pydantic model class to instantiate with the cached data.

        Returns:
            Optional[BaseModel]: The instantiated response model if found, otherwise None.
        """
        if not settings.REDIS_CACHE_ENABLED:
            return None

        cache_key = RedisAPI.generate_cache_key(
            namespace_prefix=namespace_prefix, request_signature_data=request_signature_data
        )

        cached_data = await redis_cache_service.get_cached_value(cache_key=cache_key)

        if cached_data is not None:
            return response_model_class(**cached_data)

        return None

    @staticmethod
    async def store_endpoint_response(
        namespace_prefix: str, request_signature_data: dict[str, Any], response_model_instance: BaseModel
    ) -> None:
        """
        Serializes and stores a successful endpoint response into the Redis cache.

        Args:
            namespace_prefix: A string representing the domain/feature.
            request_signature_data: A dictionary containing all the unique request parameters.
            response_model_instance: The Pydantic response model to store.
        """
        if not settings.REDIS_CACHE_ENABLED:
            return

        cache_key = RedisAPI.generate_cache_key(
            namespace_prefix=namespace_prefix, request_signature_data=request_signature_data
        )

        serialized_payload = response_model_instance.model_dump(mode="json")

        time_to_live_in_seconds = RedisAPI.calculate_seconds_until_next_database_population_time()

        # dummy return for now
        if namespace_prefix == "similar_offer":
            return

        await redis_cache_service.set_cached_value(
            cache_key=cache_key, value_to_cache=serialized_payload, time_to_live_in_seconds=time_to_live_in_seconds
        )


redis_api = RedisAPI()
