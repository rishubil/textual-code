"""
Tests for the 'Add next occurrence' feature (Ctrl+D, VS Code style).

Uses Red-Green TDD style: tests are written first (Red), then the
implementation is added to make them pass (Green).
"""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.widgets.code_editor import (
    _location_to_text_offset,
    _text_offset_to_location,
)

# ── Fixtures ────────────────────────────────────────────────────────────────────


@pytest.fixture
def occ_file(workspace: Path) -> Path:
    f = workspace / "occ_next.txt"
    f.write_text("foo bar\nfoo baz\nqux\n")  # "foo" appears 2 times
    return f


@pytest.fixture
def three_occ_file(workspace: Path) -> Path:
    f = workspace / "three.txt"
    f.write_text("foo bar foo\nfoo baz\n")  # "foo" appears 3 times
    return f


@pytest.fixture
def single_occ_file(workspace: Path) -> Path:
    f = workspace / "single_next.txt"
    f.write_text("foo bar baz\n")  # "foo" appears once
    return f


# ── Unit: _location_to_text_offset ─────────────────────────────────────────────


def test_location_to_offset_origin():
    """(0, 0) → offset 0."""
    assert _location_to_text_offset("hello\nworld", (0, 0)) == 0


def test_location_to_offset_single_line_middle():
    """(0, 3) in single-line text → 3."""
    assert _location_to_text_offset("hello", (0, 3)) == 3


def test_location_to_offset_second_line_start():
    """(1, 0) → length of first line + 1 (newline)."""
    text = "first\nsecond"
    assert _location_to_text_offset(text, (1, 0)) == len("first\n")


def test_location_to_offset_second_line_middle():
    """(1, 2) → len("first\\n") + 2."""
    text = "first\nsecond"
    assert _location_to_text_offset(text, (1, 2)) == len("first\n") + 2


def test_location_to_offset_roundtrip():
    """offset → location → offset is identity."""
    text = "foo bar\nfoo baz\nqux\n"
    for offset in range(len(text)):
        loc = _text_offset_to_location(text, offset)
        assert _location_to_text_offset(text, loc) == offset


# ── Integration: action_select_next_occurrence ─────────────────────────────────


