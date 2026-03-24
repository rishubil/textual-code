"""Tests ported from VSCode's findModel.test.ts.

Source: src/vs/editor/contrib/find/test/browser/findModel.test.ts
Ported areas: regex find/replace patterns not covered by test_regex_search.py.

Key coverage gaps filled:
- Regex multiline anchors (^, $) — requires re.MULTILINE in regex mode
- Regex lookahead in find and replace operations
- Regex capturing groups in replace (\\1 Python syntax)
- Overlapping and adjacent match replacement
- Select all matches via find bar handler
- Edge cases from VSCode issue regressions (#19740, #32522, #18711)

Behavioral differences from VSCode:
- Capture group syntax: VSCode uses $1, our editor uses \\1 (Python re.sub)
"""

from __future__ import annotations

from pathlib import Path

from tests.conftest import make_app
from textual_code.widgets.code_editor import _find_next, _text_offset_to_location
from textual_code.widgets.find_replace_bar import FindReplaceBar

# ── shared test data ─────────────────────────────────────────────────────────

# Standard text from findModel.test.ts (12 lines, trailing newline)
VSCODE_TEXT = (
    "// my cool header\n"
    '#include "cool.h"\n'
    "#include <iostream>\n"
    "\n"
    "int main() {\n"
    '    cout << "hello world, Hello!" << endl;\n'
    '    cout << "hello world again" << endl;\n'
    '    cout << "Hello world again" << endl;\n'
    '    cout << "helloworld again" << endl;\n'
    "}\n"
    "// blablablaciao\n"
)


def _line_start(text: str, line: int) -> int:
    """Character offset of the start of a 0-based line."""
    offset = 0
    for _ in range(line):
        idx = text.index("\n", offset)
        offset = idx + 1
    return offset


# ── Unit: _find_next regex anchors ───────────────────────────────────────────
# Adapted from findModel.test.ts 'find ^', 'find $', 'find next ^$', 'find .*'


def test_find_next_regex_caret_matches_line_starts():
    """'^' matches start of each line (VSCode 'find ^', line 849).

    Requires re.MULTILINE so ^ anchors at each newline boundary.
    """
    text = VSCODE_TEXT
    # First match: start of line 0
    assert _find_next(text, "^", 0, use_regex=True) == (0, 0)
    # From offset 1: should find start of line 1 (offset 18)
    ls1 = _line_start(text, 1)
    assert _find_next(text, "^", 1, use_regex=True) == (ls1, ls1)
    # From mid-line 1: should find start of line 2
    ls2 = _line_start(text, 2)
    assert _find_next(text, "^", ls1 + 5, use_regex=True) == (ls2, ls2)


def test_find_next_regex_dollar_matches_line_ends():
    """'$' matches end of each line (VSCode 'find $', line 920).

    Requires re.MULTILINE so $ anchors before each newline.
    """
    text = VSCODE_TEXT
    # Line 0: "// my cool header" (17 chars) → $ at offset 17
    assert _find_next(text, "$", 0, use_regex=True) == (17, 17)
    # From offset 18 (line 1 start): $ at end of line 1 (offset 35)
    assert _find_next(text, "$", 18, use_regex=True) == (35, 35)


def test_find_next_regex_caret_dollar_matches_empty_lines():
    """'^$' matches only empty lines (VSCode 'find next ^$', line 1012).

    VSCODE_TEXT has two empty lines: line 3 and line 11 (trailing).
    """
    text = VSCODE_TEXT
    ls3 = _line_start(text, 3)  # empty line
    assert _find_next(text, "^$", 0, use_regex=True) == (ls3, ls3)
    # From past line 3: the trailing empty line (line 11)
    ls11 = _line_start(text, 11)
    assert _find_next(text, "^$", ls3 + 1, use_regex=True) == (ls11, ls11)


def test_find_next_regex_dot_star_matches_line_content():
    """'.*' matches each line's content (VSCode 'find .*', line 1064)."""
    text = VSCODE_TEXT
    start, end = _find_next(text, ".*", 0, use_regex=True)
    assert text[start:end] == "// my cool header"


# ── Unit: _find_next regex lookahead ─────────────────────────────────────────
# Adapted from findModel.test.ts 'replace when search string has look ahed regex'


