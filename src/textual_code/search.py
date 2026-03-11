from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WorkspaceSearchResult:
    """A single line match from a workspace search."""

    file_path: Path
    line_number: int  # 1-based
    line_text: str
    match_start: int  # column, 0-based
    match_end: int  # column, 0-based


def search_workspace(
    workspace_path: Path,
    query: str,
    use_regex: bool = False,
    *,
    max_results: int = 500,
) -> list[WorkspaceSearchResult]:
    """Search all text files under workspace_path for query.

    Skips hidden files/directories (parts starting with '.') and binary files
    (detected by a null byte in the first 8 KiB).  Decodes each file as UTF-8;
    files that cannot be decoded are silently skipped.

    Returns up to max_results results ordered by file path then line number.
    Returns an empty list if query is empty or use_regex=True with an invalid
    regex pattern.
    """
    if not query:
        return []

    try:
        pattern = re.compile(query if use_regex else re.escape(query))
    except re.error:
        return []

    results: list[WorkspaceSearchResult] = []

    for file_path in sorted(workspace_path.rglob("*")):
        if not file_path.is_file():
            continue

        # Skip hidden files/directories
        try:
            rel_parts = file_path.relative_to(workspace_path).parts
        except ValueError:
            continue
        if any(part.startswith(".") for part in rel_parts):
            continue

        # Read raw bytes; skip on I/O error
        try:
            raw = file_path.read_bytes()
        except OSError:
            continue

        # Skip binary files
        if b"\x00" in raw[:8192]:
            continue

        # Decode as UTF-8; skip files with encoding errors
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue

        for line_num, line in enumerate(text.splitlines(), 1):
            for match in pattern.finditer(line):
                results.append(
                    WorkspaceSearchResult(
                        file_path=file_path,
                        line_number=line_num,
                        line_text=line,
                        match_start=match.start(),
                        match_end=match.end(),
                    )
                )
                if len(results) >= max_results:
                    return results

    return results
