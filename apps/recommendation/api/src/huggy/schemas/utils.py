import json
import base64
import binascii


def parse_hex(input_str):
    try:
        return json.loads(base64.b64decode(input_str).decode("utf-8"))
    except json.JSONDecodeError as e:
        return None
    except (ValueError, binascii.Error, TypeError):
        return None


def parse_input(input_str):
    result = parse_hex(input_str)
    if result is not None:
        return result
    return None
