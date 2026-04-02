"""
Move line up/down and scroll viewport tests.

Tests for VSCode-like Alt+Up/Down (move lines) and Ctrl+Up/Down (scroll viewport).
"""

from pathlib import Path

import pytest
from textual.widgets.text_area import Selection

from tests.conftest import make_app

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def five_line_file(workspace: Path) -> Path:
    f = workspace / "five.txt"
    f.write_text("aaa\nbbb\nccc\nddd\neee\n")
    return f


@pytest.fixture
def single_line_file(workspace: Path) -> Path:
    f = workspace / "single.txt"
    f.write_text("only line")
    return f


@pytest.fixture
def empty_file(workspace: Path) -> Path:
    f = workspace / "empty.txt"
    f.write_text("")
    return f


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_editor(app):
    """Return the MultiCursorTextArea from the active code editor."""
    return app.main_view.get_active_code_editor().editor


# ── Move Down: single cursor ─────────────────────────────────────────────────


async def test_move_line_down_single_cursor(workspace: Path, five_line_file: Path):
    """Moving line 0 down swaps it with line 1; cursor follows."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        ta.cursor_location = (0, 0)
        ta.action_move_line_down()
        lines = ta.text.split("\n")
        assert lines[0] == "bbb"
        assert lines[1] == "aaa"
        assert ta.cursor_location == (1, 0)


async def test_move_line_down_last_line_noop(workspace: Path, five_line_file: Path):
    """Moving the last content line down is a no-op."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        original = ta.text
        lines = original.split("\n")
        last_row = len(lines) - 1
        ta.cursor_location = (last_row, 0)
        ta.action_move_line_down()
        assert ta.text == original
        assert ta.cursor_location == (last_row, 0)


async def test_move_line_down_preserves_column(workspace: Path, five_line_file: Path):
    """Column position is preserved after moving down."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        ta.cursor_location = (0, 2)
        ta.action_move_line_down()
        assert ta.cursor_location == (1, 2)


# ── Move Down: multi-line selection ──────────────────────────────────────────


async def test_move_line_down_multi_line_selection(
    workspace: Path, five_line_file: Path
):
    """Selecting lines 0-1 and moving down shifts the block below line 2."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        ta.selection = Selection(start=(0, 0), end=(1, 3))
        ta.action_move_line_down()
        lines = ta.text.split("\n")
        assert lines[0] == "ccc"
        assert lines[1] == "aaa"
        assert lines[2] == "bbb"
        assert ta.selection.start == (1, 0)
        assert ta.selection.end == (2, 3)


async def test_move_line_down_selection_end_col0(workspace: Path, five_line_file: Path):
    """Selection ending at col 0 of a row excludes that row from the block."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        # Select from (0,0) to (2,0) — should only move rows 0-1
        ta.selection = Selection(start=(0, 0), end=(2, 0))
        ta.action_move_line_down()
        lines = ta.text.split("\n")
        assert lines[0] == "ccc"
        assert lines[1] == "aaa"
        assert lines[2] == "bbb"


# ── Move Up: single cursor ──────────────────────────────────────────────────


async def test_move_line_up_single_cursor(workspace: Path, five_line_file: Path):
    """Moving line 2 up swaps it with line 1; cursor follows."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        ta.cursor_location = (2, 0)
        ta.action_move_line_up()
        lines = ta.text.split("\n")
        assert lines[1] == "ccc"
        assert lines[2] == "bbb"
        assert ta.cursor_location == (1, 0)


async def test_move_line_up_first_line_noop(workspace: Path, five_line_file: Path):
    """Moving the first line up is a no-op."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        original = ta.text
        ta.cursor_location = (0, 0)
        ta.action_move_line_up()
        assert ta.text == original
        assert ta.cursor_location == (0, 0)


async def test_move_line_up_preserves_column(workspace: Path, five_line_file: Path):
    """Column position is preserved after moving up."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        ta.cursor_location = (2, 2)
        ta.action_move_line_up()
        assert ta.cursor_location == (1, 2)


# ── Move Up: multi-line selection ────────────────────────────────────────────


async def test_move_line_up_multi_line_selection(workspace: Path, five_line_file: Path):
    """Selecting lines 1-2 and moving up shifts the block above line 0."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        ta.selection = Selection(start=(1, 0), end=(2, 3))
        ta.action_move_line_up()
        lines = ta.text.split("\n")
        assert lines[0] == "bbb"
        assert lines[1] == "ccc"
        assert lines[2] == "aaa"
        assert ta.selection.start == (0, 0)
        assert ta.selection.end == (1, 3)


async def test_move_line_up_selection_end_col0(workspace: Path, five_line_file: Path):
    """Selection ending at col 0 excludes that row (move up)."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        # Select from (1,0) to (3,0) — should only move rows 1-2
        ta.selection = Selection(start=(1, 0), end=(3, 0))
        ta.action_move_line_up()
        lines = ta.text.split("\n")
        assert lines[0] == "bbb"
        assert lines[1] == "ccc"
        assert lines[2] == "aaa"


