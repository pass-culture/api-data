import typing as t
from huggy.utils.hash import hash_from_keys
import pytest


@pytest.mark.parametrize(
    ["test_dict", "expected_hash"],
    [
        (
            {
                "model_type": "filter",
                "size": 1000,
                "params": {"param1": "value1", "param2": "value2", "param3": 300},
                "debug": 1,
                "vector_column_name": "booking_number_desc",
            },
            "79e886173e",
        ),
        (
            {
                "model_type": "similar_offer",
                "size": 1000,
                "params": {},
                "user_id": 12345,
                "vector_column_name": "embeddings",
            },
            "8572fd7e04",
        ),
    ],
)
def test_hash_from_keys(test_dict: t.Dict, expected_hash: str) -> None:
    _hash = hash_from_keys(test_dict, keys=["params", "model_type"])
    assert _hash[:10] == expected_hash
