import hashlib
import json
from datetime import UTC
from datetime import datetime
from datetime import time
from datetime import timedelta
from typing import Any

from pydantic import BaseModel

from config import settings
from services.logger import logger
from services.redis import redis_cache_service
from utils.benchmark import log_execution_time


class RedisAPI:
    """
    Connector responsible for all cache operations.

    Covers two caching strategies:
    - Endpoint response cache: stores full pipeline results keyed by request signature.
    - Offer resolution cache: stores per-item DB-resolved (offer_id, venue) keyed by (H3 cell, item_id),
      allowing partial cache hits and avoiding redundant spatial SQL queries for "tops" items.

    Business Rule:
    The database is repopulated every night.
    To ensure users always retrieve fresh and accurately weighted recommendations
    after the daily batch, all cached data automatically expires at the upcoming reset hour (configurable).
    """

    # ===========================================================================
    # SHARED UTILITIES
    # ===========================================================================

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

    # ===========================================================================
    # ENDPOINT RESPONSE CACHE
    # ===========================================================================

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
        if not settings.ENDPOINT_RESPONSE_CACHE_ENABLED:
            return None

        cache_key = RedisAPI.generate_cache_key(
            namespace_prefix=namespace_prefix, request_signature_data=request_signature_data
        )

        cached_data = await redis_cache_service.get_cached_value(cache_key=cache_key)

        if cached_data is not None:
            logger.debug(
                "💾 Redis cache HIT 🟢.",
                extra={"cache_key": cache_key, "namespace": namespace_prefix},
            )
            return response_model_class(**cached_data)

        logger.debug(
            "🔍 Redis cache MISS 🔴.",
            extra={"cache_key": cache_key, "namespace": namespace_prefix},
        )
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
        if not settings.ENDPOINT_RESPONSE_CACHE_ENABLED:
            return

        cache_key = RedisAPI.generate_cache_key(
            namespace_prefix=namespace_prefix, request_signature_data=request_signature_data
        )

        serialized_payload = response_model_instance.model_dump(mode="json")

        time_to_live_in_seconds = RedisAPI.calculate_seconds_until_next_database_population_time()

        await redis_cache_service.set_cached_value(
            cache_key=cache_key, value_to_cache=serialized_payload, time_to_live_in_seconds=time_to_live_in_seconds
        )

        logger.debug(
            "💾 Response stored in Redis cache.",
            extra={
                "cache_key": cache_key,
                "namespace": namespace_prefix,
                "ttl_seconds": time_to_live_in_seconds,
            },
        )

    # ===========================================================================
    # OFFER RESOLUTION CACHE
    # ===========================================================================

    _OFFER_RESOLUTION_NAMESPACE = "offer_resolution"

    @staticmethod
    def build_offer_resolution_cache_key(h3_cell: str, item_id: str) -> str:
        """
        Builds a deterministic cache key for a given (H3 cell, item_id) pair.

        Args:
            h3_cell: The H3 cell index representing the user's geographic zone.
            item_id: The item identifier.

        Returns:
            str: A cache key of the form 'offer_resolution:{h3_cell}:{item_id}'.
        """
        return f"{RedisAPI._OFFER_RESOLUTION_NAMESPACE}:{h3_cell}:{item_id}"

    @staticmethod
    @log_execution_time
    async def mget_resolved_offers(cache_keys: list[str]) -> list[dict | None]:
        """
        Fetches cached offer-resolution payloads for a batch of keys in one round-trip.

        For "tops" multi-venue items, caches the DB-resolved (offer_id, venue coordinates,
        offer dates) keyed by (H3 cell, item_id). This allows partial cache hits,
        skipping the spatial SQL query for items already resolved in the same geographic zone.

        The cached payload stores only the DB-side fields that cannot be derived from
        the Vertex AI item data:
            - offer_id, venue_latitude, venue_longitude
            - offer_creation_date, stock_beginning_date  (offer-level, may differ across venues)

        Args:
            cache_keys: Cache keys built via build_offer_resolution_cache_key.

        Returns:
            list[dict | None]: Cached payloads in the same order as cache_keys.
                               None for any key not yet cached.
        """
        return await redis_cache_service.mget_cached_values(cache_keys)

    @staticmethod
    @log_execution_time
    async def mset_resolved_offers(key_value_pairs: dict[str, dict], time_to_live_in_seconds: int) -> None:
        """
        Stores a batch of offer-resolution payloads in one Redis pipeline round-trip.

        Args:
            key_value_pairs: Mapping of cache key → offer resolution payload dict.
            time_to_live_in_seconds: TTL applied to every key (aligned with nightly reset).
        """
        await redis_cache_service.mset_cached_values(key_value_pairs, time_to_live_in_seconds)

    # ===========================================================================
    # RETRIEVAL CACHE
    # ===========================================================================

    # Namespace for the standard coreservation Vertex retrieval endpoint.
    RETRIEVAL_NAMESPACE = "retrieval"
    # Namespace for the graph Vertex retrieval endpoint — kept separate to avoid
    # collisions with coreservation results that share the same model_type values.
    RETRIEVAL_GRAPH_NAMESPACE = "retrieval_graph"

    # Payload fields that change on every call but do not influence the Vertex model output.
    # These are stripped before hashing the cache key so that two requests with the same
    # business parameters but different call_ids still produce the same cache key.
    _RETRIEVAL_CACHE_EXCLUDED_KEYS: frozenset[str] = frozenset({"call_id"})

    @staticmethod
    def build_retrieval_cache_signature(payload: dict[str, Any]) -> dict[str, Any]:
        """
        Strips volatile keys from a Vertex prediction payload before hashing.

        Volatile keys (e.g. call_id) change on every request but do not affect the model
        output. Removing them ensures that two logically identical requests — differing only
        in call_id — resolve to the same cache key and benefit from a cache hit.

        Args:
            payload: The raw Vertex prediction payload as built by the retrieval builders.

        Returns:
            dict[str, Any]: A copy of the payload with all excluded keys removed.
        """
        return {k: v for k, v in payload.items() if k not in RedisAPI._RETRIEVAL_CACHE_EXCLUDED_KEYS}

    @staticmethod
    async def fetch_cached_retrieval_predictions(
        payload: dict[str, Any],
        namespace: str = "retrieval",
    ) -> list[dict] | None:
        """
        Looks up a cached Vertex retrieval result for the given payload.

        The cache key is derived from the prediction payload after stripping volatile fields
        (call_id), so that two calls with the same business parameters but different call_ids
        resolve to the same entry.

        This method is a pure Redis operation: it does not check any feature flag.
        The caller is responsible for deciding whether the cache should be consulted
        (see ``_is_retrieval_cache_enabled_for_model_type`` in ``core.retrieval``).

        Args:
            payload:   The raw Vertex prediction payload.
            namespace: Redis key namespace. Use ``RedisAPI.RETRIEVAL_NAMESPACE`` for the
                       coreservation endpoint and ``RedisAPI.RETRIEVAL_GRAPH_NAMESPACE``
                       for the graph endpoint.

        Returns:
            list[dict] | None: A list of serialised RecommendableItem dicts on hit,
                               or None on a cache miss.
        """
        signature = RedisAPI.build_retrieval_cache_signature(payload)
        cache_key = RedisAPI.generate_cache_key(namespace, signature)

        cached_data = await redis_cache_service.get_cached_value(cache_key=cache_key)

        if cached_data is not None:
            logger.debug(
                "💾 Retrieval cache HIT 🟢.",
                extra={"cache_key": cache_key, "namespace": namespace},
            )
            return cached_data  # list[dict]

        logger.debug(
            "🔍 Retrieval cache MISS 🔴.",
            extra={"cache_key": cache_key, "namespace": namespace},
        )
        return None

    @staticmethod
    async def store_retrieval_predictions(
        payload: dict[str, Any],
        serialized_predictions: list[dict],
        namespace: str = "retrieval",
    ) -> None:
        """
        Stores the serialised Vertex retrieval predictions in Redis.

        The payload is stripped of volatile keys (call_id) before hashing the cache key,
        so that a subsequent call with a different call_id resolves to the same entry.

        This method is a pure Redis operation: it does not check any feature flag.
        The caller is responsible for deciding whether the result should be stored
        (see ``_is_retrieval_cache_enabled_for_model_type`` in ``core.retrieval``).

        Args:
            payload:                The raw Vertex prediction payload used to produce the predictions.
            serialized_predictions: The list of RecommendableItem dicts (model_dump(mode="json")).
            namespace:              Redis key namespace (RETRIEVAL_NAMESPACE or RETRIEVAL_GRAPH_NAMESPACE).
        """
        signature = RedisAPI.build_retrieval_cache_signature(payload)
        cache_key = RedisAPI.generate_cache_key(namespace, signature)

        time_to_live_in_seconds = RedisAPI.calculate_seconds_until_next_database_population_time()

        await redis_cache_service.set_cached_value(
            cache_key=cache_key,
            value_to_cache=serialized_predictions,
            time_to_live_in_seconds=time_to_live_in_seconds,
        )

        logger.debug(
            "💾 Retrieval predictions stored in cache.",
            extra={
                "cache_key": cache_key,
                "namespace": namespace,
                "predictions_count": len(serialized_predictions),
                "ttl_seconds": time_to_live_in_seconds,
            },
        )


redis_api = RedisAPI()