def test_find_next_regex_lookahead():
    r"""hello(?=\sworld) matches 'hello' only before ' world' (line 1784)."""
    text = VSCODE_TEXT
    # First match: line 5, "hello" at col 13
    start, end = _find_next(text, r"hello(?=\sworld)", 0, use_regex=True)
    assert _text_offset_to_location(text, start) == (5, 13)
    assert _text_offset_to_location(text, end) == (5, 18)
    assert text[start:end] == "hello"

    # Next match: line 6, "hello" at col 13
    start2, end2 = _find_next(text, r"hello(?=\sworld)", end, use_regex=True)
    assert _text_offset_to_location(text, start2) == (6, 13)

    # Next match: line 7, "Hello" — case-sensitive, should NOT match
    # So it should wrap around to line 5 again
    start3, end3 = _find_next(text, r"hello(?=\sworld)", end2, use_regex=True)
    assert _text_offset_to_location(text, start3) == (5, 13)


def test_find_next_regex_lookahead_case_insensitive():
    r"""hello(?=\sworld) with case_sensitive=False also matches 'Hello world'."""
    text = VSCODE_TEXT
    matches = []
    offset = 0
    for _ in range(10):
        s, e = _find_next(
            text,
            r"hello(?=\sworld)",
            offset,
            use_regex=True,
            case_sensitive=False,
        )
        if s == -1 or s in [m[0] for m in matches]:
            break
        matches.append((s, e))
        offset = e
    # Matches: line 5 "hello", line 6 "hello", line 7 "Hello" = 3
    assert len(matches) == 3
    locs = [_text_offset_to_location(text, s) for s, _ in matches]
    assert locs == [(5, 13), (6, 13), (7, 13)]


# ── Unit: case-sensitive find ────────────────────────────────────────────────
# Adapted from findModel.test.ts 'incremental find' lines 155-178


def test_find_next_case_sensitive_hello():
    """'hello' case-sensitive: matches lowercase only (3 occurrences)."""
    text = VSCODE_TEXT
    matches = []
    offset = 0
    for _ in range(10):
        s, e = _find_next(text, "hello", offset, case_sensitive=True)
        if s == -1 or s in [m[0] for m in matches]:
            break
        matches.append((s, e))
        offset = e
    assert len(matches) == 3
    locs = [_text_offset_to_location(text, s) for s, _ in matches]
    assert locs == [(5, 13), (6, 13), (8, 13)]


def test_find_next_case_insensitive_hello():
    """'hello' case-insensitive: matches both hello and Hello (5 occurrences)."""
    text = VSCODE_TEXT
    matches = []
    offset = 0
    for _ in range(10):
        s, e = _find_next(text, "hello", offset, case_sensitive=False)
        if s == -1 or s in [m[0] for m in matches]:
            break
        matches.append((s, e))
        offset = e
    # hello (5,13), Hello (5,26), hello (6,13), Hello (7,13), hello (8,13)
    assert len(matches) == 5


# ── Integration: replace_all ─────────────────────────────────────────────────


async def test_replace_all_regex_lookahead(workspace: Path):
    r"""replaceAll hello(?=\sworld) → hi (findModel.test.ts line 1921)."""
    f = workspace / "test.txt"
    f.write_text(VSCODE_TEXT)
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.on_find_replace_bar_replace_all(
            FindReplaceBar.ReplaceAll(
                query=r"hello(?=\sworld)",
                replacement="hi",
                use_regex=True,
                case_sensitive=True,
            )
        )
        await pilot.pause()

        lines = editor.text.split("\n")
        # "hello" before " world" → "hi"
        assert '"hi world, Hello!"' in lines[5]
        assert '"hi world again"' in lines[6]
        # "Hello world" — case-sensitive, 'H' != 'h' → NOT replaced
        assert '"Hello world again"' in lines[7]
        # "helloworld" — no space before world → NOT replaced
        assert '"helloworld again"' in lines[8]


async def test_replace_all_regex_capturing_groups(workspace: Path):
    r"""replaceAll hel(lo)(?=\sworld) → hi\1 (findModel.test.ts line 2020).

    VSCode uses $1 syntax; our editor uses Python's \1 syntax.
    """
    f = workspace / "test.txt"
    f.write_text(VSCODE_TEXT)
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.on_find_replace_bar_replace_all(
            FindReplaceBar.ReplaceAll(
                query=r"hel(lo)(?=\sworld)",
                replacement=r"hi\1",
                use_regex=True,
                case_sensitive=True,
            )
        )
        await pilot.pause()

        lines = editor.text.split("\n")
        # hel(lo) → hi + lo = "hilo"
        assert '"hilo world, Hello!"' in lines[5]
        assert '"hilo world again"' in lines[6]
        assert '"Hello world again"' in lines[7]  # not replaced


