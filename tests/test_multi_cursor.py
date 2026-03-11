"""
Multi-cursor feature tests.

Unit-level tests exercise MultiCursorTextArea directly (API + editing logic).
Integration-level tests run the full app via pilot (CodeEditor + key bindings).
"""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def two_line_file(workspace: Path) -> Path:
    f = workspace / "two.txt"
    f.write_text("Hello world\nFoo bar\n")
    return f


@pytest.fixture
def three_line_file(workspace: Path) -> Path:
    f = workspace / "three.txt"
    f.write_text("line1\nline2\nline3\n")
    return f


# ── Unit: extra_cursors list ──────────────────────────────────────────────────


async def test_no_extra_cursors_initially(workspace: Path, two_line_file: Path):
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.editor.extra_cursors == []


async def test_add_cursor_adds_to_list(workspace: Path, two_line_file: Path):
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        ta.add_cursor((1, 0))
        assert (1, 0) in ta.extra_cursors


async def test_add_cursor_same_as_primary_is_noop(workspace: Path, two_line_file: Path):
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        primary = ta.cursor_location
        ta.add_cursor(primary)
        assert ta.extra_cursors == []


async def test_add_cursor_duplicate_is_noop(workspace: Path, two_line_file: Path):
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        ta.add_cursor((1, 0))
        ta.add_cursor((1, 0))  # duplicate
        assert ta.extra_cursors.count((1, 0)) == 1


async def test_clear_cursors_removes_all(workspace: Path, two_line_file: Path):
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        ta.add_cursor((1, 0))
        ta.add_cursor((1, 3))
        ta.clear_extra_cursors()
        assert ta.extra_cursors == []


# ── Unit: _new_positions (position maths) ─────────────────────────────────────


def test_new_positions_insert_same_row():
    """Insert on the same row: each cursor shifts right by 1 + num before it."""
    cursors = [(0, 3), (0, 6)]
    result = MultiCursorTextArea._new_positions(cursors, "insert")
    assert result[(0, 3)] == (0, 4)  # 0 cursors before col 3 → +1
    assert result[(0, 6)] == (0, 8)  # 1 cursor before col 6 → +1+1=+2


def test_new_positions_insert_different_rows():
    """Insert on different rows: independent shift (+1 each)."""
    cursors = [(0, 3), (1, 6)]
    result = MultiCursorTextArea._new_positions(cursors, "insert")
    assert result[(0, 3)] == (0, 4)
    assert result[(1, 6)] == (1, 7)


def test_new_positions_backspace_same_row():
    """Backspace on same row: each cursor shifts left by 1 + num before it."""
    cursors = [(0, 6), (0, 3)]
    result = MultiCursorTextArea._new_positions(cursors, "backspace")
    assert result[(0, 3)] == (0, 2)  # 0 cursors before → -1
    assert result[(0, 6)] == (0, 4)  # 1 cursor before → -1-1=-2


def test_new_positions_delete_same_row():
    """Delete on same row: cursor stays put but shifts left for deletes before it."""
    cursors = [(0, 3), (0, 6)]
    result = MultiCursorTextArea._new_positions(cursors, "delete")
    assert result[(0, 3)] == (0, 3)  # 0 cursors before → no shift
    assert result[(0, 6)] == (0, 5)  # 1 cursor before → -1


# ── Integration: Ctrl+Alt+Down / Up ───────────────────────────────────────────


async def test_ctrl_alt_down_adds_cursor_below(workspace: Path, two_line_file: Path):
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        primary_row, primary_col = ta.cursor_location

        await pilot.press("ctrl+alt+down")
        await pilot.pause()

        assert (primary_row + 1, primary_col) in ta.extra_cursors


