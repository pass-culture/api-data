from google.protobuf.json_format import MessageToDict
import pickle
import hashlib


def safe_pickle_hash(obj):
    def convert_repeated_fields(o):
        if isinstance(o, (list, tuple)):
            return [convert_repeated_fields(item) for item in o]
        if hasattr(o, "DESCRIPTOR"):
            # Protobuf message: convert to dict using MessageToDict
            try:
                return MessageToDict(o)
            except Exception:
                pass
        if hasattr(o, "__dict__"):
            obj_vars = o.__dict__.copy()
            for k, v in obj_vars.items():
                if (
                    hasattr(v, "append")
                    and hasattr(v, "__iter__")
                    and not isinstance(v, (str, bytes, dict))
                ):
                    obj_vars[k] = list(v)
                else:
                    obj_vars[k] = convert_repeated_fields(v)
            return obj_vars
        return o

    try:
        return hashlib.md5(pickle.dumps(obj)).hexdigest()
    except Exception:
        converted = convert_repeated_fields(obj)
        return hashlib.md5(pickle.dumps(converted)).hexdigest()
