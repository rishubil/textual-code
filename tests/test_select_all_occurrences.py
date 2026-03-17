"""
Tests for the 'Select all occurrences' feature.

Uses Red-Green TDD style: all tests should fail (AttributeError) before
the implementation is added, then pass after.
"""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.widgets.code_editor import _get_word_at_location

# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def occ_file(workspace: Path) -> Path:
    f = workspace / "occ.txt"
    f.write_text("foo bar\nfoo baz\nqux\n")  # "foo" appears 2 times
    return f


@pytest.fixture
def multi_occ_file(workspace: Path) -> Path:
    f = workspace / "multi.txt"
    f.write_text("foo bar foo\nfoo baz\nqux\n")  # "foo" appears 3 times
    return f


@pytest.fixture
def special_chars_file(workspace: Path) -> Path:
    f = workspace / "special.txt"
    f.write_text("a.b and a.b and axb\n")
    return f


@pytest.fixture
def multiline_occ_file(workspace: Path) -> Path:
    f = workspace / "multiline.txt"
    f.write_text("hello world\nhello there\ngoodbye\n")
    return f


@pytest.fixture
def single_occ_file(workspace: Path) -> Path:
    f = workspace / "single.txt"
    f.write_text("foo bar baz\n")  # "foo" appears once
    return f


@pytest.fixture
def word_file(workspace: Path) -> Path:
    f = workspace / "word.txt"
    f.write_text("hello world\nhello there\n")
    return f


# ── Unit: _get_word_at_location ────────────────────────────────────────────────


def test_get_word_at_location_middle():
    """Cursor in the middle of 'hello' → returns 'hello'."""
    text = "hello world"
    assert _get_word_at_location(text, 0, 2) == "hello"


def test_get_word_at_location_start_of_word():
    """Cursor at start of 'world' → returns 'world'."""
    text = "hello world"
    assert _get_word_at_location(text, 0, 6) == "world"


def test_get_word_at_location_on_whitespace():
    """Cursor on whitespace → returns ''."""
    text = "hello world"
    assert _get_word_at_location(text, 0, 5) == ""


def test_get_word_at_location_second_line():
    """Cursor on second line word → returns that word."""
    text = "foo\nbar baz"
    assert _get_word_at_location(text, 1, 4) == "baz"


def test_get_word_at_location_row_out_of_range():
    """Row beyond last line → returns ''."""
    text = "hello"
    assert _get_word_at_location(text, 5, 0) == ""


def test_get_word_at_location_col_out_of_range():
    """Col beyond end of line → returns ''."""
    text = "hello"
    assert _get_word_at_location(text, 0, 100) == ""


# ── Unit: _get_query_text ──────────────────────────────────────────────────────


