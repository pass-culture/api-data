import asyncio
import contextlib
import inspect
import json
import traceback
from typing import Any

import redis.asyncio as redis
from config import settings
from services.logger import logger


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
        self._monitor_task: asyncio.Task | None = None

    async def _monitor_connections(self) -> None:
        """
        Background task that periodically logs the number of active clients
        connected to the Redis server.
        """
        while True:
            try:
                if self.redis_client is not None:
                    # Query Redis server for client metrics
                    info = await self.redis_client.info(section="clients")
                    connected_clients = info.get("connected_clients", "unknown")

                    logger.info(
                        "📊 Redis Monitor: active global connections", extra={"connected_clients": connected_clients}
                    )
            except Exception as e:
                logger.debug("Could not retrieve Redis connection info", extra={"error": str(e)})

            await asyncio.sleep(settings.REDIS_MONITOR_INTERVAL_SECONDS)

    async def connect(self) -> None:
        """
        Connects to the Redis instance and verifies the connection.
        Should be called during the application startup lifecycle (e.g., inside FastAPI lifespan).
        """
        if settings.REDIS_CACHE_ENABLED:
            try:
                if not settings.REDIS_URL:
                    logger.warning("REDIS_URL is empty or not set. Redis cache will be disabled.")
                    self.redis_client = None
                    settings.REDIS_CACHE_ENABLED = False
                    return

                tls_kwargs: dict = {}
                if settings.REDIS_URL.startswith("rediss://") and settings.REDIS_CA_CERT_PATH:
                    tls_kwargs = {"ssl_ca_certs": settings.REDIS_CA_CERT_PATH}
                    logger.info(
                        f"Redis TLS configuration detected. Redis URL is {settings.REDIS_URL} SSL CA path will be used"
                    )
                    logger.debug(f"Redis TLS kwargs: {tls_kwargs['ssl_ca_certs']}")
                self.redis_client = redis.Redis.from_url(
                    url=settings.REDIS_URL, password=settings.REDIS_AUTH_STRING, decode_responses=True, **tls_kwargs
                )
                if self.redis_client is not None:  # ping raises a ruff error because redis_client can be None
                    logger.debug("Attempting to connect to Redis cache and ping the server...")
                    ping_result = self.redis_client.ping()
                    if inspect.isawaitable(ping_result):  # pragma: no cover
                        await ping_result

                logger.info("Redis cache enabled and successfully connected.")

                # Start the background monitoring task
                self._monitor_task = asyncio.create_task(self._monitor_connections())

            except Exception as connection_error:
                logger.error(
                    "Failed to connect to Redis during initialization. Cache disabled.",
                    extra={"error": str(connection_error), "traceback": traceback.format_exc()},
                )
                self.redis_client = None
                settings.REDIS_CACHE_ENABLED = False

    async def disconnect(self) -> None:
        """
        Safely closes the Redis connection.
        Should be called during the application shutdown lifecycle.
        """
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitor_task
            self._monitor_task = None

        if self.redis_client is not None:
            try:
                await self.redis_client.aclose()
            except AttributeError:
                # Fallback for older redis-py versions
                with contextlib.suppress(Exception):
                    await self.redis_client.close()
            except Exception as close_error:
                logger.warning(
                    "Error while closing Redis connection",
                    extra={"error": str(close_error), "traceback": traceback.format_exc()},
                )

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

        except Exception as redis_get_error:
            logger.warning(
                "Failed to retrieve value from Redis",
                extra={"cache_key": cache_key, "error": str(redis_get_error), "traceback": traceback.format_exc()},
            )

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

        except Exception as redis_set_error:
            logger.warning(
                "Failed to store value in Redis",
                extra={"cache_key": cache_key, "error": str(redis_set_error), "traceback": traceback.format_exc()},
            )


redis_cache_service = RedisCacheService()