async def test_ctrl_alt_up_adds_cursor_above(workspace: Path, three_line_file: Path):
    app = make_app(workspace, open_file=three_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        # Move primary to row 1 first
        await pilot.press("down")
        await pilot.pause()
        primary_row, primary_col = ta.cursor_location

        await pilot.press("ctrl+alt+up")
        await pilot.pause()

        assert (primary_row - 1, primary_col) in ta.extra_cursors


async def test_ctrl_alt_down_at_last_line_is_noop(workspace: Path, two_line_file: Path):
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        # Move primary to last content line manually
        last_line = ta.document.line_count - 1
        ta.cursor_location = (last_line, 0)
        await pilot.pause()

        await pilot.press("ctrl+alt+down")
        await pilot.pause()

        assert ta.extra_cursors == []


async def test_ctrl_alt_up_at_first_line_is_noop(workspace: Path, two_line_file: Path):
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        await pilot.press("ctrl+alt+up")
        await pilot.pause()

        assert ta.extra_cursors == []


# ── Integration: escape clears extra cursors ──────────────────────────────────


async def test_escape_clears_extra_cursors(workspace: Path, two_line_file: Path):
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        ta.add_cursor((1, 0))
        assert ta.extra_cursors != []

        await pilot.press("escape")
        await pilot.pause()

        assert ta.extra_cursors == []


# ── Integration: movement key clears extra cursors ────────────────────────────


async def test_movement_key_clears_extra_cursors(workspace: Path, two_line_file: Path):
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        ta.add_cursor((1, 0))

        await pilot.press("right")
        await pilot.pause()

        assert ta.extra_cursors == []


# ── Integration: multi-cursor typing ─────────────────────────────────────────


async def test_typing_inserts_at_two_cursors(workspace: Path, two_line_file: Path):
    """Type 'X' with cursors on both lines inserts on both lines."""
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        # Move primary to (0, 0) and add extra at (1, 0)
        await pilot.press("ctrl+home")
        await pilot.pause()
        ta.add_cursor((1, 0))
        await pilot.pause()

        await pilot.press("X")
        await pilot.pause()

        lines = ta.text.split("\n")
        assert lines[0].startswith("X")
        assert lines[1].startswith("X")


async def test_backspace_deletes_at_two_cursors(workspace: Path, two_line_file: Path):
    """Backspace with cursors at col>0 on both lines deletes from both."""
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        # Move primary to (0, 1) and add extra at (1, 1)
        await pilot.press("ctrl+home")
        await pilot.pause()
        await pilot.press("right")
        await pilot.pause()
        ta.add_cursor((1, 1))
        await pilot.pause()

        original_lines = ta.text.split("\n")
        orig_line0 = original_lines[0]
        orig_line1 = original_lines[1]

        await pilot.press("backspace")
        await pilot.pause()

        lines = ta.text.split("\n")
        # Each line should be shorter by 1 character
        assert len(lines[0]) == len(orig_line0) - 1
        assert len(lines[1]) == len(orig_line1) - 1


async def test_delete_deletes_at_two_cursors(workspace: Path, two_line_file: Path):
    """Delete (forward) with cursors at col<EOL on both lines deletes from both."""
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        await pilot.press("ctrl+home")
        await pilot.pause()
        ta.add_cursor((1, 0))
        await pilot.pause()

        original_lines = ta.text.split("\n")
        orig_line0 = original_lines[0]
        orig_line1 = original_lines[1]

        await pilot.press("delete")
        await pilot.pause()

        lines = ta.text.split("\n")
        assert len(lines[0]) == len(orig_line0) - 1
        assert len(lines[1]) == len(orig_line1) - 1


# ── Integration: footer cursor count ─────────────────────────────────────────


async def test_footer_shows_cursor_count_in_multicursor_mode(
    workspace: Path, two_line_file: Path
):
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        ta = editor.editor

        # Single cursor: no bracket suffix
        cursor_btn = editor.footer.cursor_button
        assert "[" not in str(cursor_btn.label)

        ta.add_cursor((1, 0))
        await pilot.pause()

        # Multi-cursor: "[2]" suffix appears
        assert "[2]" in str(cursor_btn.label)


async def test_footer_hides_cursor_count_after_escape(
    workspace: Path, two_line_file: Path
):
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        ta = editor.editor

        ta.add_cursor((1, 0))
        await pilot.pause()
        assert "[2]" in str(editor.footer.cursor_button.label)

        await pilot.press("escape")
        await pilot.pause()

        assert "[" not in str(editor.footer.cursor_button.label)
