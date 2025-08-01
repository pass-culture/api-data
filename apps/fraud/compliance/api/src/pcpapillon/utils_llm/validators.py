"""
Validation functions for file operations and data.
"""

import os
import sys
from pathlib import Path

from loguru import logger

# Add the current directory to Python path to make package imports work
sys.path.insert(0, str(Path(__file__).parent.absolute()))

from tools.text_preprocessing import preprocess_text


def validate_file_exists(file_path: str, file_type: str) -> None:
    """Validate that a file exists and is readable."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"{file_type} file not found: {file_path}")
    if not path.is_file():
        raise ValueError(f"{file_type} path is not a file: {file_path}")
    if not os.access(path, os.R_OK):
        raise PermissionError(f"Cannot read {file_type} file: {file_path}")


def get_txt_from_path(type: str, name: str) -> str:
    """
    Retrieve the content of a text file.

    Args:
        type (str): Type of file (e.g., 'prompt', 'rules', 'exemples')
        name (str): Name of the file without extension

    Returns:
        str: Content of the file

    Raises:
        FileNotFoundError: If the file doesn't exist
        PermissionError: If the file can't be read
        ValueError: If the file is empty or invalid
    """
    # Get the project root directory (where validators.py is located)
    root_dir = Path(__file__).parent
    file_path = root_dir / type / f"{name}.txt"
    logger.info(f"Reading {type} file: {name}.txt")

    try:
        validate_file_exists(str(file_path), type)
        with open(file_path, encoding="utf-8") as file:
            content = file.read().strip()

        if not content:
            raise ValueError(f"File {file_path} is empty")

        # Preprocess the content to ensure proper encoding
        content = preprocess_text(content)

        logger.debug(f"Successfully read {type} file: {name}.txt")
        return content

    except Exception as e:
        logger.error(f"Error reading {type} file {name}.txt: {e!s}")
        raise
