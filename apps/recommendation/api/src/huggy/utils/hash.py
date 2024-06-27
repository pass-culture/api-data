import hashlib
from typing import Any, List, Set
import pickle


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


def hash_from_keys(data: dict, keys: List[str] = None) -> str:
    """
    Create a hash from a dictionary based on the values of the keys.

    :param data: The dictionary to create a hash from.
    :param keys: The keys to create the hash from.
    :return: The hash.

    """
    _dict = {k: data[k] for k in keys} if keys is not None else data.copy()
    return hashlib.md5(pickle.dumps(_dict)).hexdigest()