async def test_replace_all_overlapping_two_spaces_to_one(workspace: Path):
    """replaceAll '  ' → ' ' (findModel.test.ts line 1496).

    4-space indent becomes 2-space after replacing each pair of spaces.
    """
    f = workspace / "test.txt"
    f.write_text(VSCODE_TEXT)
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.on_find_replace_bar_replace_all(
            FindReplaceBar.ReplaceAll(
                query="  ",
                replacement=" ",
                use_regex=False,
                case_sensitive=True,
            )
        )
        await pilot.pause()

        lines = editor.text.split("\n")
        # 4 spaces → 2 spaces (two overlapping "  " in "    ")
        assert lines[5].startswith("  cout")
        assert lines[6].startswith("  cout")
        assert lines[7].startswith("  cout")
        assert lines[8].startswith("  cout")


async def test_replace_all_adjacent_bla_to_ciao(workspace: Path):
    """replaceAll 'bla' → 'ciao' in 'blablablaciao' (findModel.test.ts line 1538)."""
    f = workspace / "test.txt"
    f.write_text(VSCODE_TEXT)
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.on_find_replace_bar_replace_all(
            FindReplaceBar.ReplaceAll(
                query="bla",
                replacement="ciao",
                use_regex=False,
                case_sensitive=True,
            )
        )
        await pilot.pause()

        lines = editor.text.split("\n")
        assert lines[10] == "// ciaociaociaociao"


async def test_replace_all_regex_with_newline_tab(workspace: Path):
    r"""replaceAll 'bla' → '<\n\t>' in regex mode (findModel.test.ts line 1567)."""
    f = workspace / "test.txt"
    f.write_text(VSCODE_TEXT)
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.on_find_replace_bar_replace_all(
            FindReplaceBar.ReplaceAll(
                query="bla",
                replacement="<\n\t>",
                use_regex=True,
                case_sensitive=True,
            )
        )
        await pilot.pause()

        # "// blablablaciao" → "// <\n\t><\n\t><\n\t>ciao"
        assert "// <\n\t><\n\t><\n\t>ciao" in editor.text


async def test_replace_all_with_empty_string(workspace: Path):
    """replaceAll 'hello' → '' deletes occurrences (issue #18711, line 2122)."""
    f = workspace / "test.txt"
    f.write_text(VSCODE_TEXT)
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.on_find_replace_bar_replace_all(
            FindReplaceBar.ReplaceAll(
                query="hello",
                replacement="",
                use_regex=False,
                case_sensitive=True,
            )
        )
        await pilot.pause()

        lines = editor.text.split("\n")
        # Only lowercase "hello" removed (case-sensitive)
        assert '" world, Hello!"' in lines[5]
        assert '" world again"' in lines[6]
        assert '"Hello world again"' in lines[7]  # unchanged
        assert '"world again"' in lines[8]


async def test_replace_all_regex_caret_prefix_many_lines(workspace: Path):
    """replaceAll '^' → 'a ' on 1100 lines (issue #32522, line 2154).

    Requires re.MULTILINE for ^ to match each line start.
    """
    content_lines = [f"line{i}" for i in range(1100)]
    content = "\n".join(content_lines) + "\n"
    f = workspace / "big.txt"
    f.write_text(content)
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.on_find_replace_bar_replace_all(
            FindReplaceBar.ReplaceAll(
                query="^",
                replacement="a ",
                use_regex=True,
                case_sensitive=True,
            )
        )
        await pilot.pause()

        result_lines = editor.text.split("\n")
        assert result_lines[0] == "a line0"
        assert result_lines[1] == "a line1"
        assert result_lines[999] == "a line999"
        assert result_lines[1099] == "a line1099"


async def test_replace_all_regex_optional_capture_not_undefined(workspace: Path):
    r"""replaceAll hello(z)? → hi\1: unmatched group = empty (issue #19740, line 2177).

    In JavaScript, unmatched groups become 'undefined' in $1.
    In Python, unmatched groups in \1 produce empty string.
    """
    f = workspace / "test.txt"
    f.write_text(VSCODE_TEXT)
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.on_find_replace_bar_replace_all(
            FindReplaceBar.ReplaceAll(
                query=r"hello(z)?",
                replacement=r"hi\1",
                use_regex=True,
                case_sensitive=True,
            )
        )
        await pilot.pause()

        lines = editor.text.split("\n")
        # "hello" → (z)? unmatched → \1 = "" → "hi"
        assert '"hi world, Hello!"' in lines[5]
        assert '"hi world again"' in lines[6]
        assert '"Hello world again"' in lines[7]  # case-sensitive, not replaced
        assert '"hiworld again"' in lines[8]


