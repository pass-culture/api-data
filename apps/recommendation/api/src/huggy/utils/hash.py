import hashlib
import pickle
from typing import Optional


def hash_from_keys(data: dict, keys: Optional[list[str]] = None) -> str:
    """
    Create a hash from a dictionary based on the values of the keys.

    :param data: The dictionary to create a hash from.
    :param keys: The keys to create the hash from.
    :return: The hash.

    """
    _dict = {k: data[k] for k in keys} if keys is not None else data.copy()
    return hashlib.md5(pickle.dumps(_dict)).hexdigest()
