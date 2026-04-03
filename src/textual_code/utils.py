"""Shared utilities for textual-code."""

from pathlib import Path


def is_binary_file(path: Path) -> bool:
    """Return True if path is a binary file (null byte in first 8 KiB).

    Returns False on any read error.
    """
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
    except OSError:
        return False
    return b"\x00" in chunk