async def test_get_query_text_uses_selection(workspace: Path, occ_file: Path):
    """If text is selected, _get_query_text returns selected_text."""
    from textual.widgets.text_area import Selection

    app = make_app(workspace, open_file=occ_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Select "foo" (row=0, col=0 to row=0, col=3)
        editor.editor.selection = Selection(start=(0, 0), end=(0, 3))
        await pilot.pause()
        assert editor._get_query_text() == "foo"


async def test_get_query_text_uses_word_under_cursor(workspace: Path, occ_file: Path):
    """If no selection, _get_query_text returns word under cursor."""
    from textual.widgets.text_area import Selection

    app = make_app(workspace, open_file=occ_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Cursor in "foo" with no selection
        editor.editor.selection = Selection(start=(0, 1), end=(0, 1))
        await pilot.pause()
        assert editor._get_query_text() == "foo"


async def test_get_query_text_empty_on_whitespace(workspace: Path, occ_file: Path):
    """Cursor on whitespace with no selection → returns ''."""
    from textual.widgets.text_area import Selection

    app = make_app(workspace, open_file=occ_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Cursor on space between "foo" and "bar"
        editor.editor.selection = Selection(start=(0, 3), end=(0, 3))
        await pilot.pause()
        assert editor._get_query_text() == ""


# ── Integration: action_select_all_occurrences ────────────────────────────────


async def test_select_all_occurrences_multiple_matches(workspace: Path, occ_file: Path):
    """With 2 matches, primary selection is set to first, extra cursor to second."""
    from textual.widgets.text_area import Selection

    app = make_app(workspace, open_file=occ_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Select "foo" first to use as query
        editor.editor.selection = Selection(start=(0, 0), end=(0, 3))
        await pilot.pause()

        editor.action_select_all_occurrences()
        await pilot.pause()

        # Primary selection should be at (0,0)-(0,3)
        assert editor.editor.selection.start == (0, 0)
        assert editor.editor.selection.end == (0, 3)
        # Extra cursor at end of second "foo" on line 1 (anchor at start)
        assert (1, 3) in editor.editor.extra_cursors
        assert editor.editor.extra_anchors == [(1, 0)]


async def test_select_all_occurrences_single_match(
    workspace: Path, single_occ_file: Path
):
    """Single match → only primary selection set, extra_cursors is empty."""
    from textual.widgets.text_area import Selection

    app = make_app(workspace, open_file=single_occ_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.editor.selection = Selection(start=(0, 0), end=(0, 3))
        await pilot.pause()

        editor.action_select_all_occurrences()
        await pilot.pause()

        assert editor.editor.selection.start == (0, 0)
        assert editor.editor.selection.end == (0, 3)
        assert editor.editor.extra_cursors == []


async def test_select_all_occurrences_empty_query_is_noop(
    workspace: Path, occ_file: Path
):
    """Empty query (cursor on whitespace) → no selection change."""
    from textual.widgets.text_area import Selection

    app = make_app(workspace, open_file=occ_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Cursor on space → empty query
        editor.editor.selection = Selection(start=(0, 3), end=(0, 3))
        await pilot.pause()

        original_sel = editor.editor.selection

        editor.action_select_all_occurrences()
        await pilot.pause()

        # Selection should be unchanged
        assert editor.editor.selection == original_sel
        assert editor.editor.extra_cursors == []


async def test_select_all_occurrences_extra_cursor_count(
    workspace: Path, multi_occ_file: Path
):
    """3 matches → extra_cursors has 2 entries (primary takes first)."""
    from textual.widgets.text_area import Selection

    app = make_app(workspace, open_file=multi_occ_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.editor.selection = Selection(start=(0, 0), end=(0, 3))
        await pilot.pause()

        editor.action_select_all_occurrences()
        await pilot.pause()

        assert len(editor.editor.extra_cursors) == 2


async def test_select_all_occurrences_clears_previous_cursors(
    workspace: Path, occ_file: Path
):
    """Previous extra cursors are cleared before setting new ones."""
    from textual.widgets.text_area import Selection

    app = make_app(workspace, open_file=occ_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Add a stale cursor
        editor.editor.add_cursor((0, 5))
        await pilot.pause()
        assert len(editor.editor.extra_cursors) == 1

        # Now select all "foo"
        editor.editor.selection = Selection(start=(0, 0), end=(0, 3))
        await pilot.pause()

        editor.action_select_all_occurrences()
        await pilot.pause()

        # Only the cursors from the new selection should remain
        assert (0, 5) not in editor.editor.extra_cursors


async def test_select_all_occurrences_case_sensitive(workspace: Path):
    """Search is case-sensitive: 'foo' does not match 'Foo'."""
    from textual.widgets.text_area import Selection

    f = workspace / "case.txt"
    f.write_text("foo Foo FOO\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.editor.selection = Selection(start=(0, 0), end=(0, 3))
        await pilot.pause()

        editor.action_select_all_occurrences()
        await pilot.pause()

        # Only 1 match → no extra cursors
        assert editor.editor.extra_cursors == []


async def test_select_all_occurrences_multiline(
    workspace: Path, multiline_occ_file: Path
):
    """Matches across multiple lines are all found."""
    from textual.widgets.text_area import Selection

    app = make_app(workspace, open_file=multiline_occ_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.editor.selection = Selection(start=(0, 0), end=(0, 5))
        await pilot.pause()

        editor.action_select_all_occurrences()
        await pilot.pause()

        # "hello" appears twice (line 0 and line 1)
        assert len(editor.editor.extra_cursors) == 1
        # Cursor at end of match, anchor at start
        assert (1, 5) in editor.editor.extra_cursors
        assert editor.editor.extra_anchors == [(1, 0)]


async def test_select_all_occurrences_regex_special_chars(
    workspace: Path, special_chars_file: Path
):
    """Literal 'a.b' does not match 'axb' (re.escape used)."""
    from textual.widgets.text_area import Selection

    app = make_app(workspace, open_file=special_chars_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Select "a.b" literally
        editor.editor.selection = Selection(start=(0, 0), end=(0, 3))
        await pilot.pause()

        editor.action_select_all_occurrences()
        await pilot.pause()

        # Only literal "a.b" matches (2 times), not "axb"
        assert len(editor.editor.extra_cursors) == 1


async def test_select_all_occurrences_word_under_cursor(
    workspace: Path, word_file: Path
):
    """No selection → uses word under cursor for query."""
    from textual.widgets.text_area import Selection

    app = make_app(workspace, open_file=word_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Cursor in "hello" on line 0 (no selection)
        editor.editor.selection = Selection(start=(0, 2), end=(0, 2))
        await pilot.pause()

        editor.action_select_all_occurrences()
        await pilot.pause()

        # "hello" appears on lines 0 and 1 → 1 extra cursor at end of match
        assert len(editor.editor.extra_cursors) == 1
        assert (1, 5) in editor.editor.extra_cursors


async def test_ctrl_shift_l_triggers_select_all(workspace: Path, occ_file: Path):
    """Ctrl+Shift+L key binding triggers select_all_occurrences."""
    from textual.widgets.text_area import Selection

    app = make_app(workspace, open_file=occ_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Select "foo"
        editor.editor.selection = Selection(start=(0, 0), end=(0, 3))
        await pilot.pause()

        await pilot.press("ctrl+shift+l")
        await pilot.pause()

        # Both "foo" occurrences should be selected
        assert editor.editor.selection.start == (0, 0)
        assert (1, 3) in editor.editor.extra_cursors


async def test_select_all_occurrences_cmd_no_file(workspace: Path):
    """Command palette action when no file is open → error notify, no crash."""
    app = make_app(workspace, open_file=None, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Should not raise an exception
        app.action_select_all_occurrences_cmd()
        await pilot.pause()
