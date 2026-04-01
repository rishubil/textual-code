"""
Regex search/replace feature tests.

Behaviour spec:
- use_regex=True → search using Python re patterns
- Invalid regex → error notification, no crash
- (?i) inline flag enables case-insensitive search
- Capture groups supported in replace_all (\\1 etc.)
- use_regex=False (default) → plain string search as before (no regression)
"""

from pathlib import Path

import pytest
from textual.widgets import Input

from tests.conftest import make_app, wait_for_condition
from textual_code.widgets.code_editor import _find_next

# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def regex_file(workspace: Path) -> Path:
    """File used for regex tests."""
    f = workspace / "regex_test.txt"
    f.write_text("hello world\nHELLO WORLD\nfoo123 bar456\n")
    return f


# ── _find_next unit tests ─────────────────────────────────────────────────────


def test_find_next_plain_returns_tuple():
    """use_regex=False → returns (start, end) tuple."""
    text = "hello world"
    start, end = _find_next(text, "world", 0, use_regex=False)
    assert start == 6
    assert end == 11


def test_find_next_plain_not_found_returns_minus_one():
    """use_regex=False → returns (-1, -1) when not found."""
    assert _find_next("hello", "xyz", 0, use_regex=False) == (-1, -1)


def test_find_next_regex_basic():
    """use_regex=True → pattern matching."""
    text = "hello world"
    start, end = _find_next(text, r"he.lo", 0, use_regex=True)
    assert start == 0
    assert end == 5


def test_find_next_regex_not_found():
    """use_regex=True → (-1, -1) when pattern not found."""
    assert _find_next("hello", r"xyz.+", 0, use_regex=True) == (-1, -1)


def test_find_next_regex_wrap_around():
    """use_regex=True → wraps around from start when no match after cursor."""
    text = "abc def abc"
    # cursor_offset=4 (at 'd'), 'abc' is found after at offset 8
    start, end = _find_next(text, r"abc", 4, use_regex=True)
    assert start == 8
    assert end == 11


def test_find_next_regex_wrap_around_from_end():
    """No match after cursor but exists before → returns the first match."""
    text = "abc def"
    # cursor_offset=4 → 'abc' not found after cursor → wrap → offset 0
    start, end = _find_next(text, r"abc", 4, use_regex=True)
    assert start == 0
    assert end == 3


def test_find_next_invalid_regex_raises():
    """Invalid regex → raises re.error."""
    import re

    with pytest.raises(re.error):
        _find_next("hello", r"[unclosed", 0, use_regex=True)


# ── regex find integration tests ─────────────────────────────────────────────


async def test_regex_find_matches_dot_pattern(workspace: Path, regex_file: Path):
    """Pattern he.lo selects 'hello'."""
    app = make_app(workspace, open_file=regex_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_find()
        await pilot.pause()
        await pilot.pause()  # Windows: extra pause for find bar rendering

        from textual.widgets import Checkbox

        checkbox = editor.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)
        await pilot.pause()  # Windows: extra pause for checkbox state change

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("h", "e", ".", "l", "o")
        await pilot.pause()  # Windows: extra pause for key presses
        await pilot.click("#next_match")
        await pilot.pause()
        await pilot.pause()  # Windows: extra pause for regex find + selection update

        sel = editor.editor.selection
        assert sel.start == (0, 0)
        assert sel.end == (0, 5)


