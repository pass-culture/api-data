import typing as t
from datetime import datetime


def to_days(dt: datetime):
    try:
        if dt is not None:
            return (dt - datetime.now()).days
    except Exception:
        pass
    return None


def to_float(x: t.Optional[float] = None):
    try:
        if x is not None:
            return float(x)
    except Exception:
        pass
    return None


def to_int(x: t.Optional[int] = None):
    try:
        if x is not None:
            return int(x)
    except Exception:
        pass
    return None
