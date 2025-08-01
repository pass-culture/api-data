"""
Text preprocessing utilities for handling encodings consistently.
"""

import re
import string
import unicodedata
from typing import Any


def remove_accents(input_str: str) -> str:
    """
    Removes accents from a given string.

    Args:
        input_str: Input string with accents

    Returns:
        String with accents removed
    """
    nfkd_form = unicodedata.normalize("NFKD", input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


def preprocess_string(s: str | None) -> str | None:
    """
    Preprocesses a string by lowercasing, trimming, removing punctuation, and accents.

    Args:
        s: Input string

    Returns:
        Processed string, or None if input is None or empty
    """
    if s is None or s == "":
        return None
    s = s.lower()
    s = s.strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(f"[{string.punctuation}]", "", s)
    s = remove_accents(s)
    return s


def preprocess_text(text: str, normalize: bool = True) -> str:  # noqa: FBT001
    """
    Preprocess text to ensure proper encoding of French characters and special symbols.

    Args:
        text: The text to preprocess
        normalize: If True, also normalize the text (lowercase, remove accents, etc.)

    Returns:
        Properly encoded text
    """
    try:
        # Convert to string if not already
        text = str(text)

        # First try to normalize any already encoded text
        try:
            # Handle cases where the text is double-encoded
            text = (
                text.encode("latin1")
                .decode("unicode-escape")
                .encode("latin1")
                .decode("utf-8")
            )
        except Exception:
            try:  # noqa: SIM105
                # Handle cases where the text is already UTF-8
                text = text.encode("latin1").decode("utf-8")
            except Exception:
                # If both attempts fail, keep the original text
                pass

        # Replace common incorrect character sequences
        replacements = {
            "Ã¨": "è",
            "Ã©": "é",
            "Ã": "à",
            "Â°": "°",
            "â": "'",
            "Ã´": "ô",  # noqa: RUF001
            "Ãª": "ê",
            "Ã¢": "â",
            "Ã§": "ç",
            "Ã¯": "ï",
            "Ã®": "î",
            "Ã»": "û",
            "Ã¹": "ù",
            "Ã¤": "ä",
            "Ã«": "ë",
            "Ã¼": "ü",
        }

        for wrong, right in replacements.items():
            text = text.replace(wrong, right)

        # Apply additional normalization if requested
        if normalize:
            text = preprocess_string(text) or text

        return text
    except Exception:
        return str(text)


def preprocess_dict(data: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively preprocess all string values in a dictionary.

    Args:
        data: Dictionary to process
    Returns:
        Dictionary with all string values preprocessed
    """
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = preprocess_text(value)
        elif isinstance(value, dict):
            result[key] = preprocess_dict(value)
        elif isinstance(value, list):
            result[key] = [
                preprocess_dict(item)
                if isinstance(item, dict)
                else preprocess_text(item)
                if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            result[key] = value
    return result
