from __future__ import annotations

import contextlib
import logging
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, cast
from uuid import uuid4

from charset_normalizer import detect as _cn_detect
from rich.text import Text
from textual import events, on, work
from textual.app import ComposeResult
from textual.events import Mount
from textual.message import Message
from textual.notifications import Notification, Notify
from textual.reactive import reactive
from textual.widgets import Button, Label, Static, TextArea

from textual_code.modals import (
    ChangeEncodingModalResult,
    ChangeEncodingModalScreen,
    ChangeIndentModalResult,
    ChangeIndentModalScreen,
    ChangeLanguageModalResult,
    ChangeLanguageModalScreen,
    ChangeLineEndingModalResult,
    ChangeLineEndingModalScreen,
    DeleteFileModalResult,
    DeleteFileModalScreen,
    DiscardAndReloadModalResult,
    DiscardAndReloadModalScreen,
    GotoLineModalResult,
    GotoLineModalScreen,
    OverwriteConfirmModalResult,
    OverwriteConfirmModalScreen,
    SaveAsModalResult,
    SaveAsModalScreen,
    UnsavedChangeModalResult,
    UnsavedChangeModalScreen,
)
from textual_code.widgets.find_replace_bar import FindReplaceBar
from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

log = logging.getLogger(__name__)

# Map custom language name -> highlight query string (loaded at import time)
_CUSTOM_LANGUAGE_QUERIES: dict[str, str] = {}
# Map custom language name -> tree-sitter Language object (loaded at import time)
if TYPE_CHECKING:
    from tree_sitter import Language
    from tree_sitter_language_pack import SupportedLanguage

_CUSTOM_LANGUAGES: dict[str, Language] = {}

# All language names to attempt loading from tslp's bundled highlight queries.
# Languages that have both a parser and a highlight query will be registered.
_ALL_LANG_NAMES = [
    "ada",
    "agda",
    "arduino",
    "astro",
    "awk",
    "bash",
    "bibtex",
    "bicep",
    "bitbake",
    "blade",
    "c",
    "cairo",
    "capnp",
    "clojure",
    "cmake",
    "cpp",
    "css",
    "csv",
    "cuda",
    "d",
    "dart",
    "diff",
    "dockerfile",
    "dot",
    "eex",
    "elixir",
    "elm",
    "erlang",
    "fish",
    "forth",
    "fortran",
    "git_config",
    "git_rebase",
    "gitattributes",
    "gitcommit",
    "gleam",
    "glsl",
    "go",
    "gomod",
    "gosum",
    "hack",
    "hare",
    "haskell",
    "heex",
    "html",
    "http",
    "hurl",
    "ini",
    "java",
    "javascript",
    "jsdoc",
    "json",
    "jsonnet",
    "julia",
    "kconfig",
    "kdl",
    "kotlin",
    "llvm",
    "lua",
    "luadoc",
    "luau",
    "make",
    "markdown",
    "markdown_inline",
    "mermaid",
    "meson",
    "nginx",
    "nickel",
    "nix",
    "nqc",
    "objc",
    "odin",
    "pascal",
    "pem",
    "perl",
    "po",
    "pony",
    "prisma",
    "proto",
    "pug",
    "puppet",
    "purescript",
    "python",
    "qmljs",
    "r",
    "racket",
    "readline",
    "regex",
    "requirements",
    "robot",
    "ron",
    "ruby",
    "rust",
    "scala",
    "scheme",
    "scss",
    "smithy",
    "solidity",
    "sql",
    "ssh_config",
    "starlark",
    "svelte",
    "swift",
    "textproto",
    "thrift",
    "tlaplus",
    "toml",
    "twig",
    "v",
    "vhdl",
    "wgsl",
    "yaml",
    "zig",
]

# Languages with local .scm fallback queries (tslp has parser but no bundled query).
# Some use "; inherits:" directives resolved via _FALLBACK_INHERITS.
_FALLBACK_SCM_NAMES = [
    "typescript",
    "tsx",
    "php",
    "xml",
    "dtd",
    "ocaml",
    "ocaml_interface",
    "fsharp",
    "hcl",
    "terraform",
    "wat",
    "wast",
]

# Base language for "; inherits:" resolution — applies to both fallback .scm
# files and bundled queries that contain "; inherits:" directives.
_INHERITS: dict[str, str] = {
    "typescript": "javascript",
    "tsx": "javascript",
    "terraform": "hcl",
    "wast": "wat",
    # Bundled queries with unresolved "; inherits:"
    "blade": "html",
    "cuda": "cpp",
    "glsl": "c",
    "nqc": "c",
    "objc": "c",
}

# Languages that have a tslp parser but no query at all — register with empty
# query so Textual doesn't crash trying to import a missing tree-sitter-* package.
_PARSER_ONLY_NAMES = [
    "vim",
    "graphql",
    "latex",
    "vue",
    "typst",
    "verilog",
    "vimdoc",
]

_GRAMMARS_DIR = Path(__file__).parent.parent / "grammars"

try:
    import importlib as _importlib

    from tree_sitter_language_pack import get_language as _get_ts_language

    # _native is a Rust extension without type stubs; use importlib to avoid
    # unresolved-import diagnostics from ty.
    _native = _importlib.import_module("tree_sitter_language_pack._native")
    _get_highlights_query = _native.get_highlights_query

    # Load all languages with bundled highlight queries
    for _lang_name in _ALL_LANG_NAMES:
        try:
            _lang_obj = _get_ts_language(cast("SupportedLanguage", _lang_name))
            _query = _get_highlights_query(_lang_name)
            if _query:
                _CUSTOM_LANGUAGE_QUERIES[_lang_name] = _query
                _CUSTOM_LANGUAGES[_lang_name] = _lang_obj
        except Exception:
            pass

    def _resolve_inherits(query: str, base_query: str) -> str:
        """Strip '; inherits:' directives and prepend base language query."""
        lines = [
            line
            for line in query.splitlines()
            if not line.strip().startswith("; inherits:")
        ]
        return base_query + "\n\n" + "\n".join(lines)

    # Resolve "; inherits:" in bundled queries — prepend base language query
    for _lang_name, _base in _INHERITS.items():
        if _lang_name in _CUSTOM_LANGUAGE_QUERIES and _base in _CUSTOM_LANGUAGE_QUERIES:
            _query = _CUSTOM_LANGUAGE_QUERIES[_lang_name]
            if "; inherits:" in _query:
                _CUSTOM_LANGUAGE_QUERIES[_lang_name] = _resolve_inherits(
                    _query, _CUSTOM_LANGUAGE_QUERIES[_base]
                )

    # Fallback: load .scm files for languages without bundled queries.
    # Process in order so base languages (hcl, wat) are loaded before
    # derived ones (terraform, wast).
    for _lang_name in _FALLBACK_SCM_NAMES:
        if _lang_name not in _CUSTOM_LANGUAGE_QUERIES:
            try:
                _scm_path = _GRAMMARS_DIR / f"{_lang_name}.scm"
                _query = _scm_path.read_text(encoding="utf-8")
                _lang_obj = _get_ts_language(cast("SupportedLanguage", _lang_name))
                _base = _INHERITS.get(_lang_name)
                if _base:
                    _base_query = _CUSTOM_LANGUAGE_QUERIES.get(_base, "")
                    if _base_query:
                        _query = _resolve_inherits(_query, _base_query)
                _CUSTOM_LANGUAGE_QUERIES[_lang_name] = _query
                _CUSTOM_LANGUAGES[_lang_name] = _lang_obj
            except Exception as _e:
                log.warning("Failed to load fallback language %s: %s", _lang_name, _e)

    # Register parser-only languages (no highlight query) so Textual doesn't
    # crash trying to import a missing tree-sitter-* package.
    for _lang_name in _PARSER_ONLY_NAMES:
        if _lang_name not in _CUSTOM_LANGUAGES:
            try:
                _lang_obj = _get_ts_language(cast("SupportedLanguage", _lang_name))
                _CUSTOM_LANGUAGE_QUERIES[_lang_name] = ""
                _CUSTOM_LANGUAGES[_lang_name] = _lang_obj
            except Exception:
                pass
except ImportError:
    log.warning("tree-sitter-language-pack not available; custom languages disabled")


# ── Git diff gutter ──────────────────────────────────────────────────────────

# Cached git binary path (None if git is not installed)
_git_bin: str | None = shutil.which("git")

# Maximum line count for diff computation (performance protection)
_MAX_DIFF_LINES = 10000


class LineChangeType(Enum):
    """Type of change for a line in the git diff gutter."""

    ADDED = "added"  # green ▎
    MODIFIED = "modified"  # yellow ▎
    DELETED_ABOVE = "deleted_above"  # red ▔ (content deleted above this line)
    DELETED_BELOW = "deleted_below"  # red ▁ (content deleted below this line, EOF)


def _compute_line_changes(
    old_lines: list[str], new_lines: list[str]
) -> dict[int, LineChangeType]:
    """Compute line-level changes between old and new text.

    Returns a dict mapping line indices (in new_lines) to their change type.
    All keys are guaranteed to satisfy ``0 <= k < len(new_lines)`` — no
    phantom lines are ever created.

    Returns empty dict when either side exceeds _MAX_DIFF_LINES.
    """
    if not new_lines:
        return {}
    if len(old_lines) > _MAX_DIFF_LINES or len(new_lines) > _MAX_DIFF_LINES:
        return {}

    sm = SequenceMatcher(None, old_lines, new_lines)
    changes: dict[int, LineChangeType] = {}

    for tag, _i1, _i2, j1, j2 in sm.get_opcodes():
        if tag == "replace":
            for line in range(j1, j2):
                changes[line] = LineChangeType.MODIFIED
        elif tag == "insert":
            for line in range(j1, j2):
                changes[line] = LineChangeType.ADDED
        elif tag == "delete":
            # j1 == j2 for delete opcodes (no lines in new text).
            # Place indicator on the nearest existing line.
            if j1 < len(new_lines):
                if j1 not in changes:
                    changes[j1] = LineChangeType.DELETED_ABOVE
            elif j1 > 0 and j1 - 1 not in changes:
                changes[j1 - 1] = LineChangeType.DELETED_BELOW

    return changes


