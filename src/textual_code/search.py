from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pathspec

from textual_code.utils import is_binary_file

logger = logging.getLogger(__name__)


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


@dataclass
class WorkspaceSearchResponse:
    """Result of a workspace search, including any inaccessible paths."""

    results: list[WorkspaceSearchResult] = field(default_factory=list)
    inaccessible_paths: list[str] = field(default_factory=list)


def _iter_workspace_files(
    workspace_path: Path,
    *,
    respect_gitignore: bool = False,
    files_to_include: str = "",
    files_to_exclude: str = "",
    errors: list[str] | None = None,
) -> Iterator[tuple[Path, str]]:
    """Yield (file_path, text) for each non-hidden, non-binary UTF-8 text file.

    Applies optional gitignore filtering and comma-separated glob include/exclude
    patterns.  Yields nothing if any pattern string is invalid.

    Uses os.walk with onerror to survive inaccessible directories: partial results
    are still yielded and error paths are collected in the ``errors`` list.
    """
    include_patterns = [p.strip() for p in files_to_include.split(",") if p.strip()]
    exclude_patterns = [p.strip() for p in files_to_exclude.split(",") if p.strip()]

    try:
        include_spec: pathspec.PathSpec | None = (
            pathspec.PathSpec.from_lines("gitignore", include_patterns)
            if include_patterns
            else None
        )
        exclude_spec: pathspec.PathSpec | None = (
            pathspec.PathSpec.from_lines("gitignore", exclude_patterns)
            if exclude_patterns
            else None
        )
    except Exception:
        return  # Invalid pattern → yield nothing

    def _on_walk_error(err: OSError) -> None:
        path_str = str(err.filename) if err.filename else str(err)
        logger.warning("Cannot access path during search: %s", path_str)
        if errors is not None:
            errors.append(path_str)

    # Load .gitignore files, each relative to its own directory
    gitignore_specs: list[tuple[Path, pathspec.PathSpec]] = []
    if respect_gitignore:
        try:
            gitignore_paths = sorted(workspace_path.rglob(".gitignore"))
        except OSError:
            gitignore_paths = []
        for gitignore_path in gitignore_paths:
            try:
                content = gitignore_path.read_text(encoding="utf-8", errors="replace")
                spec = pathspec.PathSpec.from_lines("gitignore", content.splitlines())
                gitignore_specs.append((gitignore_path.parent, spec))
            except Exception:
                continue

    # Collect all file paths via os.walk (survives inaccessible directories)
    all_files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(
        workspace_path, onerror=_on_walk_error
    ):
        dir_path = Path(dirpath)
        # Skip hidden directories (prune from walk)
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for filename in filenames:
            if filename.startswith("."):
                continue
            all_files.append(dir_path / filename)
    all_files.sort()

    for file_path in all_files:
        # Compute relative path
        try:
            rel_path = file_path.relative_to(workspace_path)
        except ValueError:
            continue

        # Apply gitignore
        if gitignore_specs:
            ignored = False
            for gitignore_dir, spec in gitignore_specs:
                try:
                    rel_to_dir = file_path.relative_to(gitignore_dir)
                except ValueError:
                    continue
                if spec.match_file(str(rel_to_dir)):
                    ignored = True
                    break
            if ignored:
                continue

        # Apply include filter (file must match at least one pattern)
        if include_spec is not None and not include_spec.match_file(str(rel_path)):
            continue

        # Apply exclude filter (skip if any pattern matches)
        if exclude_spec is not None and exclude_spec.match_file(str(rel_path)):
            continue

        # Skip binary files
        if is_binary_file(file_path):
            continue

        # Read and decode as UTF-8; skip on error
        try:
            raw = file_path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        yield file_path, text


def search_workspace(
    workspace_path: Path,
    query: str,
    use_regex: bool = False,
    *,
    max_results: int = 500,
    respect_gitignore: bool = False,
    files_to_include: str = "",
    files_to_exclude: str = "",
    case_sensitive: bool = True,
) -> WorkspaceSearchResponse:
    """Search all text files under workspace_path for query.

    Skips hidden files/directories (parts starting with '.') and binary files
    (detected by a null byte in the first 8 KiB).  Decodes each file as UTF-8;
    files that cannot be decoded are silently skipped.

    Returns a WorkspaceSearchResponse containing up to max_results results
    ordered by file path then line number, plus any inaccessible paths
    encountered during traversal.

    Returns an empty response if query is empty or use_regex=True with an
    invalid regex pattern.
    """
    if not query:
        return WorkspaceSearchResponse()

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(query if use_regex else re.escape(query), flags)
    except re.error:
        return WorkspaceSearchResponse()

    results: list[WorkspaceSearchResult] = []
    inaccessible: list[str] = []

    for file_path, text in _iter_workspace_files(
        workspace_path,
        respect_gitignore=respect_gitignore,
        files_to_include=files_to_include,
        files_to_exclude=files_to_exclude,
        errors=inaccessible,
    ):
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
                    return WorkspaceSearchResponse(
                        results=results,
                        inaccessible_paths=inaccessible,
                    )

    return WorkspaceSearchResponse(
        results=results,
        inaccessible_paths=inaccessible,
    )


def replace_workspace(
    workspace_path: Path,
    query: str,
    replacement: str,
    use_regex: bool = False,
    *,
    respect_gitignore: bool = False,
    files_to_include: str = "",
    files_to_exclude: str = "",
    case_sensitive: bool = True,
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

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(query if use_regex else re.escape(query), flags)
    except re.error:
        return WorkspaceReplaceResult(files_modified=0, replacements_count=0)

    files_modified = 0
    replacements_count = 0

    for file_path, text in _iter_workspace_files(
        workspace_path,
        respect_gitignore=respect_gitignore,
        files_to_include=files_to_include,
        files_to_exclude=files_to_exclude,
    ):
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