# ── Edge cases ───────────────────────────────────────────────────────────────


async def test_move_line_single_line_file_noop(workspace: Path, single_line_file: Path):
    """Single-line file: move down and up are both no-ops."""
    app = make_app(workspace, light=True, open_file=single_line_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        original = ta.text
        ta.action_move_line_down()
        assert ta.text == original
        ta.action_move_line_up()
        assert ta.text == original


async def test_move_line_down_reverse_selection(workspace: Path, five_line_file: Path):
    """Reverse selection (start > end) still moves the correct row range."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        # Reverse selection: anchor at row 1, cursor at row 0
        ta.selection = Selection(start=(1, 3), end=(0, 0))
        ta.action_move_line_down()
        lines = ta.text.split("\n")
        assert lines[0] == "ccc"
        assert lines[1] == "aaa"
        assert lines[2] == "bbb"


async def test_move_line_empty_file_noop(workspace: Path, empty_file: Path):
    """Empty file: move is a no-op."""
    app = make_app(workspace, light=True, open_file=empty_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        original = ta.text
        ta.action_move_line_down()
        assert ta.text == original
        ta.action_move_line_up()
        assert ta.text == original


# ── Multi-cursor ─────────────────────────────────────────────────────────────


async def test_move_line_down_multi_cursor(workspace: Path, five_line_file: Path):
    """Two cursors on different rows: both lines move down."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        ta.cursor_location = (0, 0)
        ta.add_cursor((2, 0))
        ta.action_move_line_down()
        lines = ta.text.split("\n")
        # line 0 (aaa) moved to 1, line 2 (ccc) moved to 3
        assert lines[0] == "bbb"
        assert lines[1] == "aaa"
        assert lines[2] == "ddd"
        assert lines[3] == "ccc"


async def test_move_line_down_blocked_at_bottom(workspace: Path, five_line_file: Path):
    """If any cursor is at the last line, entire operation is no-op."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        original = ta.text
        last_row = len(original.split("\n")) - 1
        ta.cursor_location = (0, 0)
        ta.add_cursor((last_row, 0))
        ta.action_move_line_down()
        assert ta.text == original


async def test_move_line_up_multi_cursor(workspace: Path, five_line_file: Path):
    """Two cursors on different rows: both lines move up."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        ta.cursor_location = (2, 0)
        ta.add_cursor((4, 0))
        ta.action_move_line_up()
        lines = ta.text.split("\n")
        # line 2 (ccc) moved to 1, line 4 (eee) moved to 3
        assert lines[1] == "ccc"
        assert lines[2] == "bbb"
        assert lines[3] == "eee"
        assert lines[4] == "ddd"


async def test_move_line_up_blocked_at_top(workspace: Path, five_line_file: Path):
    """If any cursor is at line 0, entire operation is no-op."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        original = ta.text
        ta.cursor_location = (0, 0)
        ta.add_cursor((3, 0))
        ta.action_move_line_up()
        assert ta.text == original


# ── Keybinding integration ───────────────────────────────────────────────────


async def test_alt_down_key(workspace: Path, five_line_file: Path):
    """Alt+Down key binding moves the current line down."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        ta.cursor_location = (0, 0)
        await pilot.wait_for_scheduled_animations()
        await pilot.press("alt+down")
        await pilot.wait_for_scheduled_animations()
        lines = ta.text.split("\n")
        assert lines[0] == "bbb"
        assert lines[1] == "aaa"


async def test_alt_up_key(workspace: Path, five_line_file: Path):
    """Alt+Up key binding moves the current line up."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        ta.cursor_location = (2, 0)
        await pilot.wait_for_scheduled_animations()
        await pilot.press("alt+up")
        await pilot.wait_for_scheduled_animations()
        lines = ta.text.split("\n")
        assert lines[1] == "ccc"
        assert lines[2] == "bbb"


# ── Scroll viewport ─────────────────────────────────────────────────────────


async def test_ctrl_down_scrolls(workspace: Path) -> None:
    """Ctrl+Down scrolls viewport; cursor position unchanged."""
    # Create a long file to ensure scrollability
    f = workspace / "long.txt"
    f.write_text("\n".join(f"line{i}" for i in range(100)) + "\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        ta.cursor_location = (0, 0)
        await pilot.wait_for_scheduled_animations()
        cursor_before = ta.cursor_location
        ta.action_scroll_down()
        await pilot.wait_for_scheduled_animations()
        assert ta.cursor_location == cursor_before


async def test_ctrl_up_scrolls(workspace: Path) -> None:
    """Ctrl+Up scrolls viewport; cursor position unchanged."""
    f = workspace / "long.txt"
    f.write_text("\n".join(f"line{i}" for i in range(100)) + "\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        ta.cursor_location = (0, 0)
        await pilot.wait_for_scheduled_animations()
        cursor_before = ta.cursor_location
        ta.action_scroll_up()
        await pilot.wait_for_scheduled_animations()
        assert ta.cursor_location == cursor_before
