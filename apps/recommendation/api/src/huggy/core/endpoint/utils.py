import typing as t
from datetime import datetime


def to_days(dt: t.Optional[datetime]) -> t.Optional[int]:
    """
    Converts a given datetime object to the number of days from the current date.

    Args:
        dt (datetime): The datetime object to be converted.

    Returns:
        int: The number of days from the current date if `dt` is valid, else None.

    Raises:
        Exception: If an error occurs during the calculation.
    """
    try:
        if dt is not None:
            return (dt - datetime.now()).days
    except Exception:
        pass
    return None


def to_float(x: t.Optional[t.Any] = None) -> t.Optional[float]:
    """
    Converts the input to a float if possible.

    Args:
        x (Any): The input value to be converted.

    Returns:
        float: The float value if conversion succeeds, else None.

    Raises:
        Exception: If the conversion fails.
    """
    try:
        if x is not None:
            return float(x)
    except Exception:
        pass
    return None


def to_int(x: t.Optional[t.Any] = None) -> t.Optional[int]:
    """
    Converts the input to an integer if possible.

    Args:
        x (Any): The input value to be converted.

    Returns:
        int: The integer value if conversion succeeds, else None.

    Raises:
        Exception: If the conversion fails.
    """
    try:
        if x is not None:
            return int(x)
    except Exception:
        pass
    return None
