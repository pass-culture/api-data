"""
Logging utilities for the LLM framework.
"""

from contextlib import suppress
from pathlib import Path
from typing import Any

from loguru import logger

# # Helper function to safely add logger levels
# def add_logger_level(name: str, no: int, color: str) -> None:
#     with suppress(TypeError):
#         # Will silently skip if level already exists
#         logger.level(name, no=no, color=color)


# Configure color logger for console output
# add_logger_level("PROMPT", no=15, color="<cyan>")
def add_logger_level_if_not_exists(name, no, color):
    try:
        logger.level(name)
    except ValueError:
        logger.level(name, no=no, color=color)


add_logger_level_if_not_exists("PROMPT", no=15, color="<cyan>")
add_logger_level_if_not_exists("CONFIG", no=15, color="<green>")
add_logger_level_if_not_exists("METADATA", no=15, color="<yellow>")
# add_logger_level("CONFIG", no=15, color="<green>")
# add_logger_level("METADATA", no=15, color="<yellow>")

# Configure loguru to write to a file with rotation
log_path = Path("logs")
log_path.mkdir(exist_ok=True)

# Add a sink for human-readable prompt logs
logger.add(
    log_path / "llm_prompts_{time}.log",
    format="<blue>{time:YYYY-MM-DD HH:mm:ss}</blue> | {message}",
    rotation="100 MB",
    level="PROMPT",
    encoding="utf-8",  # Ensure proper UTF-8 encoding
    catch=True,  # Catch any encoding errors
)


def clean_text(text: str) -> str:
    """Ensure text is properly encoded and decoded for display."""
    try:
        # Convert to string if not already
        text = str(text)

        # First try to normalize any already encoded text
        with suppress(Exception):
            # Handle cases where the text is double-encoded
            text = (
                text.encode("latin1")
                .decode("unicode-escape")
                .encode("latin1")
                .decode("utf-8")
            )

        with suppress(Exception):
            # Handle cases where the text is already UTF-8
            text = text.encode("latin1").decode("utf-8")

        # Replace common incorrect character sequences
        replacements = {
            "Ã¨": "è",
            "Ã©": "é",
            "Ã": "à",
            "Â°": "°",
            "â": "'",
            "Ã´": "ô",  # noqa: RUF001 => à checker
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

        return text
    except Exception as e:
        logger.warning(f"Error cleaning text: {e}")
        return str(text)


def format_config(config: dict[str, Any]) -> str:
    """Format configuration details in a readable way."""
    return (
        f"Model: {clean_text(config.get('model'))} ({config.get('provider')})\n"
        f"Type: {clean_text(config.get('prompt_type'))} prompt\n"
        f"Temperature: {config.get('temperature')}\n"
        f"Schema: {clean_text(config.get('schema_type'))}"
    )


def format_metadata(metadata: dict[str, Any] | None) -> str:
    """Format metadata in a readable way."""
    if not metadata:
        return "No additional metadata"

    return "\n".join(f"{k}: {clean_text(str(v))}" for k, v in metadata.items())


def log_llm_response(
    response: str,
    success: bool,  # noqa: FBT001
    error_msg: str | None = None,
    offer_id: str | None = None,
) -> None:
    """
    Log LLM response along with its status.

    Args:
        response (str): The raw response from the LLM
        success (bool): Whether the LLM call was successful
        error_msg (str, optional): Error message if the call failed
        offer_id (str, optional): The ID of the offer being processed
    """
    # Create a visually appealing separator
    separator = "=" * 80

    status_icon = "[+]" if success else "[-]"
    status_text = "SUCCESS" if success else "FAILED"

    # Format the log entry
    log_message = f"""
{separator}
[LLM RESPONSE] {f"[{offer_id}]" if offer_id else ""}
{separator}

[STATUS] {status_icon} {status_text}

[RAW RESPONSE]
---------------
{clean_text(response) if response else "No response received"}

"""

    if not success and error_msg:
        log_message += f"""
[ERROR]
---------
{clean_text(error_msg)}
"""

    log_message += f"\n{separator}\n"
    logger.log("PROMPT", log_message)


def log_llm_prompt(
    prompt: str,
    config: dict[str, Any],
    offer_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Log LLM prompt along with configuration and metadata in a human-readable format.

    Args:
        prompt (str): The rendered prompt to be sent to the LLM
        config (Dict[str, Any]): The configuration used for this LLM call
        offer_id (str, optional): The ID of the offer being processed
        metadata (Dict[str, Any], optional): Additional metadata to log
    """
    # Create a visually appealing separator
    separator = "=" * 80

    # Format the log entry in sections
    log_message = f"""
{separator}
[PROMPT LOG] {f"[{offer_id}]" if offer_id else ""}
{separator}

[CONFIGURATION]
-------------------
{format_config(config)}

[METADATA]
------------
{format_metadata(metadata)}

[PROMPT]
----------
{clean_text(prompt)}

{separator}
"""
    logger.log("PROMPT", log_message)
