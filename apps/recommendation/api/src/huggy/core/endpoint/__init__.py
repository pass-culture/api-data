from abc import ABC


class AbstractEndpoint(ABC):  # noqa: B024
    MODEL_TYPE = "unknown"

    def __init__(
        self,
        endpoint_name: str,
        size,
        fallback_endpoints=None,
        cached: bool = False,  # noqa: FBT001
    ) -> None:
        """
        endpoint_name : Default endpoint
        fallback_endpoints : list of endpoints to retry in case no results or timeout error
        """
        if fallback_endpoints is None:
            fallback_endpoints = []
        self.endpoint_name = str(endpoint_name.value)
        self.size = size
        self.fallback_endpoints = [str(x.value) for x in fallback_endpoints]
        self.model_version = None
        self.model_display_name = None
        self.cached = cached

    async def to_dict(self):
        return {
            "endpoint_name": self.endpoint_name,
            "size": self.size,
            "model_version": self.model_version,
            "model_display_name": self.model_display_name,
            "cached": self.cached,
        }
