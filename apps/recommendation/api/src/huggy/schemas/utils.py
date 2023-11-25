import json


def parse_hex(input_str):
    try:
        int(input_str, 16)
        return parse_json(bytes.fromhex(input_str).decode("utf-8"))
    except ValueError:
        return None


def parse_json(input_str):
    try:
        return json.loads(input_str)
    except json.JSONDecodeError:
        return None


def parse_input(input_str):
    result = parse_hex(input_str)
    if result is not None:
        input_str = result
    result = parse_json(input_str)
    if result is not None:
        return result
    return None