async def test_ctrl_d_no_selection_selects_word(workspace: Path, occ_file: Path):
    """No selection, cursor on word → selects that word (primary selection only)."""
    from textual.widgets.text_area import Selection

    app = make_app(workspace, open_file=occ_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Cursor inside "foo" at (0, 1), no selection
        editor.editor.selection = Selection(start=(0, 1), end=(0, 1))
        await pilot.pause()

        editor.action_select_next_occurrence()
        await pilot.pause()

        # Primary selection should now cover "foo"
        assert editor.editor.selection.start == (0, 0)
        assert editor.editor.selection.end == (0, 3)
        # No extra cursors yet — first Ctrl+D just selects the word
        assert editor.editor.extra_cursors == []


async def test_ctrl_d_with_selection_adds_cursor(workspace: Path, occ_file: Path):
    """Selection exists → next occurrence added as extra cursor."""
    from textual.widgets.text_area import Selection

    app = make_app(workspace, open_file=occ_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Primary selection covers first "foo"
        editor.editor.selection = Selection(start=(0, 0), end=(0, 3))
        await pilot.pause()

        editor.action_select_next_occurrence()
        await pilot.pause()

        # Extra cursor added at end of second "foo" (line 1, col 3), with selection
        assert (1, 3) in editor.editor.extra_cursors
        assert editor.editor.extra_anchors == [(1, 0)]


async def test_ctrl_d_twice_adds_two_cursors(workspace: Path, three_occ_file: Path):
    """Two Ctrl+D presses after initial selection → two extra cursors."""
    from textual.widgets.text_area import Selection

    # text = "foo bar foo\nfoo baz\n"
    # positions: (0,0), (0,8), (1,0)
    app = make_app(workspace, open_file=three_occ_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Primary selection: first "foo"
        editor.editor.selection = Selection(start=(0, 0), end=(0, 3))
        await pilot.pause()

        editor.action_select_next_occurrence()
        await pilot.pause()
        assert len(editor.editor.extra_cursors) == 1
        # second "foo" at (0,8)-(0,11)
        assert editor.editor.extra_anchors == [(0, 8)]

        editor.action_select_next_occurrence()
        await pilot.pause()
        assert len(editor.editor.extra_cursors) == 2
        # third "foo" at (1,0)-(1,3)
        assert editor.editor.extra_anchors == [(0, 8), (1, 0)]


async def test_ctrl_d_all_selected_notification(workspace: Path, occ_file: Path):
    """After all occurrences selected, next Ctrl+D shows notification."""
    from textual.widgets.text_area import Selection

    app = make_app(workspace, open_file=occ_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Select first "foo"
        editor.editor.selection = Selection(start=(0, 0), end=(0, 3))
        await pilot.pause()

        # First Ctrl+D: adds second "foo" cursor
        editor.action_select_next_occurrence()
        await pilot.pause()
        assert len(editor.editor.extra_cursors) == 1

        # Second Ctrl+D: wraps around — should notify (no crash, no new cursor)
        before_count = len(editor.editor.extra_cursors)
        editor.action_select_next_occurrence()
        await pilot.pause()
        # Cursor count should not increase further
        assert len(editor.editor.extra_cursors) == before_count


async def test_ctrl_d_no_selection_non_word(workspace: Path, occ_file: Path):
    """Cursor on whitespace with no selection → no-op."""
    from textual.widgets.text_area import Selection

    app = make_app(workspace, open_file=occ_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Cursor on space between "foo" and "bar" at col 3
        editor.editor.selection = Selection(start=(0, 3), end=(0, 3))
        await pilot.pause()

        original_sel = editor.editor.selection
        editor.action_select_next_occurrence()
        await pilot.pause()

        # Selection unchanged, no extra cursors
        assert editor.editor.selection == original_sel
        assert editor.editor.extra_cursors == []


async def test_ctrl_d_single_occurrence_notification(
    workspace: Path, single_occ_file: Path
):
    """Single occurrence: first Ctrl+D selects word, second notifies wrap-around."""
    from textual.widgets.text_area import Selection

    app = make_app(workspace, open_file=single_occ_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Select the only "foo"
        editor.editor.selection = Selection(start=(0, 0), end=(0, 3))
        await pilot.pause()

        # Ctrl+D on single occurrence: wrap-around hits primary selection → notify
        editor.action_select_next_occurrence()
        await pilot.pause()

        # Still no extra cursors (all already selected)
        assert editor.editor.extra_cursors == []


async def test_ctrl_d_binding(workspace: Path, occ_file: Path):
    """Ctrl+D key binding triggers select_next_occurrence."""
    from textual.widgets.text_area import Selection

    app = make_app(workspace, open_file=occ_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Select first "foo"
        editor.editor.selection = Selection(start=(0, 0), end=(0, 3))
        await pilot.pause()

        await pilot.press("ctrl+d")
        await pilot.pause()

        # Extra cursor added at end of second "foo" (line 1, col 3), with selection
        assert (1, 3) in editor.editor.extra_cursors
        assert editor.editor.extra_anchors == [(1, 0)]


async def test_ctrl_d_extra_cursor_has_selection(workspace: Path, occ_file: Path):
    """Ctrl+D with selection → extra cursor has selection spanning the matched text."""
    from textual.widgets.text_area import Selection

    # occ_file: "foo bar\nfoo baz\nqux\n"
    # first "foo": (0,0)-(0,3), second "foo": (1,0)-(1,3)
    app = make_app(workspace, open_file=occ_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Primary selection covers first "foo"
        editor.editor.selection = Selection(start=(0, 0), end=(0, 3))
        await pilot.pause()

        editor.action_select_next_occurrence()
        await pilot.pause()

        # Extra cursor at end of second "foo", anchor at its start
        assert editor.editor.extra_cursors == [(1, 3)]
        assert editor.editor.extra_anchors == [(1, 0)]


async def test_ctrl_d_cmd_no_file(workspace: Path):
    """Command palette action when no file open → no crash."""
    app = make_app(workspace, open_file=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Should not raise an exception
        app.action_add_next_occurrence_cmd()
        await pilot.pause()