def _get_git_head_content(path: Path) -> str | None:
    """Get the HEAD version of a file from git.

    Uses ``git rev-parse --show-toplevel`` to detect the git root
    independently of the workspace path.

    Returns None when:
    - git binary not found
    - path is not inside a git repo
    - file is not tracked (untracked / new)
    - subprocess times out or fails
    """
    if _git_bin is None:
        log.debug("git diff gutter: git binary not found")
        return None

    resolved = path.resolve()
    parent = str(resolved.parent)

    try:
        # Find git root
        result = subprocess.run(
            [_git_bin, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=parent,
            timeout=5,
        )
        if result.returncode != 0:
            log.debug("git diff gutter: not a git repo at %s", parent)
            return None

        git_root = Path(result.stdout.strip())
        rel_path = resolved.relative_to(git_root).as_posix()

        # Get HEAD content
        result = subprocess.run(
            [_git_bin, "show", f"HEAD:{rel_path}"],
            capture_output=True,
            text=True,
            cwd=str(git_root),
            timeout=5,
        )
        if result.returncode != 0:
            log.debug("git diff gutter: file not tracked: %s", rel_path)
            return None

        return result.stdout
    except subprocess.TimeoutExpired:
        log.warning("git diff gutter: timed out for %s", path)
        return None
    except (OSError, ValueError) as e:
        log.debug("git diff gutter: error: %s", e)
        return None


def _editorconfig_glob_to_pattern(glob: str) -> re.Pattern:
    """Convert an EditorConfig glob pattern to a compiled re.Pattern.

    If the glob contains no slash, it is prefixed with '**/' so that it
    matches the filename at any directory depth (per EditorConfig spec).
    """
    if "/" not in glob:
        glob = "**/" + glob
    return re.compile(_glob_to_regex(glob))


def _glob_to_regex(glob: str) -> str:
    """Translate a single EditorConfig glob string into a regex string."""
    result: list[str] = []
    i = 0
    n = len(glob)
    while i < n:
        c = glob[i]
        if c == "\\" and i + 1 < n:
            result.append(re.escape(glob[i + 1]))
            i += 2
        elif c == "*":
            if i + 1 < n and glob[i + 1] == "*":
                if i + 2 < n and glob[i + 2] == "/":
                    # **/ → optional path prefix (matches zero or more dirs)
                    result.append("(.*/)?")
                    i += 3
                else:
                    result.append(".*")
                    i += 2
            else:
                result.append("[^/]*")
                i += 1
        elif c == "?":
            result.append("[^/]")
            i += 1
        elif c == "[":
            j = i + 1
            if j < n and glob[j] == "!":
                j += 1
            if j < n and glob[j] == "]":
                j += 1
            while j < n and glob[j] != "]":
                j += 1
            bracket = glob[i : j + 1]
            if bracket.startswith("[!"):
                bracket = "[^" + bracket[2:]
            result.append(bracket)
            i = j + 1
        elif c == "{":
            j = i + 1
            depth = 1
            while j < n and depth > 0:
                if glob[j] == "{":
                    depth += 1
                elif glob[j] == "}":
                    depth -= 1
                j += 1
            inner = glob[i + 1 : j - 1]
            range_match = re.match(r"^(-?\d+)\.\.(-?\d+)$", inner)
            if range_match:
                n1, n2 = int(range_match.group(1)), int(range_match.group(2))
                if n1 < n2:
                    alternatives = [str(x) for x in range(n1, n2 + 1)]
                    result.append("(" + "|".join(alternatives) + ")")
                else:
                    result.append(re.escape(glob[i:j]))
            else:
                parts = inner.split(",")
                converted = [_glob_to_regex(p) for p in parts]
                result.append("(" + "|".join(converted) + ")")
            i = j
        elif c == "/":
            result.append("/")
            i += 1
        else:
            result.append(re.escape(c))
            i += 1
    return "".join(result)


def _parse_editorconfig_file(
    ec_file: Path, target_file: Path
) -> tuple[bool, dict[str, str]]:
    """Parse one .editorconfig file and return (is_root, matched_properties).

    is_root is True only when 'root = true' appears in the preamble
    (before any section header). Properties from sections whose glob matches
    *target_file* are collected; later sections override earlier ones.
    All keys and values are lowercased.
    """
    is_root = False
    result: dict[str, str] = {}
    try:
        rel_str = str(target_file.relative_to(ec_file.parent)).replace("\\", "/")
    except ValueError:
        return False, {}

    try:
        content = ec_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False, {}
    in_preamble = True
    current_section_matches = False

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#") or stripped.startswith(";"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            in_preamble = False
            glob = stripped[1:-1]
            try:
                pattern = _editorconfig_glob_to_pattern(glob)
                current_section_matches = bool(pattern.fullmatch(rel_str))
            except re.error:
                current_section_matches = False
            continue
        if "=" in stripped:
            key, _, value = stripped.partition("=")
            key = key.strip().lower()
            value = value.strip().lower()
            if in_preamble:
                if key == "root" and value == "true":
                    is_root = True
            elif current_section_matches:
                result[key] = value

    return is_root, result


def _read_editorconfig(path: Path) -> tuple[dict[str, str], list[Path]]:
    """Return EditorConfig properties that apply to *path* and searched dirs.

    Traverses from path.parent upward, collecting .editorconfig files.
    Closer files take precedence over more distant ones.
    Stops at root=true (preamble only) or the filesystem root.
    All keys and values are lowercased.

    Returns (properties, searched_dirs) where searched_dirs is the list of
    directories checked for .editorconfig files (closest first).
    """
    result: dict[str, str] = {}
    searched_dirs: list[Path] = []

    # Collect .editorconfig files from closest to farthest
    config_files: list[Path] = []
    directory = path.parent
    while True:
        searched_dirs.append(directory)
        ec_file = directory / ".editorconfig"
        try:
            if ec_file.is_file():
                config_files.append(ec_file)
        except OSError:
            pass
        parent = directory.parent
        if parent == directory:
            break
        directory = parent

    # Process closest first; closer keys win (not overwritten by farther)
    root_dir: Path | None = None
    for ec_file in config_files:
        is_root, props = _parse_editorconfig_file(ec_file, path)
        for key, value in props.items():
            if key not in result:
                result[key] = value
        if is_root:
            root_dir = ec_file.parent
            break

    # Trim searched_dirs to stop at root=true boundary
    if root_dir is not None:
        try:
            idx = searched_dirs.index(root_dir)
            searched_dirs = searched_dirs[: idx + 1]
        except ValueError:
            pass

    return result, searched_dirs


def _snapshot_editorconfig_mtimes(dirs: list[Path]) -> dict[Path, float | None]:
    """Return {dir: mtime_or_None} for .editorconfig in each directory."""
    mtimes: dict[Path, float | None] = {}
    for d in dirs:
        try:
            mtimes[d] = (d / ".editorconfig").stat().st_mtime
        except OSError:
            mtimes[d] = None
    return mtimes


_CHARSET_MAP: dict[str, str] = {
    "utf-8": "utf-8",
    "utf-8-bom": "utf-8-sig",
    "utf-16be": "utf-16",
    "utf-16le": "utf-16",
    "latin1": "latin-1",
}


def _text_offset_to_location(text: str, offset: int) -> tuple[int, int]:
    """Convert a character offset in *text* to a (row, col) location."""
    row = col = 0
    for ch in text[:offset]:
        if ch == "\n":
            row += 1
            col = 0
        else:
            col += 1
    return (row, col)


def _location_to_text_offset(text: str, location: tuple[int, int]) -> int:
    """Convert a (row, col) location to a character offset in text."""
    row, col = location
    lines = text.split("\n")
    offset = sum(len(lines[i]) + 1 for i in range(min(row, len(lines))))
    return offset + col


def _word_boundary_pattern(query: str) -> str:
    """Build a regex pattern that matches *query* at word boundaries."""
    return r"\b" + re.escape(query) + r"\b"


def _find_next(
    text: str,
    query: str,
    cursor_offset: int,
    use_regex: bool = False,
    case_sensitive: bool = True,
) -> tuple[int, int]:
    """Return (start, end) of next match from cursor_offset, wrapping around.

    Returns (-1, -1) if not found.
    Raises re.error for invalid regex when use_regex=True.
    """
    flags = 0 if case_sensitive else re.IGNORECASE
    if use_regex:
        flags |= re.MULTILINE
    pattern = re.compile(query if use_regex else re.escape(query), flags)
    match = pattern.search(text, cursor_offset)
    if match is None:
        match = pattern.search(text, 0)
    if match is not None:
        return match.start(), match.end()
    return -1, -1


def _find_previous(
    text: str,
    query: str,
    cursor_offset: int,
    use_regex: bool = False,
    case_sensitive: bool = True,
) -> tuple[int, int]:
    """Return (start, end) of previous match before cursor_offset, wrapping around.

    A match whose end >= cursor_offset is skipped (it overlaps the cursor).
    Returns (-1, -1) if not found.
    Raises re.error for invalid regex when use_regex=True.
    """
    flags = 0 if case_sensitive else re.IGNORECASE
    if use_regex:
        flags |= re.MULTILINE
    pattern = re.compile(query if use_regex else re.escape(query), flags)
    # Single pass: track the last match before cursor and the last match overall
    last_before = None
    last_overall = None
    for m in pattern.finditer(text):
        last_overall = m
        if m.end() < cursor_offset:
            last_before = m
    result = last_before or last_overall
    if result is not None:
        return result.start(), result.end()
    return -1, -1


def _get_word_at_location(text: str, row: int, col: int) -> str:
    """Return the word under (row, col) using \\w+ boundaries.

    Returns an empty string if the character at (row, col) is not a word
    character or if the coordinates are out of range.
    """
    bounds = MultiCursorTextArea._word_bounds_at(text, row, col)
    if bounds is None:
        return ""
    lines = text.split("\n")
    line = lines[row]
    return line[bounds[0] : bounds[1]]


def _convert_indentation(text: str, to_type: str, to_size: int) -> str:
    """Convert the leading indentation of each line to the target type and size.

    Each existing tab is treated as *to_size* virtual spaces when computing the
    new leading whitespace, so mixed indent files are normalized correctly.
    """
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.lstrip()
        leading = line[: len(line) - len(stripped)]
        # Normalize to virtual spaces (each tab counts as to_size spaces)
        spaces = leading.replace("\t", " " * to_size)
        if to_type == "tabs":
            n_tabs, remainder = divmod(len(spaces), to_size)
            new_leading = "\t" * n_tabs + " " * remainder
        else:
            new_leading = spaces
        result.append(new_leading + stripped)
    return "\n".join(result)


def _detect_line_ending(raw_text: str) -> str:
    """Detect line ending style from raw file text (read with open(newline=""))."""
    if "\r\n" in raw_text:
        return "crlf"
    if "\r" in raw_text:
        return "cr"
    return "lf"


def _convert_line_ending(text: str, line_ending: str) -> str:
    """Convert TextArea.text (LF-only) to the specified line ending style.

    Used when saving the file.
    """
    if line_ending == "crlf":
        return text.replace("\n", "\r\n")
    if line_ending == "cr":
        return text.replace("\n", "\r")
    return text


def _trim_trailing_whitespace(text: str) -> str:
    """Remove trailing whitespace from each line.

    Operates on LF-normalized text (as stored in TextArea).
    """
    return "\n".join(line.rstrip(" \t") for line in text.split("\n"))


def _insert_final_newline(text: str) -> str:
    """Ensure text ends with a newline character.

    If text is empty, return empty (do not add newline to empty content).
    """
    if not text or text.endswith("\n"):
        return text
    return text + "\n"


def _remove_final_newline(text: str) -> str:
    """Ensure text does NOT end with a newline character."""
    return text.rstrip("\n")


def _indent_display(indent_type: str, indent_size: int) -> str:
    """Return footer display label for indentation settings."""
    if indent_type == "tabs":
        return "Tabs"
    return f"{indent_size} Spaces"


_ENCODING_DISPLAY: dict[str, str] = {
    # Unicode
    "utf-8": "UTF-8",
    "utf-8-sig": "UTF-8 BOM",
    "utf-16": "UTF-16",
    "utf-16-le": "UTF-16 LE",
    "utf-16-be": "UTF-16 BE",
    "utf-32": "UTF-32",
    "utf-32-le": "UTF-32 LE",
    "utf-32-be": "UTF-32 BE",
    # Western European
    "latin-1": "Latin-1 (ISO-8859-1)",
    "cp1252": "Windows-1252 (Western)",
    "iso-8859-15": "ISO-8859-15 (Western)",
    # Central/Eastern European
    "cp1250": "Windows-1250 (Central European)",
    "iso-8859-2": "ISO-8859-2 (Central European)",
    "cp1257": "Windows-1257 (Baltic)",
    "iso-8859-13": "ISO-8859-13 (Baltic)",
    # Cyrillic
    "cp1251": "Windows-1251 (Cyrillic)",
    "iso-8859-5": "ISO-8859-5 (Cyrillic)",
    "koi8-r": "KOI8-R (Russian)",
    "koi8-u": "KOI8-U (Ukrainian)",
    # Greek
    "cp1253": "Windows-1253 (Greek)",
    "iso-8859-7": "ISO-8859-7 (Greek)",
    # Turkish
    "cp1254": "Windows-1254 (Turkish)",
    "iso-8859-9": "ISO-8859-9 (Turkish)",
    # Hebrew
    "cp1255": "Windows-1255 (Hebrew)",
    # Arabic
    "cp1256": "Windows-1256 (Arabic)",
    # Vietnamese
    "cp1258": "Windows-1258 (Vietnamese)",
    # Japanese
    "shift_jis": "Shift-JIS (Japanese)",
    "euc_jp": "EUC-JP (Japanese)",
    # Chinese Simplified
    "gbk": "GBK (Chinese Simplified)",
    "gb18030": "GB18030 (Chinese Simplified)",
    # Chinese Traditional
    "big5": "Big5 (Chinese Traditional)",
    # Korean
    "euc_kr": "EUC-KR (Korean)",
    # ASCII
    "ascii": "ASCII",
}


def _detect_encoding(raw_bytes: bytes) -> str:
    """Detect file encoding from raw bytes using BOM inspection then charset-normalizer.

    Falls back to latin-1 for short or ambiguous byte sequences.
    """
    # UTF-32 BOM must be checked before UTF-16 (shares prefix bytes)
    if raw_bytes.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        return "utf-32"
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    try:
        raw_bytes.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    # Use charset-normalizer for non-UTF-8 content.
    # Requires enough bytes for reliable detection (short sequences are ambiguous).
    if len(raw_bytes) >= 100:
        result = _cn_detect(raw_bytes)
        encoding = result.get("encoding")
        confidence = result.get("confidence") or 0.0
        if encoding and confidence > 0.7:
            return encoding.lower()
    return "latin-1"


_LINE_ENDING_WARNING = (
    "{ending} line endings: copied/pasted text will use LF internally."
)


@dataclass
class EditorState:
    """Serialized state of a CodeEditor for lazy unmounting."""

    pane_id: str
    path: Path | None
    text: str
    initial_text: str
    language: str | None
    encoding: str
    line_ending: str
    indent_type: str
    indent_size: int
    word_wrap: bool
    cursor_end: tuple[int, int]
    scroll_offset: tuple[int, int]
    file_mtime: float | None
    ec_search_dirs: list[Path]
    ec_mtimes: dict[Path, float | None]
    trim_trailing_whitespace: bool | None
    insert_final_newline: bool | None
    syntax_theme: str
    warn_line_ending: bool
    notified_copy_line_ending: bool
    show_indentation_guides: bool = True
    render_whitespace: str = "none"


class _PathLabel(Label):
    """Label that front-truncates its content to fit the available width."""

    _raw: str = ""

    def show(
        self,
        path: Path | None,
        workspace_path: Path | None = None,
        mode: str = "absolute",
    ) -> None:
        """Set the path and immediately render (uses current region if available)."""
        if path is None:
            self._raw = ""
        elif mode == "relative" and workspace_path is not None:
            try:
                self._raw = path.relative_to(workspace_path).as_posix()
            except ValueError:
                self._raw = str(path)
        else:
            self._raw = str(path)
        self._truncate()

    def _truncate(self) -> None:
        raw = self._raw
        available = self.region.width
        if available > 0 and len(raw) > available:
            theme = self.app.theme_variables
            fg = theme.get("foreground-darken-3", "#a2a2a2")
            bg = theme.get("surface-lighten-2", "#3e3e3e")
            ellipsis_style = f"{fg} on {bg}"
            if available > 3:
                tail = raw[-(available - 3) :]
                text = Text()
                text.append("...", style=ellipsis_style)
                text.append(tail)
                self.update(text)
            else:
                self.update(Text("..."[:available], style=ellipsis_style))
        else:
            self.update(raw)

    def on_resize(self) -> None:
        self._truncate()


class CodeEditorFooter(Static):
    """
    Footer for the CodeEditor widget.

    It displays the information about the current file being edited.
    """

    DEFAULT_CSS = """
    CodeEditorFooter {
        dock: bottom;
        height: 1;
        layout: horizontal;
    }
    CodeEditorFooter Button {
        height: 1;
        border: none;
        min-width: 0;
    }
    """

    # the path of the file
    path: reactive[Path | None] = reactive(None, init=False)
    # the language of the file
    language: reactive[str | None] = reactive(None, init=False)
    # the cursor location (row, col) — zero-based internally, displayed 1-based
    cursor_location: reactive[tuple[int, int]] = reactive((0, 0), init=False)
    # total cursor count (1 = single cursor, >1 = multi-cursor active)
    cursor_count: reactive[int] = reactive(1, init=False)
    # the line ending style
    line_ending: reactive[str] = reactive("lf", init=False)
    # the file encoding
    encoding: reactive[str] = reactive("utf-8", init=False)
    # the indentation type ("spaces" or "tabs")
    indent_type: reactive[str] = reactive("spaces", init=False)
    # the indentation size (2, 4, or 8)
    indent_size: reactive[int] = reactive(4, init=False)
    # path display mode ("absolute" or "relative")
    path_display_mode: reactive[str] = reactive("absolute", init=False)

    def __init__(
        self,
        path: Path | None = None,
        language: str | None = None,
        line_ending: str = "lf",
        encoding: str = "utf-8",
        indent_type: str = "spaces",
        indent_size: int = 4,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.set_reactive(CodeEditorFooter.path, path)
        self.set_reactive(CodeEditorFooter.language, language)
        self.set_reactive(CodeEditorFooter.line_ending, line_ending)
        self.set_reactive(CodeEditorFooter.encoding, encoding)
        self.set_reactive(CodeEditorFooter.indent_type, indent_type)
        self.set_reactive(CodeEditorFooter.indent_size, indent_size)

    def reset(self) -> None:
        """Reset footer to empty/default state (no active editor).

        path_display_mode intentionally excluded — global setting, not per-editor state.
        """
        self.path = None
        self.language = None
        self.cursor_location = (0, 0)
        self.cursor_count = 1
        self.line_ending = "lf"
        self.encoding = "utf-8"
        self.indent_type = "spaces"
        self.indent_size = 4

    def compose(self) -> ComposeResult:
        yield _PathLabel(
            str(self.path) if self.path else "",
            id="path",
        )
        yield Button(
            "Ln 1, Col 1",
            variant="default",
            id="cursor_btn",
        )
        yield Button(
            self.line_ending.upper(),
            variant="default",
            id="line_ending_btn",
        )
        yield Button(
            _ENCODING_DISPLAY.get(self.encoding, self.encoding),
            variant="default",
            id="encoding_btn",
        )
        yield Button(
            _indent_display(self.indent_type, self.indent_size),
            variant="default",
            id="indent_btn",
        )
        yield Button(
            self.language or "plain",
            variant="default",
            id="language",
        )

    def _refresh_path_display(self) -> None:
        ws = getattr(self.app, "workspace_path", None)
        self.path_view.show(self.path, ws, self.path_display_mode)

    def watch_path(self, path: Path | None) -> None:
        self._refresh_path_display()

    def watch_path_display_mode(self, mode: str) -> None:
        self._refresh_path_display()

    def watch_language(self, language: str | None) -> None:
        self.language_button.label = language or "plain"
        self.language_button.refresh(layout=True)
        self.refresh(layout=True)

    def watch_cursor_location(self, location: tuple[int, int]) -> None:
        self._update_cursor_button()

    def watch_cursor_count(self, count: int) -> None:
        self._update_cursor_button()

    def _update_cursor_button_label(self) -> None:
        """Update cursor button label only (no refresh)."""
        row, col = self.cursor_location
        label = f"Ln {row + 1}, Col {col + 1}"
        if self.cursor_count > 1:
            label += f" [{self.cursor_count}]"
        self.cursor_button.label = label

    def _update_cursor_button(self) -> None:
        self._update_cursor_button_label()
        self.cursor_button.refresh(layout=True)
        self.refresh(layout=True)

    def refresh_all_buttons(self) -> None:
        """Update all button labels from current reactive values and refresh once."""
        self._refresh_path_display()
        self._update_cursor_button_label()
        self.cursor_button.refresh(layout=True)
        self.line_ending_button.label = self.line_ending.upper()
        self.line_ending_button.refresh(layout=True)
        self.encoding_button.label = _ENCODING_DISPLAY.get(self.encoding, self.encoding)
        self.encoding_button.refresh(layout=True)
        self.indent_button.label = _indent_display(self.indent_type, self.indent_size)
        self.indent_button.refresh(layout=True)
        self.language_button.label = self.language or "plain"
        self.language_button.refresh(layout=True)
        self.refresh(layout=True)

    def watch_line_ending(self, line_ending: str) -> None:
        self.line_ending_button.label = line_ending.upper()
        self.line_ending_button.refresh(layout=True)
        self.refresh(layout=True)

    def watch_encoding(self, encoding: str) -> None:
        self.encoding_button.label = _ENCODING_DISPLAY.get(encoding, encoding)
        self.encoding_button.refresh(layout=True)
        self.refresh(layout=True)

    def watch_indent_type(self, indent_type: str) -> None:
        self.indent_button.label = _indent_display(indent_type, self.indent_size)
        self.indent_button.refresh(layout=True)
        self.refresh(layout=True)

    def watch_indent_size(self, indent_size: int) -> None:
        self.indent_button.label = _indent_display(self.indent_type, indent_size)
        self.indent_button.refresh(layout=True)
        self.refresh(layout=True)

    @property
    def path_view(self) -> _PathLabel:
        return self.query_one("#path", _PathLabel)

    @property
    def cursor_button(self) -> Button:
        return self.query_one("#cursor_btn", Button)

    @property
    def line_ending_button(self) -> Button:
        return self.query_one("#line_ending_btn", Button)

    @property
    def encoding_button(self) -> Button:
        return self.query_one("#encoding_btn", Button)

    @property
    def indent_button(self) -> Button:
        return self.query_one("#indent_btn", Button)

    @property
    def language_button(self) -> Button:
        return self.query_one("#language", Button)


class CodeEditor(Static):
    """
    Code editor widget.

    It allows the user to edit code in a text area, with syntax highlighting.
    """

    # the unique ID of the pane.
    # this is used to identify the pane in the MainView.
    pane_id: reactive[str] = reactive("", init=False)
    # the path of the file
    path: reactive[Path | None] = reactive(None, init=False)
    # the initial text of the editor.
    # this is the text that was loaded from the file.
    # if the text is change from the initial text, the editor is considered to have
    # unsaved changes.
    initial_text: reactive[str] = reactive("", init=False)
    # the current text of the editor
    text: reactive[str] = reactive("", init=False)
    # the title of the editor.
    # it will be displayed in the tab of the pane.
    title: reactive[str] = reactive("...", init=False)
    # the language of the file
    language: reactive[str | None] = reactive(None, init=False)
    # the line ending style of the file
    line_ending: reactive[str] = reactive("lf", init=False)
    # the file encoding
    encoding: reactive[str] = reactive("utf-8", init=False)
    # the indentation type ("spaces" or "tabs")
    indent_type: reactive[str] = reactive("spaces", init=False)
    # the indentation size (2, 4, or 8)
    indent_size: reactive[int] = reactive(4, init=False)
    # whether word wrap is enabled
    word_wrap: reactive[bool] = reactive(False, init=False)
    show_indentation_guides: reactive[bool] = reactive(True, init=False)
    render_whitespace: reactive[str] = reactive("none", init=False)

    # mapping of file extensions to language names
    LANGUAGE_EXTENSIONS = {
        "py": "python",
        "pyi": "python",
        "json": "json",
        "md": "markdown",
        "markdown": "markdown",
        "yaml": "yaml",
        "yml": "yaml",
        "toml": "toml",
        "rs": "rust",
        "html": "html",
        "htm": "html",
        "css": "css",
        "xml": "xml",
        "regex": "regex",
        "sql": "sql",
        "js": "javascript",
        "mjs": "javascript",
        "cjs": "javascript",
        "java": "java",
        "sh": "bash",
        "bash": "bash",
        "go": "go",
        "svg": "xml",
        "xhtml": "xml",
        # tree-sitter-language-pack languages
        "dockerfile": "dockerfile",
        "ts": "typescript",
        "tsx": "tsx",
        "c": "c",
        "h": "c",
        "cpp": "cpp",
        "cc": "cpp",
        "cxx": "cpp",
        "hpp": "cpp",
        "rb": "ruby",
        "kt": "kotlin",
        "kts": "kotlin",
        "lua": "lua",
        "php": "php",
        "mk": "make",
        # expanded languages
        "scala": "scala",
        "sc": "scala",
        "swift": "swift",
        "r": "r",
        "R": "r",
        "pl": "perl",
        "pm": "perl",
        "hs": "haskell",
        "ex": "elixir",
        "exs": "elixir",
        "erl": "erlang",
        "zig": "zig",
        "dart": "dart",
        "jl": "julia",
        "nix": "nix",
        "clj": "clojure",
        "cljs": "clojure",
        "elm": "elm",
        "f90": "fortran",
        "f95": "fortran",
        "f03": "fortran",
        "ml": "ocaml",
        "mli": "ocaml_interface",
        "scss": "scss",
        "d": "d",
        "v": "v",
        "ada": "ada",
        "adb": "ada",
        "ads": "ada",
        "fish": "fish",
        "gleam": "gleam",
        "ini": "ini",
        "cfg": "ini",
        "proto": "proto",
        "svelte": "svelte",
        "tf": "terraform",
        "tfvars": "terraform",
        "hcl": "hcl",
        "fs": "fsharp",
        "fsi": "fsharp",
        "fsx": "fsharp",
        "dtd": "dtd",
        "wat": "wat",
        "wast": "wast",
    }

    # mapping of exact file names to language names (checked before extension)
    LANGUAGE_FILENAMES = {
        ".bashrc": "bash",
        ".bash_profile": "bash",
        ".bash_logout": "bash",
        # custom languages via tree-sitter-language-pack
        "Dockerfile": "dockerfile",
        "Makefile": "make",
        "makefile": "make",
        "GNUmakefile": "make",
    }

    @dataclass
    class TitleChanged(Message):
        """
        Message to notify that the title of the editor has changed.
        """

        code_editor: CodeEditor

        @property
        def control(self) -> CodeEditor:
            return self.code_editor

    @dataclass
    class Saved(Message):
        """
        Message to notify that the file has been saved.
        """

        code_editor: CodeEditor

        @property
        def control(self) -> CodeEditor:
            return self.code_editor

    @dataclass
    class SavedAs(Message):
        """
        Message to notify that the file has been saved as a new file.
        """

        code_editor: CodeEditor

        @property
        def control(self) -> CodeEditor:
            return self.code_editor

    @dataclass
    class Closed(Message):
        """
        Message to notify that the editor has been closed.
        """

        code_editor: CodeEditor

        @property
        def control(self) -> CodeEditor:
            return self.code_editor

    @dataclass
    class Deleted(Message):
        """
        Message to notify that the file has been deleted.
        """

        code_editor: CodeEditor

        @property
        def control(self) -> CodeEditor:
            return self.code_editor

    @dataclass
    class TextChanged(Message):
        """Posted when the editor's text content changes."""

        code_editor: CodeEditor

        @property
        def control(self) -> CodeEditor:
            return self.code_editor

    @dataclass
    class FooterStateChanged(Message):
        """Posted when this editor's footer-relevant state changes."""

        code_editor: CodeEditor

        @property
        def control(self) -> CodeEditor:
            return self.code_editor

    @classmethod
    def generate_pane_id(cls) -> str:
        """
        Generate a unique pane ID.
        """
        return f"pane-code-editor-{uuid4().hex}"

    def __init__(
        self,
        pane_id: str,
        path: Path | None,
        *args,
        default_indent_type: str = "spaces",
        default_indent_size: int = 4,
        default_line_ending: str = "lf",
        default_encoding: str = "utf-8",
        default_syntax_theme: str = "monokai",
        default_word_wrap: bool = False,
        default_show_indentation_guides: bool = True,
        default_render_whitespace: str = "none",
        default_warn_line_ending: bool = True,
        _from_state: EditorState | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.set_reactive(CodeEditor.pane_id, pane_id)
        self.set_reactive(CodeEditor.path, path)
        self._file_mtime: float | None = None
        self._external_change_notification: Notification | None = None
        self._syntax_theme: str = default_syntax_theme
        self._warn_line_ending: bool = default_warn_line_ending
        self._notified_copy_line_ending: bool = False
        # tracks the end offset of the last successful find for sequential search
        self._find_offset: int | None = None
        # Ctrl+D word-boundary mode: non-empty when initiated from collapsed cursor
        self._ctrl_d_query: str = ""
        # EditorConfig save-time transformations (None = not set)
        self._trim_trailing_whitespace: bool | None = None
        self._insert_final_newline: bool | None = None
        # EditorConfig watch state
        self._ec_search_dirs: list[Path] = []
        self._ec_mtimes: dict[Path, float | None] = {}
        # cursor/scroll positions to restore after mount (lazy remount)
        self._restore_cursor: tuple[int, int] | None = None
        self._restore_scroll: tuple[int, int] | None = None
        self._is_restoring: bool = False
        # Git diff gutter: cached HEAD lines for diff computation
        self._git_head_lines: list[str] | None = None

        if _from_state is not None:
            # Restore from captured state — skip file I/O
            self.set_reactive(CodeEditor.pane_id, _from_state.pane_id)
            self.set_reactive(CodeEditor.path, _from_state.path)
            self.set_reactive(CodeEditor.initial_text, _from_state.initial_text)
            self.set_reactive(CodeEditor.text, _from_state.text)
            self.set_reactive(CodeEditor.language, _from_state.language)
            self.set_reactive(CodeEditor.encoding, _from_state.encoding)
            self.set_reactive(CodeEditor.line_ending, _from_state.line_ending)
            self.set_reactive(CodeEditor.indent_type, _from_state.indent_type)
            self.set_reactive(CodeEditor.indent_size, _from_state.indent_size)
            self.set_reactive(CodeEditor.word_wrap, _from_state.word_wrap)
            self.set_reactive(
                CodeEditor.show_indentation_guides,
                _from_state.show_indentation_guides,
            )
            self.set_reactive(
                CodeEditor.render_whitespace,
                _from_state.render_whitespace,
            )
            self._file_mtime = _from_state.file_mtime
            self._ec_search_dirs = list(_from_state.ec_search_dirs)
            self._ec_mtimes = dict(_from_state.ec_mtimes)
            self._trim_trailing_whitespace = _from_state.trim_trailing_whitespace
            self._insert_final_newline = _from_state.insert_final_newline
            self._syntax_theme = _from_state.syntax_theme
            self._warn_line_ending = _from_state.warn_line_ending
            self._notified_copy_line_ending = _from_state.notified_copy_line_ending
            self._restore_cursor = _from_state.cursor_end
            self._restore_scroll = _from_state.scroll_offset
            self._is_restoring = True
            return

        # if a path is provided, load the file content
        if path is not None:
            try:
                raw_bytes = path.read_bytes()
            except Exception as e:
                raw_bytes = b""
                self.notify(f"Error reading file: {e}", severity="error")
            detected_encoding = _detect_encoding(raw_bytes)
            self.set_reactive(CodeEditor.encoding, detected_encoding)
            try:
                raw_text = raw_bytes.decode(detected_encoding)
            except Exception:
                raw_text = raw_bytes.decode("latin-1", errors="replace")
            detected = _detect_line_ending(raw_text)
            self.set_reactive(CodeEditor.line_ending, detected)
            # normalize to \n for the editor
            text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
            # remove BOM char if present (utf-8-sig decodes it, but guard defensively)
            if text.startswith("\ufeff"):
                text = text[1:]
            self.set_reactive(CodeEditor.initial_text, text)
            self.set_reactive(CodeEditor.text, text)
            with contextlib.suppress(OSError):
                self._file_mtime = path.stat().st_mtime

            # Apply EditorConfig overrides (after auto-detect)
            ec, self._ec_search_dirs = _read_editorconfig(path)
            self._ec_mtimes = _snapshot_editorconfig_mtimes(self._ec_search_dirs)
            self._apply_editorconfig(ec, init_all=True)

            self.set_reactive(CodeEditor.word_wrap, default_word_wrap)
            self.set_reactive(
                CodeEditor.show_indentation_guides,
                default_show_indentation_guides,
            )
            self.set_reactive(
                CodeEditor.render_whitespace,
                default_render_whitespace,
            )
        else:
            # Apply app-level defaults for new untitled files
            self.set_reactive(CodeEditor.indent_type, default_indent_type)
            self.set_reactive(CodeEditor.indent_size, default_indent_size)
            self.set_reactive(CodeEditor.line_ending, default_line_ending)
            self.set_reactive(CodeEditor.encoding, default_encoding)
            self.set_reactive(CodeEditor.word_wrap, default_word_wrap)
            self.set_reactive(
                CodeEditor.show_indentation_guides,
                default_show_indentation_guides,
            )
            self.set_reactive(
                CodeEditor.render_whitespace,
                default_render_whitespace,
            )

    def _apply_editorconfig(
        self, ec: dict[str, str], *, init_all: bool = False
    ) -> None:
        """Apply editorconfig properties to editor state.

        When init_all=True (first open), uses set_reactive (widget not mounted
        yet, watchers cannot fire). Also applies charset and end_of_line.
        When init_all=False (reload), uses direct assignment so that watchers
        fire and the TextArea widget + footer are updated.
        """
        ec_indent_style = ec.get("indent_style")
        if init_all:
            if ec_indent_style == "space":
                self.set_reactive(CodeEditor.indent_type, "spaces")
            elif ec_indent_style == "tab":
                self.set_reactive(CodeEditor.indent_type, "tabs")
        else:
            if ec_indent_style == "space":
                self.indent_type = "spaces"
            elif ec_indent_style == "tab":
                self.indent_type = "tabs"

        ec_indent = ec.get("indent_size")
        if ec_indent == "tab":
            ec_indent = ec.get("tab_width")
        if not ec_indent and ec_indent_style == "tab":
            ec_indent = ec.get("tab_width")
        if ec_indent and ec_indent != "unset":
            with contextlib.suppress(ValueError):
                size = int(ec_indent)
                if size in (2, 4, 8):
                    if init_all:
                        self.set_reactive(CodeEditor.indent_size, size)
                    else:
                        self.indent_size = size

        if init_all:
            ec_charset = ec.get("charset")
            if ec_charset and ec_charset != "unset":
                enc = _CHARSET_MAP.get(ec_charset)
                if enc:
                    self.set_reactive(CodeEditor.encoding, enc)

            ec_eol = ec.get("end_of_line")
            if ec_eol and ec_eol != "unset" and ec_eol in ("lf", "crlf", "cr"):
                self.set_reactive(CodeEditor.line_ending, ec_eol)

        ec_trim = ec.get("trim_trailing_whitespace")
        if ec_trim == "true":
            self._trim_trailing_whitespace = True
        elif ec_trim == "false":
            self._trim_trailing_whitespace = False
        elif not init_all:
            self._trim_trailing_whitespace = None

        ec_final_newline = ec.get("insert_final_newline")
        if ec_final_newline == "true":
            self._insert_final_newline = True
        elif ec_final_newline == "false":
            self._insert_final_newline = False
        elif not init_all:
            self._insert_final_newline = None

    def compose(self) -> ComposeResult:
        yield FindReplaceBar()
        # Custom languages require register_language() before use;
        # pass None and let watch_language() handle registration.
        lang = None if self.language in _CUSTOM_LANGUAGES else self.language
        yield MultiCursorTextArea.code_editor(
            text=self.text,
            language=lang,
            tab_behavior="focus",
        )

    def _notify_footer(self) -> None:
        """Post FooterStateChanged so MainView can update the global footer."""
        self.post_message(self.FooterStateChanged(self))

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        if event.widget is self.editor:
            self._notify_footer()

    @on(Mount)
    def on_mount(self, event: Mount) -> None:
        # update the title of the editor
        self.update_title()
        # apply syntax highlighting theme
        self._ensure_theme_registered(self._syntax_theme)
        self.editor.theme = self._syntax_theme
        # apply word wrap (reactive init=False, so set manually)
        self.editor.soft_wrap = self.word_wrap
        # apply indentation guides (reactive init=False, so set manually)
        self.editor._show_indentation_guides = self.show_indentation_guides
        # apply render whitespace (reactive init=False, so set manually)
        self.editor._render_whitespace = self.render_whitespace
        # apply indent settings (reactive init=False, so set manually)
        self.editor.indent_width = self.indent_size
        self.editor.indent_type = self.indent_type
        if self._is_restoring:
            # Language was set via set_reactive; apply it to the editor widget
            self.watch_language(self.language)
            if self._restore_cursor is not None:
                self.editor.cursor_location = self._restore_cursor
                self._restore_cursor = None
            if self._restore_scroll is not None:
                x, y = self._restore_scroll
                self.editor.scroll_to(x, y, animate=False)
                self._restore_scroll = None
            self._is_restoring = False
        else:
            # update the language of the editor (triggers lazy language registration)
            self.load_language_from_path(self.path)
        # Start background git diff computation
        self._refresh_git_diff()

    # ── git diff gutter ──────────────────────────────────────────────────────

    @work(thread=True, exclusive=True, group="git_diff")
    def _refresh_git_diff(self) -> None:
        """Fetch HEAD content in a background thread and compute line diff."""
        head_lines = self._fetch_head_lines()
        self.app.call_from_thread(self._apply_git_diff, head_lines)

    def _fetch_head_lines(self) -> list[str] | None:
        """Return HEAD lines for the current file, or None to clear indicators."""
        if self.path is None:
            return None
        app = self.app
        if hasattr(app, "default_show_git_status") and not app.default_show_git_status:
            return None
        head_content = _get_git_head_content(self.path)
        if head_content is None:
            return None
        return head_content.splitlines()

    def _apply_git_diff(self, head_lines: list[str] | None) -> None:
        """Apply git diff results on the main thread."""
        if not self.is_mounted:
            return
        self._git_head_lines = head_lines
        self._recompute_git_diff()

    def _recompute_git_diff(self) -> None:
        """Recompute line changes using cached HEAD lines and current text."""
        if self._git_head_lines is None:
            if self.editor._line_changes:
                self.editor.set_line_changes({})
            return
        current_lines = self.editor.text.splitlines()
        changes = _compute_line_changes(self._git_head_lines, current_lines)
        log.debug("git diff: %d changes for %s", len(changes), self.path)
        self.editor.set_line_changes(changes)

    def update_title(self) -> None:
        """
        Update the title of the editor.

        The title is the name of the file, with an asterisk (*) if there are unsaved.
        If the file path is not set, the title is "<Untitled>".
        """
        is_changed = False
        if self.text != self.initial_text:
            is_changed = True
        name = "<Untitled>"
        if self.path is not None:
            name = self.path.name
        self.title = f"{name}{'*' if is_changed else ''}"

    def load_language_from_path(self, path: Path | None) -> None:
        """
        Update the language of the editor based on the file name or extension.
        """
        if path is None:
            self.language = None
            return
        # Check full filename first (for files like .bashrc with no extension)
        filename = path.name
        if filename in self.LANGUAGE_FILENAMES:
            self.language = self.LANGUAGE_FILENAMES[filename]
            return
        # Fall back to extension
        extension = path.suffix.lstrip(".")
        self.language = self.LANGUAGE_EXTENSIONS.get(extension, None)

    def replace_editor_text(self, text: str) -> None:
        """
        Replace the text in the editor with the new text.
        """

        self.editor.replace(
            text,
            self.editor.document.start,
            self.editor.document.end,
        )

    def sync_text(self, text: str) -> None:
        """Sync text from another editor editing the same file. Preserves cursor."""
        if self.editor.text == text:
            return
        selection = self.editor.selection
        self.replace_editor_text(text)
        self.editor.selection = selection

    def watch_title(self, title: str) -> None:
        # notify that the title has changed
        # this will update the tab title in the MainView
        self.post_message(
            self.TitleChanged(
                code_editor=self,
            )
        )

    def watch_text(self, text: str) -> None:
        # update the title, as the text has changed
        self.update_title()
        self.post_message(self.TextChanged(self))

    def watch_initial_text(self, initial_text: str) -> None:
        # update the title, as the initial text has changed
        self.update_title()
        # replace the text in the editor with the new initial text
        self.replace_editor_text(initial_text)

    def watch_path(self, path: Path | None) -> None:
        # update the title, as the path has changed
        self.update_title()

        # update the language based on the new path
        self.load_language_from_path(path)

        self._notify_footer()

    def watch_language(self, language: str | None):
        # Always register custom tree-sitter language to override Textual built-ins
        if language and language in _CUSTOM_LANGUAGES:
            query = _CUSTOM_LANGUAGE_QUERIES.get(language, "")
            try:
                self.editor.register_language(
                    language, _CUSTOM_LANGUAGES[language], query
                )
            except Exception as e:
                log.warning("Failed to register language %s: %s", language, e)
        # update the language in the editor
        self.editor.language = language
        self._notify_footer()

    def watch_line_ending(self, line_ending: str) -> None:
        self._notified_copy_line_ending = False
        self._notify_footer()

    def watch_encoding(self, encoding: str) -> None:
        self._notify_footer()

    def watch_indent_type(self, indent_type: str) -> None:
        self.editor.indent_type = indent_type
        self._notify_footer()

    def watch_indent_size(self, indent_size: int) -> None:
        self.editor.indent_width = indent_size
        self._notify_footer()

    def watch_word_wrap(self, value: bool) -> None:
        self.editor.soft_wrap = value

    def action_toggle_word_wrap(self) -> None:
        """Toggle word wrap for the current file."""
        self.word_wrap = not self.word_wrap

    def watch_show_indentation_guides(self, value: bool) -> None:
        self.editor._show_indentation_guides = value
        # Private API dependency: clear Textual's internal line cache so
        # the rendering update takes effect immediately.
        self.editor._line_cache.clear()
        self.editor.refresh()

    def action_toggle_indentation_guides(self) -> None:
        """Toggle indentation guides for the current file."""
        self.show_indentation_guides = not self.show_indentation_guides

    def watch_render_whitespace(self, value: str) -> None:
        self.editor._render_whitespace = value
        self.editor._line_cache.clear()
        self.editor.refresh()

    _RENDER_WHITESPACE_MODES = ("none", "all", "boundary", "trailing")

    def action_cycle_render_whitespace(self) -> None:
        """Cycle through whitespace rendering modes."""
        modes = self._RENDER_WHITESPACE_MODES
        try:
            idx = modes.index(self.render_whitespace)
        except ValueError:
            idx = -1
        new_mode = modes[(idx + 1) % len(modes)]
        self.render_whitespace = new_mode
        self.notify(f"Render whitespace: {new_mode}")

    def _notify_non_lf_if_needed(self, *, from_clipboard: bool = False) -> None:
        if not self._warn_line_ending:
            return
        if self.line_ending == "lf":
            return
        if from_clipboard and self._notified_copy_line_ending:
            return
        self.notify(
            _LINE_ENDING_WARNING.format(ending=self.line_ending.upper()),
            severity="warning",
        )
        if from_clipboard:
            self._notified_copy_line_ending = True

    def _poll_file_change(self) -> None:
        """Check if file was modified externally; auto-reload if no unsaved changes."""
        if self.path is None or self._file_mtime is None:
            return
        try:
            current_mtime = self.path.stat().st_mtime
        except OSError:
            return
        if current_mtime == self._file_mtime:
            return
        if self.text != self.initial_text:
            if self._external_change_notification is None:
                notification = Notification(
                    "File changed externally. Reload to apply changes.",
                    severity="warning",
                    timeout=float("inf"),
                )
                self._external_change_notification = notification
                self.app.post_message(Notify(notification))
        else:
            self._reload_file()

    def _poll_editorconfig_change(self) -> None:
        """Check if any .editorconfig in the chain has changed; re-apply if so."""
        if self.path is None or not self._ec_search_dirs:
            return
        current = _snapshot_editorconfig_mtimes(self._ec_search_dirs)
        if current != self._ec_mtimes:
            self._apply_editorconfig_changes()

    def _apply_editorconfig_changes(self) -> None:
        """Re-read and re-apply editorconfig properties (safe-to-change only)."""
        if self.path is None:
            return
        ec, self._ec_search_dirs = _read_editorconfig(self.path)
        self._ec_mtimes = _snapshot_editorconfig_mtimes(self._ec_search_dirs)
        self._apply_editorconfig(ec, init_all=False)
        self.notify("EditorConfig updated.", severity="information")

    def _dismiss_external_change_notification(self) -> None:
        """Dismiss the external-change toast if one is currently displayed."""
        if self._external_change_notification is not None:
            self.app._unnotify(self._external_change_notification)
            self._external_change_notification = None

    def _reload_file(self) -> None:
        """Reload file content from disk, resetting unsaved state."""
        self._dismiss_external_change_notification()
        if self.path is None:
            return
        try:
            raw_bytes = self.path.read_bytes()
        except OSError as e:
            self.notify(f"Error reloading file: {e}", severity="error")
            return
        detected_encoding = _detect_encoding(raw_bytes)
        try:
            raw_text = raw_bytes.decode(detected_encoding)
        except Exception:
            raw_text = raw_bytes.decode("latin-1", errors="replace")
        detected = _detect_line_ending(raw_text)
        text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        if text.startswith("\ufeff"):
            text = text[1:]
        self.encoding = detected_encoding
        self.line_ending = detected
        self.initial_text = text  # triggers watch_initial_text → replace_editor_text
        self.text = text  # sync reactive so text == initial_text immediately
        with contextlib.suppress(OSError):
            self._file_mtime = self.path.stat().st_mtime
        self.notify("File reloaded.", severity="information")

    def action_revert_file(self) -> None:
        """Manually reload the current file from disk."""
        if self.path is None:
            self.notify("No file to reload.", severity="error")
            return
        if self.text != self.initial_text:

            def do_reload(result: DiscardAndReloadModalResult | None) -> None:
                if result is None or result.is_cancelled or not result.should_reload:
                    return
                self._reload_file()

            self.app.push_screen(DiscardAndReloadModalScreen(), do_reload)
            return
        self._reload_file()

    def _apply_save_transformations(self, text: str) -> str:
        """Apply EditorConfig save-time transformations to text.

        Order: trim_trailing_whitespace first, then insert_final_newline.
        Operates on LF-normalized text (before line ending conversion).
        """
        if self._trim_trailing_whitespace is True:
            text = _trim_trailing_whitespace(text)
        if self._insert_final_newline is True:
            text = _insert_final_newline(text)
        elif self._insert_final_newline is False:
            text = _remove_final_newline(text)
        return text

    def _write_to_disk(self) -> None:
        """Write current text to disk and update mtime. Requires self.path is set."""
        assert self.path is not None
        self._dismiss_external_change_notification()
        try:
            saved_text = self._apply_save_transformations(self.text)
            content = _convert_line_ending(saved_text, self.line_ending)
            self.path.write_bytes(content.encode(self.encoding))
            if saved_text != self.text:
                self.text = saved_text
                self.replace_editor_text(saved_text)
            self.initial_text = self.text
            with contextlib.suppress(OSError):
                self._file_mtime = self.path.stat().st_mtime
            self.notify("File saved", severity="information")
            self.post_message(self.Saved(code_editor=self))
        except Exception as e:
            self.notify(f"Error saving file: {e}", severity="error")

    def action_save(self) -> None:
        """
        Save the current text to the file.
        """
        if self.path is None:
            self.action_save_as()
            return
        # Check for external changes before saving
        try:
            current_mtime = self.path.stat().st_mtime
        except OSError:
            current_mtime = None
        if (
            current_mtime is not None
            and self._file_mtime is not None
            and current_mtime != self._file_mtime
        ):

            def do_overwrite(result: OverwriteConfirmModalResult | None) -> None:
                if result is None or result.is_cancelled or not result.should_overwrite:
                    return
                self._write_to_disk()

            self.app.push_screen(OverwriteConfirmModalScreen(), do_overwrite)
            return
        self._write_to_disk()

    def action_save_as(self, *, on_complete: Callable | None = None) -> None:
        """
        Save the current text to a new file.
        """

        def do_save_as(result: SaveAsModalResult | None) -> None:
            if result is None or result.is_cancelled:
                if on_complete:
                    on_complete()
                return

            if result.file_path is None:
                self.notify("File path cannot be empty", severity="error")
                if on_complete:
                    on_complete()
                return

            new_path = Path(result.file_path).resolve()
            if new_path.exists():
                self.notify("File already exists", severity="error")
                if on_complete:
                    on_complete()
                return

            try:
                saved_text = self._apply_save_transformations(self.text)
                content = _convert_line_ending(saved_text, self.line_ending)
                new_path.write_bytes(content.encode(self.encoding))
                if saved_text != self.text:
                    self.text = saved_text
                    self.replace_editor_text(saved_text)
                self.initial_text = self.text
                self.path = new_path
                with contextlib.suppress(OSError):
                    self._file_mtime = new_path.stat().st_mtime
                self.post_message(
                    self.SavedAs(
                        code_editor=self,
                    )
                )
                self.notify(f"File saved: {self.path}", severity="information")
            except Exception as e:
                self.notify(f"Error saving file: {e}", severity="error")
                if on_complete:
                    on_complete()
                return

            if on_complete:
                on_complete()

        self.app.push_screen(SaveAsModalScreen(), do_save_as)
        return

    def action_close(
        self, *, on_complete: Callable[[bool], None] | None = None
    ) -> None:
        """
        Close the editor.
        """

        def do_unsaved_changes(result: UnsavedChangeModalResult | None) -> None:
            if result is None or result.is_cancelled:
                if on_complete:
                    on_complete(False)
                return

            if result.should_save is None:
                self.notify("Please select an option", severity="error")
                if on_complete:
                    on_complete(False)
                return

            if result.should_save:
                if self.path is None:
                    self.notify(
                        "Cannot save: no file path. Use 'Save As' first.",
                        severity="error",
                    )
                    if on_complete:
                        on_complete(False)
                    return
                self.action_save()
                if self.text == self.initial_text:
                    self.post_message(self.Closed(code_editor=self))
                    if on_complete:
                        on_complete(True)
                    return
                else:
                    if on_complete:
                        on_complete(False)
                    return
            else:
                self.post_message(self.Closed(code_editor=self))
                if on_complete:
                    on_complete(True)
                return

        if self.text != self.initial_text:
            self.app.push_screen(UnsavedChangeModalScreen(), do_unsaved_changes)
            return

        self.post_message(self.Closed(code_editor=self))
        if on_complete:
            on_complete(True)

    def action_delete(self) -> None:
        """
        Delete the file.
        """
        if not self.path:
            self.notify(
                "No file to delete. Please save the file first.", severity="error"
            )
            return

        def do_delete(result: DeleteFileModalResult | None) -> None:
            if not result or result.is_cancelled:
                return
            if not self.path:
                self.notify(
                    "No file to delete. Please save the file first.", severity="error"
                )
                return
            if result.should_delete:
                try:
                    self.path.unlink()
                    self.notify(f"File deleted: {self.path}", severity="information")
                    self.post_message(
                        self.Deleted(
                            code_editor=self,
                        )
                    )
                except Exception as e:
                    self.notify(f"Error deleting file: {e}", severity="error")

        assert self.path is not None
        self.app.push_screen(DeleteFileModalScreen(self.path), do_delete)

    def action_goto_line(self) -> None:
        """
        Open the Goto Line modal and move the cursor to the specified location.
        """

        def do_goto(result: GotoLineModalResult | None) -> None:
            if not result or result.is_cancelled or not result.value:
                return
            try:
                parts = result.value.split(":")
                row = int(parts[0]) - 1
                col = int(parts[1]) - 1 if len(parts) > 1 else 0
            except ValueError:
                self.notify(
                    "Invalid location format. Use 'line' or 'line:col'.",
                    severity="error",
                )
                return
            line_count = len(self.editor.document.lines)
            if row < 0 or row >= line_count:
                self.notify(
                    f"Line {row + 1} is out of range (1–{line_count}).",
                    severity="error",
                )
                return
            col = max(0, col)
            self.editor.cursor_location = (row, col)

        self.app.push_screen(GotoLineModalScreen(), do_goto)

    def action_find(self) -> None:
        """Show the inline find bar in find mode."""
        self._find_offset = None
        self.query_one(FindReplaceBar).show_find()

    def action_replace(self) -> None:
        """Show the inline find/replace bar in replace mode."""
        self._find_offset = None
        self.query_one(FindReplaceBar).show_replace()

    def on_find_replace_bar_find_next(self, event: FindReplaceBar.FindNext) -> None:
        if not event.query:
            return

        from textual.widgets.text_area import Selection

        query = event.query
        text = self.text

        # Use tracked offset for sequential finds; fall back to cursor position
        if self._find_offset is not None:
            cursor_offset = self._find_offset
        else:
            cursor_row, cursor_col = self.editor.cursor_location
            lines = text.split("\n")
            cursor_offset = (
                sum(len(lines[i]) + 1 for i in range(cursor_row)) + cursor_col
            )

        try:
            start_idx, end_idx = _find_next(
                text, query, cursor_offset, event.use_regex, event.case_sensitive
            )
        except re.error as e:
            self.notify(f"Invalid regex: {e}", severity="error")
            return

        if start_idx == -1:
            self._find_offset = None
            self.notify(f"'{query}' not found", severity="warning")
            return

        self._find_offset = end_idx
        self.editor.selection = Selection(
            start=_text_offset_to_location(text, start_idx),
            end=_text_offset_to_location(text, end_idx),
        )

    def on_find_replace_bar_find_previous(
        self, event: FindReplaceBar.FindPrevious
    ) -> None:
        if not event.query:
            return

        from textual.widgets.text_area import Selection

        query = event.query
        text = self.text

        # Use tracked offset for sequential finds; fall back to cursor position
        if self._find_offset is not None:
            cursor_offset = self._find_offset
        else:
            cursor_row, cursor_col = self.editor.cursor_location
            lines = text.split("\n")
            cursor_offset = (
                sum(len(lines[i]) + 1 for i in range(cursor_row)) + cursor_col
            )

        try:
            start_idx, end_idx = _find_previous(
                text, query, cursor_offset, event.use_regex, event.case_sensitive
            )
        except re.error as e:
            self.notify(f"Invalid regex: {e}", severity="error")
            return

        if start_idx == -1:
            self._find_offset = None
            self.notify(f"'{query}' not found", severity="warning")
            return

        self._find_offset = start_idx
        self.editor.selection = Selection(
            start=_text_offset_to_location(text, start_idx),
            end=_text_offset_to_location(text, end_idx),
        )

    def on_find_replace_bar_replace_all(self, event: FindReplaceBar.ReplaceAll) -> None:
        if not event.query:
            return

        find_query = event.query
        replacement = event.replacement
        use_regex = event.use_regex
        case_sensitive = event.case_sensitive
        flags = 0 if case_sensitive else re.IGNORECASE
        if use_regex:
            flags |= re.MULTILINE
        try:
            pattern = re.compile(
                find_query if use_regex else re.escape(find_query), flags
            )
            count = len(pattern.findall(self.text))
            if count == 0:
                self.notify(f"'{find_query}' not found", severity="warning")
                return
            new_text = pattern.sub(replacement, self.text)
        except re.error as e:
            self.notify(f"Invalid regex: {e}", severity="error")
            return
        self.replace_editor_text(new_text)
        self.notify(f"Replaced {count} occurrence(s)", severity="information")

    def on_find_replace_bar_replace_current(
        self, event: FindReplaceBar.ReplaceCurrent
    ) -> None:
        if not event.query:
            return

        from textual.widgets.text_area import Selection

        find_query = event.query
        replacement = event.replacement
        use_regex = event.use_regex
        case_sensitive = event.case_sensitive
        flags = 0 if case_sensitive else re.IGNORECASE
        if use_regex:
            flags |= re.MULTILINE

        sel = self.editor.selection
        text = self.text
        lines = text.split("\n")
        start_offset = (
            sum(len(lines[i]) + 1 for i in range(sel.start[0])) + sel.start[1]
        )
        end_offset = sum(len(lines[i]) + 1 for i in range(sel.end[0])) + sel.end[1]

        try:
            # Match against full text so lookaheads/lookbehinds can see context
            pattern = re.compile(
                find_query if use_regex else re.escape(find_query), flags
            )
            m = pattern.match(text, start_offset)
        except re.error as e:
            self.notify(f"Invalid regex: {e}", severity="error")
            return

        if m is not None and m.end() == end_offset:
            try:
                # Use match.expand() to process backreferences with full
                # text context — re.sub on isolated selected_text would
                # break lookaheads/lookbehinds that need surrounding text.
                rep = m.expand(replacement)
            except (re.error, IndexError):
                rep = replacement
            new_text = text[:start_offset] + rep + text[end_offset:]
            search_from = start_offset + len(rep)
            try:
                start_idx, end_idx = _find_next(
                    new_text, find_query, search_from, use_regex, case_sensitive
                )
            except re.error:
                start_idx = -1
                end_idx = -1
            self.replace_editor_text(new_text)
            if start_idx != -1:
                self.editor.selection = Selection(
                    start=_text_offset_to_location(new_text, start_idx),
                    end=_text_offset_to_location(new_text, end_idx),
                )
        else:
            cursor_row, cursor_col = self.editor.cursor_location
            lines = text.split("\n")
            cursor_offset = (
                sum(len(lines[i]) + 1 for i in range(cursor_row)) + cursor_col
            )
            try:
                start_idx, end_idx = _find_next(
                    text, find_query, cursor_offset, use_regex, case_sensitive
                )
            except re.error as e:
                self.notify(f"Invalid regex: {e}", severity="error")
                return
            if start_idx == -1:
                self.notify(f"'{find_query}' not found", severity="warning")
                return
            self.editor.selection = Selection(
                start=_text_offset_to_location(text, start_idx),
                end=_text_offset_to_location(text, end_idx),
            )

    def on_find_replace_bar_closed(self, event: FindReplaceBar.Closed) -> None:
        self._find_offset = None
        self.editor.focus()

    def on_find_replace_bar_select_all(self, event: FindReplaceBar.SelectAll) -> None:
        if not event.query:
            return

        text = self.text
        flags = 0 if event.case_sensitive else re.IGNORECASE
        if event.use_regex:
            flags |= re.MULTILINE
        try:
            pattern = re.compile(
                event.query if event.use_regex else re.escape(event.query), flags
            )
        except re.error as e:
            self.notify(f"Invalid regex: {e}", severity="error")
            return

        matches = list(pattern.finditer(text))
        count = self._apply_matches_as_cursors(matches, text)

        self._find_offset = None
        self.editor.focus()

        if count == 0:
            self.notify(f"'{event.query}' not found", severity="warning")
        elif count >= 2:
            self.notify(f"{count} occurrences selected")

    def action_change_language(self) -> None:
        """
        Open the Change Language modal and update the syntax highlighting language.
        """
        languages = sorted(
            set(self.LANGUAGE_EXTENSIONS.values())
            | set(self.LANGUAGE_FILENAMES.values())
        )

        def do_change(result: ChangeLanguageModalResult | None) -> None:
            if result is None or result.is_cancelled:
                return
            self.language = result.language

        self.app.push_screen(
            ChangeLanguageModalScreen(
                languages=languages,
                current_language=self.language,
            ),
            do_change,
        )

    def action_change_indent(self) -> None:
        """
        Open the Change Indentation modal and convert the file's indentation.
        """

        def do_change(result: ChangeIndentModalResult | None) -> None:
            if result is None or result.is_cancelled:
                return
            if result.indent_type is None or result.indent_size is None:
                return
            new_text = _convert_indentation(
                self.text, result.indent_type, result.indent_size
            )
            self.replace_editor_text(new_text)
            self.indent_type = result.indent_type
            self.indent_size = result.indent_size

        self.app.push_screen(
            ChangeIndentModalScreen(
                self.indent_type, self.indent_size, show_save_level=False
            ),
            do_change,
        )

    def action_change_line_ending(self) -> None:
        """
        Open the Change Line Ending modal and update the line ending style.
        """

        def do_change(result: ChangeLineEndingModalResult | None) -> None:
            if result is None or result.is_cancelled:
                return
            if result.line_ending is None:
                return
            self.line_ending = result.line_ending
            self._notify_non_lf_if_needed()

        self.app.push_screen(
            ChangeLineEndingModalScreen(
                current_line_ending=self.line_ending, show_save_level=False
            ),
            do_change,
        )

    def action_change_encoding(self) -> None:
        """
        Open the Change Encoding modal and update the file encoding.
        """

        def do_change(result: ChangeEncodingModalResult | None) -> None:
            if result is None or result.is_cancelled:
                return
            if result.encoding is None:
                return
            self.encoding = result.encoding

        self.app.push_screen(
            ChangeEncodingModalScreen(
                current_encoding=self.encoding, show_save_level=False
            ),
            do_change,
        )

    def action_focus(self) -> None:
        """
        Focus the editor.
        """
        self.editor.focus()

    @on(TextArea.Changed)
    def on_text_changed(self, event: TextArea.Changed):
        event.stop()

        # update the text when editor's text changes
        self.text = event.control.text
        # Recompute git diff using cached HEAD (no subprocess)
        self._recompute_git_diff()

    @on(TextArea.SelectionChanged)
    def on_selection_changed(self, event: TextArea.SelectionChanged):
        event.stop()
        self._notify_footer()

    @on(MultiCursorTextArea.CursorsChanged)
    def on_cursors_changed(self, event: MultiCursorTextArea.CursorsChanged):
        event.stop()
        self._notify_footer()
        # Reset Ctrl+D word mode when extra cursors are cleared (e.g. Escape)
        if not self.editor.extra_cursors:
            self._ctrl_d_query = ""

    @on(MultiCursorTextArea.ClipboardAction)
    def on_clipboard_action(self, event: MultiCursorTextArea.ClipboardAction) -> None:
        event.stop()
        self._notify_non_lf_if_needed(from_clipboard=True)

    def action_add_cursor_below(self) -> None:
        """Add an extra cursor one line below the primary cursor."""
        row, col = self.editor.cursor_location
        if row < self.editor.document.line_count - 1:
            self.editor.add_cursor((row + 1, col))

    def action_add_cursor_above(self) -> None:
        """Add an extra cursor one line above the primary cursor."""
        row, col = self.editor.cursor_location
        if row > 0:
            self.editor.add_cursor((row - 1, col))

    def _get_query_text(self) -> str:
        """Return selected text, or word under cursor if no selection."""
        sel = self.editor.selection
        if sel.start != sel.end:
            return self.editor.selected_text
        row, col = self.editor.cursor_location
        return _get_word_at_location(self.text, row, col)

    def _apply_matches_as_cursors(self, matches: list[re.Match], text: str) -> int:
        """Set primary selection to first match, add extra cursors for the rest.

        Zero-length matches are silently skipped.
        Returns the number of matches applied.
        """
        from textual.widgets.text_area import Selection

        self.editor.clear_extra_cursors()

        matches = [m for m in matches if m.start() < m.end()]
        if not matches:
            return 0

        first = matches[0]
        self.editor.selection = Selection(
            start=_text_offset_to_location(text, first.start()),
            end=_text_offset_to_location(text, first.end()),
        )

        for m in matches[1:]:
            self.editor.add_cursor(
                _text_offset_to_location(text, m.end()),
                anchor=_text_offset_to_location(text, m.start()),
            )

        return len(matches)

    def action_select_all_occurrences(self) -> None:
        """Select all occurrences of the current selection or word under cursor.

        Matching VSCode behavior:
        - From collapsed cursor: whole-word, case-sensitive matching.
        - From existing selection: substring, case-insensitive matching.
        """
        sel = self.editor.selection
        from_collapsed = sel.start == sel.end

        query = self._get_query_text()
        if not query:
            return

        text = self.text
        if from_collapsed:
            pattern = re.compile(_word_boundary_pattern(query))
        else:
            pattern = re.compile(re.escape(query), re.IGNORECASE)
        matches = list(pattern.finditer(text))
        count = self._apply_matches_as_cursors(matches, text)
        self._find_offset = None

        if count == 0:
            self.notify(f"'{query}' not found", severity="warning")
        elif count >= 2:
            self.notify(f"{count} occurrences selected")

    def action_select_next_occurrence(self) -> None:
        """Add a cursor at the next occurrence (VS Code Ctrl+D style).

        Two modes, matching VSCode behavior:
        - **Word mode** (from collapsed cursor): case-sensitive, whole-word
          boundary matching. Activated when Ctrl+D first selects a word.
        - **Substring mode** (from existing selection): case-insensitive,
          plain substring matching. Used when user has text selected.
        """
        from textual.widgets.text_area import Selection

        text = self.text
        query = self._get_query_text()
        if not query:
            return

        sel = self.editor.selection

        # Case 1: No selection — select word under cursor (word-boundary mode)
        if sel.start == sel.end:
            self._ctrl_d_query = query
            row, col = self.editor.cursor_location
            line_offset = _location_to_text_offset(text, (row, 0))
            for m in re.finditer(_word_boundary_pattern(query), text):
                if m.start() <= line_offset + col < m.end():
                    self.editor.selection = Selection(
                        start=_text_offset_to_location(text, m.start()),
                        end=_text_offset_to_location(text, m.end()),
                    )
                    return
            return

        # Case 2: Selection exists — find next occurrence
        # Reset word mode if the selected text changed (user selected manually)
        if self._ctrl_d_query and self.editor.selected_text != self._ctrl_d_query:
            self._ctrl_d_query = ""

        if self.editor.extra_cursors:
            last_cursor = self.editor.extra_cursors[-1]
            last_anchor = self.editor.extra_anchors[-1]
            search_from = _location_to_text_offset(text, max(last_cursor, last_anchor))
        else:
            search_from = _location_to_text_offset(text, max(sel.start, sel.end))

        if self._ctrl_d_query:
            start, end = _find_next(
                text,
                _word_boundary_pattern(query),
                search_from,
                use_regex=True,
                case_sensitive=True,
            )
        else:
            start, end = _find_next(text, query, search_from, case_sensitive=False)

        if start == -1:
            return

        match_start = _text_offset_to_location(text, start)
        match_end = _text_offset_to_location(text, end)

        # Check if match is already selected (primary or any extra cursor)
        primary_start = min(sel.start, sel.end)
        primary_end = max(sel.start, sel.end)
        if match_start == primary_start and match_end == primary_end:
            self.notify(
                "All occurrences already selected",
                severity="information",
            )
            return
        for ec, ea in zip(
            self.editor.extra_cursors,
            self.editor.extra_anchors,
            strict=True,
        ):
            if min(ec, ea) == match_start and max(ec, ea) == match_end:
                self.notify(
                    "All occurrences already selected",
                    severity="information",
                )
                return

        # Match extra cursor direction to primary selection
        cursor, anchor = (
            (match_start, match_end)
            if sel.start > sel.end
            else (match_end, match_start)
        )
        self.editor.add_cursor(cursor, anchor=anchor)
        self._scroll_to_location(cursor)

    def _scroll_to_location(self, location: tuple[int, int]) -> None:
        """Scroll the editor viewport to make *location* visible."""
        from textual.geometry import Region, Spacing

        x, y = self.editor.wrapped_document.location_to_offset(location)
        self.editor.scroll_to_region(
            Region(x, y, width=3, height=1),
            spacing=Spacing(right=self.editor.gutter_width),
            animate=False,
            force=True,
        )

    @property
    def editor(self) -> MultiCursorTextArea:
        return self.query_one(MultiCursorTextArea)

    @property
    def syntax_theme(self) -> str:
        """Return the current syntax highlighting theme."""
        return self._syntax_theme

    @syntax_theme.setter
    def syntax_theme(self, theme: str) -> None:
        """Set the syntax highlighting theme and update the editor."""
        self._syntax_theme = theme
        self._ensure_theme_registered(theme)
        self.editor.theme = theme

    def _ensure_theme_registered(self, theme: str) -> None:
        """Lazily convert and register a Pygments theme if not already known."""
        if theme in self.editor.available_themes:
            return
        try:
            from textual_code.pygments_theme_converter import (
                pygments_to_textarea_theme,
            )

            ta_theme = pygments_to_textarea_theme(theme)
            self.editor.register_theme(ta_theme)
        except Exception:
            log.warning("Failed to register theme %s", theme)

    def capture_state(self) -> EditorState:
        """Serialize current editor state for lazy unmounting."""
        try:
            scroll = (int(self.editor.scroll_x), int(self.editor.scroll_y))
            cursor = self.editor.selection.end
        except Exception:
            scroll = (0, 0)
            cursor = (0, 0)
        state = EditorState(
            pane_id=self.pane_id,
            path=self.path,
            text=self.text,
            initial_text=self.initial_text,
            language=self.language,
            encoding=self.encoding,
            line_ending=self.line_ending,
            indent_type=self.indent_type,
            indent_size=self.indent_size,
            word_wrap=self.word_wrap,
            show_indentation_guides=self.show_indentation_guides,
            render_whitespace=self.render_whitespace,
            cursor_end=cursor,
            scroll_offset=scroll,
            file_mtime=self._file_mtime,
            ec_search_dirs=list(self._ec_search_dirs),
            ec_mtimes=dict(self._ec_mtimes),
            trim_trailing_whitespace=self._trim_trailing_whitespace,
            insert_final_newline=self._insert_final_newline,
            syntax_theme=self._syntax_theme,
            warn_line_ending=self._warn_line_ending,
            notified_copy_line_ending=self._notified_copy_line_ending,
        )
        log.debug("capture_state: pane=%s path=%s", state.pane_id, state.path)
        return state

    @classmethod
    def from_state(cls, state: EditorState) -> CodeEditor:
        """Create a CodeEditor from a captured EditorState (no file I/O)."""
        log.debug("from_state: pane=%s path=%s", state.pane_id, state.path)
        return cls(
            pane_id=state.pane_id,
            path=state.path,
            _from_state=state,
        )

    @staticmethod
    def save_from_state(state: EditorState) -> None:
        """Save an unmounted editor's state to disk.

        Applies save-time transformations and updates state.initial_text
        and state.file_mtime in place.
        """
        if state.path is None:
            return
        try:
            text = state.text
            if state.trim_trailing_whitespace is True:
                text = _trim_trailing_whitespace(text)
            if state.insert_final_newline is True:
                text = _insert_final_newline(text)
            elif state.insert_final_newline is False:
                text = _remove_final_newline(text)
            content = _convert_line_ending(text, state.line_ending)
            state.path.write_bytes(content.encode(state.encoding))
            if text != state.text:
                state.text = text
            state.initial_text = state.text
            with contextlib.suppress(OSError):
                state.file_mtime = state.path.stat().st_mtime
            log.debug("save_from_state: saved %s", state.path)
        except Exception as e:
            log.error("save_from_state: error saving %s: %s", state.path, e)
