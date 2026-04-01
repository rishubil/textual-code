"""
Find (Ctrl+F) feature tests — plain search in the current file.

Behaviour spec:
- Ctrl+F opens FindReplaceBar in find mode
- Submitting a query selects the first occurrence at/after the cursor
- If no match exists after the cursor, wraps around to the first match in the
  file
- If no match at all, a notification is shown and the cursor does not move
- Closing the bar leaves the cursor unchanged
- Search is case-sensitive
- Empty query does nothing
- Works on untitled (unsaved) files

Helper spec (_text_offset_to_location):
- Converts a character offset to a (row, col) tuple
- Newline characters increment row and reset col
"""

from pathlib import Path

import pytest
from textual.widgets import Checkbox, Input

from tests.conftest import make_app
from textual_code.widgets.code_editor import (
    _find_previous,
    _text_offset_to_location,
)
from textual_code.widgets.find_replace_bar import FindReplaceBar

# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def search_file(workspace: Path) -> Path:
    """A file with repeated words useful for search testing."""
    f = workspace / "search.txt"
    f.write_text("hello world\nhello textual\nfoo bar\n")
    return f


# ── Ctrl+F opens bar ──────────────────────────────────────────────────────────


async def test_ctrl_f_opens_find_bar(workspace: Path, search_file: Path):
    app = make_app(workspace, light=True, open_file=search_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        await pilot.press("ctrl+f")
        await pilot.wait_for_scheduled_animations()
        bar = editor.query_one(FindReplaceBar)
        assert bar.display
        assert not bar.replace_mode


# ── find selects text ─────────────────────────────────────────────────────────


async def test_find_selects_first_match_from_start(workspace: Path, search_file: Path):
    """Searching for 'hello' from the start selects the first 'hello'."""
    app = make_app(workspace, light=True, open_file=search_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()

        sel = editor.editor.selection
        # 'hello' is at (0, 0)–(0, 5)
        assert sel.start == (0, 0)
        assert sel.end == (0, 5)


async def test_find_from_cursor_finds_next_occurrence(
    workspace: Path, search_file: Path
):
    """When cursor is past the first match, the second occurrence is selected."""
    app = make_app(workspace, light=True, open_file=search_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Move cursor past first 'hello' (row=0, col=6 — after 'hello ')
        editor.editor.cursor_location = (0, 6)
        await pilot.wait_for_scheduled_animations()

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()

        sel = editor.editor.selection
        # second 'hello' is at (1, 0)–(1, 5)
        assert sel.start == (1, 0)
        assert sel.end == (1, 5)


async def test_find_wraps_around_to_beginning(workspace: Path, search_file: Path):
    """When no match exists after cursor, wraps to the first match in file."""
    app = make_app(workspace, light=True, open_file=search_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Move cursor to last line so 'hello' only appears before cursor
        editor.editor.cursor_location = (2, 0)
        await pilot.wait_for_scheduled_animations()

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()

        sel = editor.editor.selection
        # wraps around: first 'hello' at (0, 0)–(0, 5)
        assert sel.start == (0, 0)
        assert sel.end == (0, 5)


async def test_find_no_match_does_not_change_cursor(workspace: Path, search_file: Path):
    """When query is not found anywhere, cursor stays put."""
    app = make_app(workspace, light=True, open_file=search_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        original_location = editor.editor.cursor_location

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("z", "z", "z", "n", "o", "t", "f", "o", "u", "n", "d")
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()

        assert editor.editor.cursor_location == original_location


async def test_find_cancel_keeps_cursor(workspace: Path, search_file: Path):
    """Closing the find bar leaves the cursor unchanged."""
    app = make_app(workspace, light=True, open_file=search_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.editor.cursor_location = (1, 3)
        await pilot.wait_for_scheduled_animations()

        original_location = editor.editor.cursor_location

        editor.action_find()
        await pilot.wait_for_scheduled_animations()
        await pilot.click("#close_btn")
        await pilot.wait_for_scheduled_animations()

        assert editor.editor.cursor_location == original_location


async def test_find_empty_query_does_nothing(workspace: Path, search_file: Path):
    """Submitting an empty query does not move the cursor."""
    app = make_app(workspace, light=True, open_file=search_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        original_location = editor.editor.cursor_location

        editor.action_find()
        await pilot.wait_for_scheduled_animations()
        # Submit with empty input
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()

        assert editor.editor.cursor_location == original_location


async def test_find_multiline_match(workspace: Path):
    """Search works across multi-line files and finds correct location."""
    f = workspace / "multi.py"
    f.write_text("def foo():\n    return 42\ndef bar():\n    return 0\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("r", "e", "t", "u", "r", "n")
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()

        sel = editor.editor.selection
        # 'return' first appears at (1, 4)–(1, 10)
        assert sel.start == (1, 4)
        assert sel.end == (1, 10)


# ── _text_offset_to_location helper ───────────────────────────────────────────


def test_offset_to_location_start_of_file():
    assert _text_offset_to_location("hello\nworld", 0) == (0, 0)


def test_offset_to_location_mid_first_line():
    assert _text_offset_to_location("hello\nworld", 3) == (0, 3)


def test_offset_to_location_end_of_first_line():
    # offset 5 points to the '\n' itself — still on row 0
    assert _text_offset_to_location("hello\nworld", 5) == (0, 5)


def test_offset_to_location_start_of_second_line():
    # offset 6 is the first char after '\n'
    assert _text_offset_to_location("hello\nworld", 6) == (1, 0)


def test_offset_to_location_mid_second_line():
    assert _text_offset_to_location("hello\nworld", 8) == (1, 2)


def test_offset_to_location_three_lines():
    text = "ab\ncd\nef"
    # 'e' is at offset 6 → row 2, col 0
    assert _text_offset_to_location(text, 6) == (2, 0)
    # 'f' is at offset 7 → row 2, col 1
    assert _text_offset_to_location(text, 7) == (2, 1)


def test_offset_to_location_empty_first_line():
    # "\nhello" — first line is empty
    assert _text_offset_to_location("\nhello", 1) == (1, 0)
    assert _text_offset_to_location("\nhello", 3) == (1, 2)


# ── Case sensitivity ──────────────────────────────────────────────────────────


async def test_find_is_case_sensitive_no_match(workspace: Path, search_file: Path):
    """'Hello' (capital H) is not found in a file that only has 'hello'."""
    app = make_app(workspace, light=True, open_file=search_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        original_location = editor.editor.cursor_location

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("H", "e", "l", "l", "o")  # capital H
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()

        assert editor.editor.cursor_location == original_location


async def test_find_is_case_sensitive_exact_match(workspace: Path):
    """Exact-case query matches correctly."""
    f = workspace / "mixed.txt"
    f.write_text("Hello World\nhello world\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("H", "e", "l", "l", "o")  # capital H
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()

        sel = editor.editor.selection
        # 'Hello' at (0, 0)–(0, 5)
        assert sel.start == (0, 0)
        assert sel.end == (0, 5)


# ── Cursor inside a match ─────────────────────────────────────────────────────


async def test_find_cursor_inside_match_skips_to_next(
    workspace: Path, search_file: Path
):
    """When cursor is inside a match, that match is skipped; next is selected."""
    # search_file: "hello world\nhello textual\nfoo bar\n"
    app = make_app(workspace, light=True, open_file=search_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Place cursor at col 2 — inside the first 'hello'
        editor.editor.cursor_location = (0, 2)
        await pilot.wait_for_scheduled_animations()

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()

        sel = editor.editor.selection
        # Skips first 'hello' (starts at 0), finds second 'hello' at (1, 0)
        assert sel.start == (1, 0)
        assert sel.end == (1, 5)


# ── Single-character query ────────────────────────────────────────────────────


async def test_find_single_char_query(workspace: Path, search_file: Path):
    """A single-character query selects a one-character range."""
    # search_file: "hello world\nhello textual\nfoo bar\n"
    app = make_app(workspace, light=True, open_file=search_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("h")
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()

        sel = editor.editor.selection
        assert sel.start == (0, 0)
        assert sel.end == (0, 1)


# ── Multi-word query ──────────────────────────────────────────────────────────


async def test_find_multiword_query(workspace: Path, search_file: Path):
    """A multi-word query spanning a space is found correctly."""
    # search_file first line: "hello world"
    app = make_app(workspace, light=True, open_file=search_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input", Input)
        input_widget.value = "hello world"
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for input value change
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for find result + selection update

        sel = editor.editor.selection
        assert sel.start == (0, 0)
        assert sel.end == (0, 11)


# ── Match at end of file ──────────────────────────────────────────────────────


async def test_find_match_at_end_of_file(workspace: Path):
    """Match at the very end of the file is found and selected correctly."""
    f = workspace / "end.txt"
    f.write_text("line one\nfind me")  # no trailing newline
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input", Input)
        input_widget.value = "find me"
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for input value change
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for find result + selection update

        sel = editor.editor.selection
        # "find me" is on row 1, cols 0–7
        assert sel.start == (1, 0)
        assert sel.end == (1, 7)


# ── Single-line file ──────────────────────────────────────────────────────────


async def test_find_in_single_line_file(workspace: Path):
    """Search works correctly in a file with no newlines."""
    f = workspace / "oneline.txt"
    f.write_text("abcdefgh")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("d", "e", "f")
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()

        sel = editor.editor.selection
        assert sel.start == (0, 3)
        assert sel.end == (0, 6)


async def test_find_wrap_in_single_line_file(workspace: Path):
    """Wrap-around works even in a single-line file."""
    f = workspace / "oneline2.txt"
    f.write_text("abc abc abc")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Place cursor after the last 'abc'
        editor.editor.cursor_location = (0, 9)
        await pilot.wait_for_scheduled_animations()

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("a", "b", "c")
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()

        sel = editor.editor.selection
        # last 'abc' starts at col 8, but cursor is at 9 → wraps → first 'abc' at col 0
        assert sel.start == (0, 0)
        assert sel.end == (0, 3)


# ── File without trailing newline ─────────────────────────────────────────────


async def test_find_file_without_trailing_newline(workspace: Path):
    """Find works on files that do not end with a newline."""
    f = workspace / "no_newline.txt"
    f.write_text("first line\nsecond line")  # no trailing \n
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input", Input)
        input_widget.value = "second"
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for input value change
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for find result + selection update

        sel = editor.editor.selection
        assert sel.start == (1, 0)
        assert sel.end == (1, 6)


# ── Sequential finds ──────────────────────────────────────────────────────────


async def test_find_sequential_opens_finds_next_each_time(
    workspace: Path, search_file: Path
):
    """Clicking Next multiple times progresses through occurrences."""
    # search_file: "hello world\nhello textual\nfoo bar\n"
    # Two 'hello': (0,0)–(0,5) and (1,0)–(1,5)
    app = make_app(workspace, light=True, open_file=search_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Open bar and type query
        editor.action_find()
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for find bar rendering
        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for input focus
        await pilot.press("h", "e", "l", "l", "o")
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for key presses

        # First click: finds 'hello' at (0, 0)
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for find + selection update
        assert editor.editor.selection.start == (0, 0)

        # Second click: searches from end of selection (0,5) → finds (1, 0)
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for find + selection update
        assert editor.editor.selection.start == (1, 0)
        assert editor.editor.selection.end == (1, 5)


# ── Untitled file ─────────────────────────────────────────────────────────────


async def test_find_works_on_untitled_file(workspace: Path):
    """Find works on a new, unsaved file after typing content via pilot."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+n")
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Type content into the TextArea so text reactive is set
        editor.editor.focus()
        await pilot.wait_for_scheduled_animations()
        for ch in "hello world":
            await pilot.press(ch)
        await pilot.wait_for_scheduled_animations()

        # Move cursor back to start before searching
        editor.editor.cursor_location = (0, 0)
        await pilot.wait_for_scheduled_animations()

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("w", "o", "r", "l", "d")
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()

        sel = editor.editor.selection
        assert sel.start[1] == 6  # 'world' starts at col 6 in "hello world"


# ── Enter key submits ─────────────────────────────────────────────────────────


async def test_find_enter_key_submits(workspace: Path, search_file: Path):
    """Pressing Enter in the query input triggers the find."""
    app = make_app(workspace, light=True, open_file=search_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("f", "o", "o")
        await pilot.press("enter")  # submit via Enter, not button click
        await pilot.wait_for_scheduled_animations()

        sel = editor.editor.selection
        # 'foo' is on row 2, col 0
        assert sel.start == (2, 0)
        assert sel.end == (2, 3)


# ── No active editor ──────────────────────────────────────────────────────────


async def test_ctrl_f_with_no_open_file_opens_no_bar(workspace: Path):
    """Ctrl+F when no file is open does not open a FindReplaceBar."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # No file opened — no CodeEditor, so no FindReplaceBar visible
        await pilot.press("ctrl+f")
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is None


async def test_find_cmd_with_no_open_file_does_nothing(workspace: Path):
    """action_find_cmd when no file is open does not crash."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.action_find_cmd()
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is None


# ── Whole-file match ──────────────────────────────────────────────────────────


async def test_find_entire_file_content_as_query(workspace: Path):
    """When the query is the entire file content, the whole file is selected."""
    content = "match me"
    f = workspace / "whole.txt"
    f.write_text(content)
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input", Input)
        input_widget.value = content
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for input value change
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for find result + selection update

        sel = editor.editor.selection
        assert sel.start == (0, 0)
        assert sel.end == (0, len(content))


# ── Case-insensitive find ─────────────────────────────────────────────────────


async def test_case_insensitive_find_selects_uppercase_match(workspace: Path):
    """Case-insensitive find selects uppercase match for lowercase query."""
    f = workspace / "ci.txt"
    f.write_text("HELLO world\nhello\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_find()
        await pilot.wait_for_scheduled_animations()
        bar = editor.query_one(FindReplaceBar)

        # Uncheck case_sensitive checkbox
        case_cb = bar.query_one("#case_sensitive", Checkbox)
        case_cb.value = False
        await pilot.wait_for_scheduled_animations()

        await pilot.click("#find_input")
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()

        sel = editor.editor.selection
        # "HELLO" at (0, 0)-(0, 5) should be selected first
        assert sel.start == (0, 0)
        assert sel.end == (0, 5)


async def test_case_sensitive_find_does_not_match_different_case(workspace: Path):
    """Case-sensitive find (default) does not match different-case text."""
    f = workspace / "cs.txt"
    f.write_text("HELLO world\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        await pilot.click("#find_input")
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.click("#next_match")
        await pilot.wait_for_scheduled_animations()

        # No selection change since "hello" != "HELLO" (case-sensitive default)
        sel = editor.editor.selection
        assert sel.start == sel.end  # cursor not moved to a selection


# ── _find_previous unit tests ────────────────────────────────────────────────


def test_find_previous_basic():
    """_find_previous finds the match before cursor_offset."""
    text = "hello world hello"
    # cursor at offset 17 (end of text), match at 12-17 has end=17 (not < 17),
    # so it is skipped; first 'hello' at 0-5 is found
    start, end = _find_previous(text, "hello", 17)
    assert (start, end) == (0, 5)


def test_find_previous_wraps_around():
    """_find_previous wraps to the last match when no match before cursor."""
    text = "hello world hello"
    # cursor at offset 0, no match before it → wraps to last match at 12
    start, end = _find_previous(text, "hello", 0)
    assert (start, end) == (12, 17)


def test_find_previous_not_found():
    """_find_previous returns (-1, -1) when query not in text."""
    assert _find_previous("hello world", "zzz", 5) == (-1, -1)


def test_find_previous_regex():
    """_find_previous works with regex patterns."""
    text = "abc 123 def 456"
    # cursor at 12 (start of "456"), previous numeric match is "123" at 4-7
    start, end = _find_previous(text, r"\d+", 12, use_regex=True)
    assert (start, end) == (4, 7)


def test_find_previous_case_insensitive():
    """_find_previous respects case_sensitive=False."""
    text = "Hello HELLO hello"
    # cursor at 12 (start of last "hello"), previous match is "HELLO" at 6-11
    start, end = _find_previous(text, "hello", 12, case_sensitive=False)
    assert (start, end) == (6, 11)


# ── Find Previous integration tests ─────────────────────────────────────────


async def test_find_previous_selects_previous_match(workspace: Path, search_file: Path):
    """Shift+Enter in find bar selects the previous match."""
    # search_file: "hello world\nhello textual\nfoo bar\n"
    app = make_app(workspace, light=True, open_file=search_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Place cursor after second 'hello' (row=1, col=5)
        editor.editor.cursor_location = (1, 5)
        await pilot.wait_for_scheduled_animations()

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("h", "e", "l", "l", "o")

        # Click prev_match button
        await pilot.click("#prev_match")
        await pilot.wait_for_scheduled_animations()

        sel = editor.editor.selection
        # Should find 'hello' at (0, 0)-(0, 5) — the previous match
        assert sel.start == (0, 0)
        assert sel.end == (0, 5)


async def test_find_previous_wraps_to_last_match(workspace: Path, search_file: Path):
    """Find previous from before all matches wraps to the last match."""
    # search_file: "hello world\nhello textual\nfoo bar\n"
    app = make_app(workspace, light=True, open_file=search_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Cursor at start
        editor.editor.cursor_location = (0, 0)
        await pilot.wait_for_scheduled_animations()

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("h", "e", "l", "l", "o")

        await pilot.click("#prev_match")
        await pilot.wait_for_scheduled_animations()

        sel = editor.editor.selection
        # Wraps to last 'hello' at (1, 0)-(1, 5)
        assert sel.start == (1, 0)
        assert sel.end == (1, 5)


async def test_find_previous_shift_enter(workspace: Path, search_file: Path):
    """Shift+Enter in find input triggers find previous."""
    app = make_app(workspace, light=True, open_file=search_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Place cursor at end of file
        editor.editor.cursor_location = (2, 7)
        await pilot.wait_for_scheduled_animations()

        editor.action_find()
        await pilot.wait_for_scheduled_animations()

        input_widget = editor.query_one("#find_input")
        await pilot.click(input_widget)
        await pilot.press("h", "e", "l", "l", "o")

        # Shift+Enter should find previous
        await pilot.press("shift+enter")
        await pilot.wait_for_scheduled_animations()

        sel = editor.editor.selection
        # Should find 'hello' at (1, 0)-(1, 5) — the last match before cursor
        assert sel.start == (1, 0)
        assert sel.end == (1, 5)