# ── Integration: replace_current regex ───────────────────────────────────────


async def test_replace_current_regex_lookahead_sequential(workspace: Path):
    r"""Sequential replace with hello(?=\sworld) → hi (findModel.test.ts line 1784).

    1st call: no match in selection → find next match → select it
    2nd call: selection matches → replace → find next match
    """
    f = workspace / "test.txt"
    f.write_text(VSCODE_TEXT)
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.editor.cursor_location = (0, 0)
        await pilot.pause()

        msg = FindReplaceBar.ReplaceCurrent(
            query=r"hello(?=\sworld)",
            replacement="hi",
            use_regex=True,
            case_sensitive=True,
        )

        # 1st call: find first match (no replacement yet)
        editor.on_find_replace_bar_replace_current(msg)
        await pilot.pause()

        sel = editor.editor.selection
        assert sel.start == (5, 13)
        assert sel.end == (5, 18)
        # Text unchanged
        assert "hello world, Hello!" in editor.text.split("\n")[5]

        # 2nd call: replace "hello" → "hi", then find next match
        editor.on_find_replace_bar_replace_current(msg)
        await pilot.pause()

        lines = editor.text.split("\n")
        assert '"hi world, Hello!"' in lines[5]
        # Next match selected: line 6
        sel = editor.editor.selection
        assert sel.start == (6, 13)
        assert sel.end == (6, 18)


async def test_replace_current_regex_capturing_groups(workspace: Path):
    r"""Sequential replace hel(lo)(?=\sworld) → hi\1 (findModel.test.ts line 1954).

    Each replacement produces "hilo" (hi + captured "lo").
    """
    f = workspace / "test.txt"
    f.write_text(VSCODE_TEXT)
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.editor.cursor_location = (0, 0)
        await pilot.pause()

        msg = FindReplaceBar.ReplaceCurrent(
            query=r"hel(lo)(?=\sworld)",
            replacement=r"hi\1",
            use_regex=True,
            case_sensitive=True,
        )

        # Find first match
        editor.on_find_replace_bar_replace_current(msg)
        await pilot.pause()
        assert editor.editor.selection.start == (5, 13)

        # Replace: hello → hilo
        editor.on_find_replace_bar_replace_current(msg)
        await pilot.pause()
        assert '"hilo world, Hello!"' in editor.text.split("\n")[5]

        # Replace next: line 6 hello → hilo
        editor.on_find_replace_bar_replace_current(msg)
        await pilot.pause()
        assert '"hilo world again"' in editor.text.split("\n")[6]


# ── Integration: select all matches ──────────────────────────────────────────


async def test_select_all_matches_creates_multi_cursors(workspace: Path):
    """selectAllMatches places cursors on all matches (findModel.test.ts line 1658)."""
    f = workspace / "test.txt"
    f.write_text(VSCODE_TEXT)
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.on_find_replace_bar_select_all(
            FindReplaceBar.SelectAll(
                query="hello",
                use_regex=False,
                case_sensitive=True,
            )
        )
        await pilot.pause()

        ta = editor.editor
        # "hello" case-sensitive: 3 matches (lines 5, 6, 8)
        total_cursors = 1 + len(ta.extra_cursors)
        assert total_cursors == 3


async def test_select_all_matches_regex_lookahead(workspace: Path):
    r"""selectAllMatches with lookahead creates cursors on matches only."""
    f = workspace / "test.txt"
    f.write_text(VSCODE_TEXT)
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.on_find_replace_bar_select_all(
            FindReplaceBar.SelectAll(
                query=r"hello(?=\sworld)",
                use_regex=True,
                case_sensitive=True,
            )
        )
        await pilot.pause()

        ta = editor.editor
        # Matches: line 5 "hello" (before " world"), line 6 "hello"
        # NOT line 8 "helloworld" (no space), NOT line 7 "Hello" (case)
        total_cursors = 1 + len(ta.extra_cursors)
        assert total_cursors == 2
