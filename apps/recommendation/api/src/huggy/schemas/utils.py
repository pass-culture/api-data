import base64
import binascii
import json


def parse_input(input_str):
    try:
        return json.loads(base64.b64decode(input_str).decode("utf-8"))
    except json.JSONDecodeError:
        return None
    except (ValueError, binascii.Error, TypeError):
        return None
