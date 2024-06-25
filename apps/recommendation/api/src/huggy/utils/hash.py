import hashlib
from typing import Any, Dict, List, Set


def _extract_values(data: Any, keys: Set[str], values: List[str] = None) -> List[str]:
    """
    Extract values from a dictionary based on the keys.

    :param data: The dictionary to extract values from.
    :param keys: The keys to extract values for.
    :param values: The list to append the values to.
    :return: The list of values.

    """
    if values is None:
        values = []

    if isinstance(data, dict):
        for key, value in data.items():
            if key in keys:
                values.append(str(value))
            if isinstance(value, (dict, list)):
                _extract_values(value, keys, values)
    elif isinstance(data, list):
        for item in data:
            _extract_values(item, keys, values)

    return values


def hash_from_keys(data: Dict, keys: List[str] = None) -> str:
    """
    Create a hash from a dictionary based on the values of the keys.

    :param data: The dictionary to create a hash from.
    :param keys: The keys to create the hash from.
    :return: The hash.

    """
    if keys is None:
        keys = list(data.keys())
    keys_set: Set[str] = set(keys)
    values: List[str] = _extract_values(data, keys_set)

    concatenated_values: str = "".join(values)

    hash_object = hashlib.sha256(concatenated_values.encode())
    hash_hex: str = hash_object.hexdigest()

    return hash_hex
