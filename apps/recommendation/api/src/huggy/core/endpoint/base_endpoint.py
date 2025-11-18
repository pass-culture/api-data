from typing import Optional

from huggy.utils.hash import hash_from_keys


class BaseEndpoint:
    def __init__(
        self,
        endpoint_name: str,
        size,
        fallback_endpoints=None,
        *,
        use_cache: bool = False,
    ) -> None:
        """
        endpoint_name : Default endpoint
        fallback_endpoints : List of endpoints to retry in case no results or timeout error
        """
        if fallback_endpoints is None:
            fallback_endpoints = []
        self.endpoint_name = str(endpoint_name)
        self.size = size
        self.fallback_endpoints = [str(x) for x in fallback_endpoints]
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
