from __future__ import annotations

import difflib
import hashlib
import logging
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pathspec
from ripgrep_rs import files as rg_files
from ripgrep_rs import search_structured

from textual_code.commands import _SORT_BY_PATH
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
    match_start: int  # column, 0-based (character offset)
    match_end: int  # column, 0-based (character offset)


@dataclass
class WorkspaceSearchResponse:
    """Result of a workspace search, including any inaccessible paths.

    Note: ``inaccessible_paths`` is no longer populated when using the
    ripgrep-rs backend (it silently skips inaccessible files).  The field
    is retained for API compatibility.
    """

    results: list[WorkspaceSearchResult] = field(default_factory=list)
    inaccessible_paths: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _parse_include_exclude(
    files_to_include: str,
    files_to_exclude: str,
) -> tuple[pathspec.PathSpec | None, pathspec.PathSpec | None] | None:
    """Parse comma-separated include/exclude filter strings into PathSpec objects.

    Returns ``(include_spec, exclude_spec)``.  Either element may be ``None``
    when the corresponding filter string is empty.  Returns ``None`` on any
    parse error so callers can yield/return nothing.
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
        return None

    return include_spec, exclude_spec


def _byte_offset_to_char_offset(line_text: str, byte_offset: int) -> int:
    """Convert a byte offset within a UTF-8 line to a character offset.

    Uses ``errors="replace"`` so that a byte offset falling in the middle of
    a multi-byte character does not raise.
    """
    return len(
        line_text.encode("utf-8")[:byte_offset].decode("utf-8", errors="replace")
    )


# ---------------------------------------------------------------------------
# File enumeration (used by preview_workspace_replace)
# ---------------------------------------------------------------------------


def _iter_workspace_files(
    workspace_path: Path,
    *,
    respect_gitignore: bool = False,
    show_hidden_files: bool = True,
    files_to_include: str = "",
    files_to_exclude: str = "",
) -> Iterator[tuple[Path, str]]:
    """Yield (file_path, text) for each non-binary UTF-8 text file.

    When *show_hidden_files* is True, dot-prefixed entries are included
    (``.git`` is always excluded).  Uses ``ripgrep-rs`` for fast file
    enumeration with native ``.gitignore`` support.  Applies optional
    comma-separated glob include/exclude patterns via ``pathspec``
    post-filtering.
    """
    parsed = _parse_include_exclude(files_to_include, files_to_exclude)
    if parsed is None:
        return  # Invalid pattern -> yield nothing
    include_spec, exclude_spec = parsed

    # Exclude .git when showing hidden files (matches _rg_scan in commands.py)
    globs = ["!.git/", "!.git"] if show_hidden_files else None
    raw_paths = rg_files(
        paths=[str(workspace_path)],
        hidden=show_hidden_files,
        no_ignore=not respect_gitignore,
        globs=globs,
        sort=_SORT_BY_PATH,
    )

    for path_str in raw_paths:
        file_path = Path(path_str)

        # Apply include/exclude filters on the relative path
        try:
            rel_path = file_path.relative_to(workspace_path)
        except ValueError:
            continue
        rel_str = str(rel_path)

        if include_spec is not None and not include_spec.match_file(rel_str):
            continue
        if exclude_spec is not None and exclude_spec.match_file(rel_str):
            continue

        # Skip binary files (rg_files lists all files, not just text)
        if is_binary_file(file_path):
            continue

        # Read and decode as UTF-8; skip on error
        try:
            raw = file_path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        yield file_path, text


# ---------------------------------------------------------------------------
# Workspace search (ripgrep-rs backend)
# ---------------------------------------------------------------------------


def search_workspace(
    workspace_path: Path,
    query: str,
    use_regex: bool = False,
    *,
    max_results: int = 500,
    respect_gitignore: bool = False,
    show_hidden_files: bool = True,
    files_to_include: str = "",
    files_to_exclude: str = "",
    case_sensitive: bool = True,
) -> WorkspaceSearchResponse:
    """Search all text files under workspace_path for query.

    Uses ``ripgrep-rs`` for fast, native file enumeration and text matching.
    When *show_hidden_files* is True, dot-prefixed entries are included
    (``.git`` is always excluded).  Binary files are skipped.

    Returns a WorkspaceSearchResponse containing up to *max_results* results
    ordered by file path then line number.

    Returns an empty response if *query* is empty or *use_regex* is True with
    an invalid regex pattern.
    """
    if not query:
        return WorkspaceSearchResponse()

    # Build the regex pattern — always validate with Python re first so that
    # the search and replace flows use compatible regex semantics.
    rg_pattern = query if use_regex else re.escape(query)
    try:
        re.compile(rg_pattern, 0 if case_sensitive else re.IGNORECASE)
    except re.error:
        return WorkspaceSearchResponse()

    # Parse include/exclude for post-filtering
    parsed = _parse_include_exclude(files_to_include, files_to_exclude)
    if parsed is None:
        return WorkspaceSearchResponse()
    include_spec, exclude_spec = parsed
    has_filters = include_spec is not None or exclude_spec is not None

    # Generous limit: filters may discard many results, so fetch more upfront
    rg_max_total = max_results * 50 if has_filters else max_results * 5

    t0 = time.monotonic()
    try:
        globs = ["!.git/", "!.git"] if show_hidden_files else None
        matches = search_structured(
            patterns=[rg_pattern],
            paths=[str(workspace_path)],
            hidden=show_hidden_files,
            no_ignore=not respect_gitignore,
            globs=globs,
            case_sensitive=case_sensitive,
            sort=_SORT_BY_PATH,
            max_total=rg_max_total,
        )
    except ValueError as exc:
        logger.info("search_workspace: ripgrep rejected pattern: %s", exc)
        return WorkspaceSearchResponse()
    elapsed = time.monotonic() - t0
    logger.debug(
        "search_workspace: ripgrep returned %d lines in %.3fs (query=%r)",
        len(matches),
        elapsed,
        query,
    )

    results: list[WorkspaceSearchResult] = []
    path_cache: dict[str, Path] = {}

    for match in matches:
        # Skip binary content (null byte in matched line)
        if "\x00" in match.line_text:
            continue

        line_text = match.line_text.rstrip("\n\r")

        # Reuse Path objects for the same file
        path_key = match.path
        if path_key not in path_cache:
            path_cache[path_key] = Path(path_key)
        file_path = path_cache[path_key]

        # Post-filter by include/exclude on the relative path
        if has_filters:
            try:
                rel_path = file_path.relative_to(workspace_path)
            except ValueError:
                continue
            rel_str = str(rel_path)
            if include_spec is not None and not include_spec.match_file(rel_str):
                continue
            if exclude_spec is not None and exclude_spec.match_file(rel_str):
                continue

        # Convert byte offsets to char offsets — skip encoding for ASCII
        if line_text.isascii():
            for sub in match.submatches:
                results.append(
                    WorkspaceSearchResult(
                        file_path=file_path,
                        line_number=match.line_number,
                        line_text=line_text,
                        match_start=sub.start,
                        match_end=sub.end,
                    )
                )
                if len(results) >= max_results:
                    return WorkspaceSearchResponse(results=results)
        else:
            line_bytes = line_text.encode("utf-8")
            for sub in match.submatches:
                results.append(
                    WorkspaceSearchResult(
                        file_path=file_path,
                        line_number=match.line_number,
                        line_text=line_text,
                        match_start=len(
                            line_bytes[: sub.start].decode("utf-8", errors="replace")
                        ),
                        match_end=len(
                            line_bytes[: sub.end].decode("utf-8", errors="replace")
                        ),
                    )
                )
                if len(results) >= max_results:
                    return WorkspaceSearchResponse(results=results)

    return WorkspaceSearchResponse(results=results)


# ---------------------------------------------------------------------------
# Workspace replace (delegates to preview + apply)
# ---------------------------------------------------------------------------


def replace_workspace(
    workspace_path: Path,
    query: str,
    replacement: str,
    use_regex: bool = False,
    *,
    respect_gitignore: bool = False,
    show_hidden_files: bool = True,
    files_to_include: str = "",
    files_to_exclude: str = "",
    case_sensitive: bool = True,
) -> WorkspaceReplaceResult:
    """Replace all occurrences of query with replacement in workspace text files.

    Thin wrapper around ``preview_workspace_replace`` +
    ``apply_workspace_replace``.  Returns a ``WorkspaceReplaceResult`` with the
    number of files modified and total replacements made.
    """
    response = preview_workspace_replace(
        workspace_path,
        query,
        replacement,
        use_regex,
        respect_gitignore=respect_gitignore,
        show_hidden_files=show_hidden_files,
        files_to_include=files_to_include,
        files_to_exclude=files_to_exclude,
        case_sensitive=case_sensitive,
        max_files=999_999,  # no practical limit for direct replace
    )
    if not response.previews:
        return WorkspaceReplaceResult(files_modified=0, replacements_count=0)

    result = apply_workspace_replace(
        response.previews,
        query,
        replacement,
        use_regex,
        case_sensitive=case_sensitive,
    )
    return WorkspaceReplaceResult(
        files_modified=result.files_modified,
        replacements_count=result.replacements_count,
    )


# ---------------------------------------------------------------------------
# Workspace replace preview + apply (hash-based conflict detection)
# ---------------------------------------------------------------------------

_MAX_PREVIEW_FILES = 100


@dataclass
class FileDiffPreview:
    """Preview data for a single file in a workspace replace operation."""

    file_path: Path
    rel_path: str
    original_hash: str  # SHA-256 hex digest (64 chars)
    replacement_count: int
    diff_lines: list[str]  # unified_diff output lines


@dataclass
class PreviewResponse:
    """Result of preview_workspace_replace()."""

    previews: list[FileDiffPreview] = field(default_factory=list)
    is_truncated: bool = False


@dataclass
class ApplyResult:
    """Result of apply_workspace_replace()."""

    files_modified: int = 0
    replacements_count: int = 0
    files_skipped: int = 0
    skipped_files: list[str] = field(default_factory=list)
    failed_files: list[str] = field(default_factory=list)


def preview_workspace_replace(
    workspace_path: Path,
    query: str,
    replacement: str,
    use_regex: bool = False,
    *,
    respect_gitignore: bool = False,
    show_hidden_files: bool = True,
    files_to_include: str = "",
    files_to_exclude: str = "",
    case_sensitive: bool = True,
    max_files: int = _MAX_PREVIEW_FILES,
) -> PreviewResponse:
    """Generate per-file diff previews for a workspace replace operation.

    Returns a ``PreviewResponse`` containing up to *max_files* previews
    and a flag indicating whether more files matched.
    """
    if not query:
        return PreviewResponse()

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(query if use_regex else re.escape(query), flags)
    except re.error:
        return PreviewResponse()

    previews: list[FileDiffPreview] = []
    is_truncated = False
    t0 = time.monotonic()

    for file_path, text in _iter_workspace_files(
        workspace_path,
        respect_gitignore=respect_gitignore,
        show_hidden_files=show_hidden_files,
        files_to_include=files_to_include,
        files_to_exclude=files_to_exclude,
    ):
        new_text, count = pattern.subn(replacement, text)
        if count == 0 or new_text == text:
            continue

        if len(previews) >= max_files:
            is_truncated = True
            break

        try:
            rel_path = str(file_path.relative_to(workspace_path))
        except ValueError:
            rel_path = str(file_path)

        original_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        diff_lines = list(
            difflib.unified_diff(
                text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=rel_path,
                tofile=rel_path,
                n=2,
            )
        )

        previews.append(
            FileDiffPreview(
                file_path=file_path,
                rel_path=rel_path,
                original_hash=original_hash,
                replacement_count=count,
                diff_lines=diff_lines,
            )
        )

    elapsed = time.monotonic() - t0
    logger.debug(
        "preview_workspace_replace: %d files, %d replacements in %.3fs",
        len(previews),
        sum(p.replacement_count for p in previews),
        elapsed,
    )
    return PreviewResponse(previews=previews, is_truncated=is_truncated)


def apply_workspace_replace(
    previews: list[FileDiffPreview],
    query: str,
    replacement: str,
    use_regex: bool = False,
    *,
    case_sensitive: bool = True,
) -> ApplyResult:
    """Apply replacements for previously previewed files.

    Re-reads each file and verifies its SHA-256 hash matches the preview.
    Files that have changed since the preview are skipped.
    """
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(query if use_regex else re.escape(query), flags)
    except re.error:
        return ApplyResult()

    result = ApplyResult()
    t0 = time.monotonic()

    for preview in previews:
        try:
            raw = preview.file_path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            result.failed_files.append(preview.rel_path)
            continue

        current_hash = hashlib.sha256(raw).hexdigest()
        if current_hash != preview.original_hash:
            result.files_skipped += 1
            result.skipped_files.append(preview.rel_path)
            continue

        new_text, count = pattern.subn(replacement, text)
        if count == 0:
            continue

        try:
            preview.file_path.write_bytes(new_text.encode("utf-8"))
        except OSError:
            result.failed_files.append(preview.rel_path)
            continue

        result.files_modified += 1
        result.replacements_count += count

    elapsed = time.monotonic() - t0
    logger.debug(
        "apply_workspace_replace: %d modified, %d skipped, %d failed in %.3fs",
        result.files_modified,
        result.files_skipped,
        len(result.failed_files),
        elapsed,
    )
    return result
