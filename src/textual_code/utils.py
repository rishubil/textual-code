"""Shared utilities for textual-code."""

from pathlib import Path


def is_binary_file(path: Path) -> bool:
    """Return True if path is a binary file (null byte in first 8 KiB).

    Returns False on any read error.
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return False
    return b"\x00" in raw[:8192]
