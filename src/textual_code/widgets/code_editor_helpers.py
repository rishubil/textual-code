"""Helper functions for CodeEditor: EditorConfig, text utilities, and search."""

from __future__ import annotations

import re
from pathlib import Path

from charset_normalizer import detect as _cn_detect

from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

# ── EditorConfig support ────────────────────────────────────────────────────


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


# ── Text utilities ──────────────────────────────────────────────────────────

_CHARSET_MAP: dict[str, str] = {
    "utf-8": "utf-8",
    "utf-8-bom": "utf-8-sig",
    "utf-16be": "utf-16",
    "utf-16le": "utf-16",
    "latin1": "latin-1",
}


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


# ── Search / find utilities ─────────────────────────────────────────────────


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
