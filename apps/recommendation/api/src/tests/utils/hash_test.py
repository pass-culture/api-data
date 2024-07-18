import uuid

import pytest
from huggy.utils.hash import hash_from_keys

SIMILAR_OFFER_INSTANCE = {
    "model_type": "similar_offer",
    "size": 1000,
    "params": {},
    "user_id": 12345,
    "vector_column_name": "embeddings",
    "call_id": str(uuid.uuid4()),
}
FILTER_INSTANCE = {
    "model_type": "filter",
    "size": 1000,
    "params": {"param1": "value1", "param2": "value2", "param3": 300},
    "debug": 1,
    "vector_column_name": "booking_number_desc",
    "call_id": str(uuid.uuid4()),
}


@pytest.mark.parametrize(
    ("test_dict", "columns", "expected_hash"),
    [
        (
            SIMILAR_OFFER_INSTANCE,
            ["params", "model_type"],
            "8c8984f7de180877ab6f3507115447c4",
        ),
        (
            SIMILAR_OFFER_INSTANCE,
            ["params", "model_type", "vector_column_name"],
            "5573eaa7b7c54a56bdd83538b4361613",
        ),
        (
            FILTER_INSTANCE,
            ["params", "model_type", "vector_column_name"],
            "4e43dd21082493e504e3c9812335f3e5",
        ),
    ],
)
def test_hash_from_keys(test_dict: dict, columns: list, expected_hash: str) -> None:
    print(test_dict)
    print(columns)
    _hash = hash_from_keys(test_dict, keys=columns)
    print(_hash)
    assert _hash == expected_hash
