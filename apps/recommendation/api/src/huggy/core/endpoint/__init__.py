from abc import ABC
from typing import Optional

from aiocache import Cache
from aiocache.serializers import PickleSerializer
from huggy.utils.hash import hash_from_keys

VERTEX_CACHE = Cache(
    Cache.MEMORY, ttl=6000, serializer=PickleSerializer(), namespace="vertex_cache"
)


class AbstractEndpoint(ABC):  # noqa: B024
    MODEL_TYPE = "unknown"

    def __init__(
        self,
        endpoint_name: str,
        size,
        fallback_endpoints=None,
        use_cache: bool = False,  # noqa: FBT001
    ) -> None:
        """
        endpoint_name : Default endpoint
        fallback_endpoints : List of endpoints to retry in case no results or timeout error
        """
        if fallback_endpoints is None:
            fallback_endpoints = []
        self.endpoint_name = str(endpoint_name.value)
        self.size = size
        self.fallback_endpoints = [str(x.value) for x in fallback_endpoints]
        self.use_cache = use_cache
        # Theses variables will be set by the model.
        self.model_version = None
        self.model_display_name = None
        self.cached = False

    async def to_dict(self):
        return {
            "endpoint_name": self.endpoint_name,
            "size": self.size,
            "model_version": self.model_version,
            "model_display_name": self.model_display_name,
            "cached": self.cached,
            "use_cache": self.use_cache,
        }

    @staticmethod
    def _get_instance_hash(instance: dict, ignore_keys: Optional[list] = None) -> str:
        """
        Generate a hash from the instance to use as a key for caching
        """
        # drop call_id from instance
        if ignore_keys is None:
            ignore_keys = ["call_id"]
        keys = [k for k in instance if k not in ignore_keys]
        return hash_from_keys(instance, keys=keys)
