import json


def parse_hex(input_str):
    try:
        int(input_str, 16)
        return json.loads(bytes.fromhex(input_str).decode("utf-8"))
    except json.JSONDecodeError as e:
        print(e)
        return None
    except ValueError:
        return None


def parse_input(input_str):
    result = parse_hex(input_str)
    if result is not None:
        return result
    return None
