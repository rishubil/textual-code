from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from textual_code.utils import is_binary_file


@dataclass
class WorkspaceReplaceResult:
    """Summary of a workspace-wide replace operation."""

    files_modified: int
    replacements_count: int


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
        if is_binary_file(file_path):
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


def replace_workspace(
    workspace_path: Path,
    query: str,
    replacement: str,
    use_regex: bool = False,
) -> WorkspaceReplaceResult:
    """Replace all occurrences of query with replacement in workspace text files.

    Uses the same file-skipping rules as search_workspace(): skips hidden
    files/directories, binary files, and files that cannot be decoded as UTF-8.

    Returns a WorkspaceReplaceResult with the number of files modified and
    total replacements made.  Returns zeros if query is empty or use_regex=True
    with an invalid pattern.
    """
    if not query:
        return WorkspaceReplaceResult(files_modified=0, replacements_count=0)

    try:
        pattern = re.compile(query if use_regex else re.escape(query))
    except re.error:
        return WorkspaceReplaceResult(files_modified=0, replacements_count=0)

    files_modified = 0
    replacements_count = 0

    for file_path in sorted(workspace_path.rglob("*")):
        if not file_path.is_file():
            continue

        try:
            rel_parts = file_path.relative_to(workspace_path).parts
        except ValueError:
            continue
        if any(part.startswith(".") for part in rel_parts):
            continue

        try:
            raw = file_path.read_bytes()
        except OSError:
            continue

        if b"\x00" in raw[:8192]:
            continue

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue

        new_text, count = pattern.subn(replacement, text)
        if count > 0:
            try:
                file_path.write_text(new_text, encoding="utf-8")
            except OSError:
                continue
            files_modified += 1
            replacements_count += count

    return WorkspaceReplaceResult(
        files_modified=files_modified,
        replacements_count=replacements_count,
    )