async def test_regex_find_no_match_shows_warning(workspace: Path, regex_file: Path):
    """No-match regex → cursor does not move (not found)."""
    app = make_app(workspace, open_file=regex_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        original_location = editor.editor.cursor_location

        editor.action_find()
        await pilot.pause()

        from textual.widgets import Checkbox

        checkbox = editor.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("x", "y", "z", ".", "+")
        await pilot.click("#next_match")
        await pilot.pause()

        assert editor.editor.cursor_location == original_location


async def test_regex_find_wrap_around(workspace: Path, regex_file: Path):
    """Regex search from end of file → finds first match via wrap-around."""
    app = make_app(workspace, open_file=regex_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Move cursor to last line
        editor.editor.cursor_location = (2, 0)
        await pilot.pause()

        editor.action_find()
        await pilot.pause()

        from textual.widgets import Checkbox

        checkbox = editor.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.click("#next_match")
        await pilot.pause()

        sel = editor.editor.selection
        # wrap-around → first 'hello' at (0, 0)
        assert sel.start == (0, 0)
        assert sel.end == (0, 5)


async def test_invalid_regex_find_shows_error(workspace: Path, regex_file: Path):
    """Invalid regex → error notification, no crash."""
    app = make_app(workspace, open_file=regex_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        original_location = editor.editor.cursor_location

        editor.action_find()
        await pilot.pause()

        from textual.widgets import Checkbox

        checkbox = editor.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        # "[unclosed" → re.error
        await pilot.press("[")
        await pilot.click("#next_match")
        await pilot.pause()

        # no crash + cursor unchanged
        assert editor.editor.cursor_location == original_location


async def test_regex_find_case_insensitive_inline(workspace: Path, regex_file: Path):
    """(?i)hello → also selects 'HELLO'."""
    # regex_file: "hello world\nHELLO WORLD\nfoo123 bar456\n"
    app = make_app(workspace, open_file=regex_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Move cursor past first 'hello' to find second 'HELLO'
        editor.editor.cursor_location = (1, 0)
        await pilot.pause()

        editor.action_find()
        await pilot.pause()

        from textual.widgets import Checkbox

        checkbox = editor.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)
        await pilot.pause()  # Windows: extra pause for checkbox state change

        input_widget = editor.query_one("#find_input", Input)
        input_widget.value = "(?i)hello"
        await pilot.pause()
        await pilot.click("#next_match")
        # Windows: wait for regex find + selection update to complete
        await wait_for_condition(
            pilot,
            lambda: editor.editor.selection.end == (1, 5),
            msg="Regex case-insensitive find did not select HELLO at (1,0)–(1,5)",
        )

        sel = editor.editor.selection
        # cursor at (1,0) → searches from (1,0) → HELLO at (1,0)–(1,5)
        assert sel.start == (1, 0)
        assert sel.end == (1, 5)


async def test_plain_find_regression(workspace: Path, regex_file: Path):
    """Without checking use_regex → plain string search works as before."""
    app = make_app(workspace, open_file=regex_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_find()
        await pilot.pause()

        # do not check use_regex
        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.click("#next_match")
        await pilot.pause()

        sel = editor.editor.selection
        assert sel.start == (0, 0)
        assert sel.end == (0, 5)


# ── regex replace_all integration tests ──────────────────────────────────────


async def test_regex_replace_all_basic(workspace: Path, regex_file: Path):
    r"""\d+ → replace all occurrences with [NUM]."""
    app = make_app(workspace, open_file=regex_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_replace()
        await pilot.pause()

        from textual.widgets import Checkbox

        checkbox = editor.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)
        await pilot.pause()  # Windows: extra pause for checkbox state change

        await pilot.click("#find_input")
        await pilot.press("\\", "d", "+")
        await pilot.click("#replace_input")
        await pilot.press("[", "N", "U", "M", "]")
        await pilot.pause()  # Windows: extra pause for key presses to propagate
        await pilot.click("#replace_all_btn")
        # Windows: wait for regex replace all to complete
        await wait_for_condition(
            pilot,
            lambda: "[NUM]" in editor.text,
            msg="Regex replace all did not substitute [NUM]",
        )
        assert "123" not in editor.text
        assert "456" not in editor.text


async def test_regex_replace_all_capture_group(workspace: Path):
    r"""(\w+) → [\1] capture group replacement."""
    f = workspace / "capture.txt"
    f.write_text("hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_replace()
        await pilot.pause()
        await pilot.pause()  # Windows: extra pause for replace bar rendering

        from textual.widgets import Checkbox

        checkbox = editor.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)
        await pilot.pause()  # Windows: extra pause for checkbox state change

        await pilot.click("#find_input")
        # pattern: (\w+)
        await pilot.press("(", "\\", "w", "+", ")")
        await pilot.click("#replace_input")
        # replacement: [\1]
        await pilot.press("[", "\\", "1", "]")
        await pilot.pause()  # Windows: extra pause for key presses
        await pilot.click("#replace_all_btn")
        await pilot.pause()
        await pilot.pause()  # Windows: extra pause for regex replace all completion

        assert "[hello]" in editor.text
        assert "[world]" in editor.text


async def test_invalid_regex_replace_all_error(workspace: Path, regex_file: Path):
    """Invalid regex in replace_all → error notification, text unchanged."""
    app = make_app(workspace, open_file=regex_file, light=True)
    original_text = regex_file.read_text(encoding="utf-8")
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_replace()
        await pilot.pause()

        from textual.widgets import Checkbox

        checkbox = editor.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)

        await pilot.click("#find_input")
        await pilot.press("[")
        await pilot.click("#replace_input")
        await pilot.press("x")
        await pilot.click("#replace_all_btn")
        await pilot.pause()

        # text unchanged
        assert editor.text == original_text


# ── regex replace single integration tests ────────────────────────────────────


async def test_regex_replace_single_match_replaces(workspace: Path):
    r"""Selection is a fullmatch → replace, then select next match."""
    f = workspace / "single_rep.txt"
    f.write_text("foo123 foo456\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # First select foo123
        from textual.widgets.text_area import Selection

        editor.editor.selection = Selection(start=(0, 0), end=(0, 6))
        await pilot.pause()

        editor.action_replace()
        await pilot.pause()
        await pilot.pause()  # Windows: extra pause for replace bar rendering

        from textual.widgets import Checkbox

        checkbox = editor.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)
        await pilot.pause()  # Windows: extra pause for checkbox state change

        await pilot.click("#find_input")
        await pilot.press("f", "o", "o", "\\", "d", "+")
        await pilot.click("#replace_input")
        await pilot.press("X")
        await pilot.pause()  # Windows: extra pause for key presses
        await pilot.click("#replace_btn")
        await pilot.pause()
        await pilot.pause()  # Windows: extra pause for regex replace + next match

        # foo123 → X, then foo456 is selected
        assert "X" in editor.text
        assert "foo123" not in editor.text


async def test_regex_replace_single_no_match_finds(workspace: Path):
    """Selection does not match → only selects the next regex match."""
    f = workspace / "no_match_sel.txt"
    f.write_text("hello foo123\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # cursor at start with no selection (selected_text != "foo\d+")
        editor.action_replace()
        await pilot.pause()
        await pilot.pause()  # Windows: extra pause for replace bar rendering

        from textual.widgets import Checkbox

        checkbox = editor.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)
        await pilot.pause()  # Windows: extra pause for checkbox state change

        await pilot.click("#find_input")
        await pilot.pause()  # Windows: extra pause for input focus
        await pilot.press("f", "o", "o", "\\", "d", "+")
        await pilot.click("#replace_input")
        await pilot.pause()  # Windows: extra pause for input focus
        await pilot.press("X")
        await pilot.pause()  # Windows: extra pause for key presses
        await pilot.click("#replace_btn")
        await pilot.pause()
        await pilot.pause()  # Windows: extra pause for replace + next match

        sel = editor.editor.selection
        # foo123 at (0, 6)–(0, 12) should be selected
        assert sel.start == (0, 6)
        assert sel.end == (0, 12)
        # text not yet changed
        assert "foo123" in editor.text


async def test_invalid_regex_replace_single_error(workspace: Path, regex_file: Path):
    """Invalid regex in replace single → error notification, text unchanged."""
    app = make_app(workspace, open_file=regex_file, light=True)
    original_text = regex_file.read_text(encoding="utf-8")
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_replace()
        await pilot.pause()

        from textual.widgets import Checkbox

        checkbox = editor.query_one("#use_regex", Checkbox)
        await pilot.click(checkbox)

        await pilot.click("#find_input")
        await pilot.press("[")
        await pilot.click("#replace_input")
        await pilot.press("x")
        await pilot.click("#replace_btn")
        await pilot.pause()

        # text unchanged
        assert editor.text == original_text
