"""Tests for double/triple click word/line selection in MultiCursorTextArea."""

from pathlib import Path

import pytest
from textual import events
from textual.widgets.text_area import Selection

from tests.conftest import make_app
from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea


def _make_click(chain: int = 1) -> events.Click:
    """Create a Click event for testing with the given chain count."""
    return events.Click(
        None,
        x=0,
        y=0,
        delta_x=0,
        delta_y=0,
        button=1,
        shift=False,
        meta=False,
        ctrl=False,
        chain=chain,
    )


# ── Unit: _word_bounds_at ────────────────────────────────────────────────────


def test_word_bounds_at_returns_word_range():
    """_word_bounds_at returns (start, end) for word under cursor."""
    # "hello world" — cursor on 'w' of 'world' (col=6)
    bounds = MultiCursorTextArea._word_bounds_at("hello world", 0, 6)
    assert bounds == (6, 11)


def test_word_bounds_at_start_of_word():
    """_word_bounds_at works when cursor is at start of a word."""
    bounds = MultiCursorTextArea._word_bounds_at("hello world", 0, 0)
    assert bounds == (0, 5)


def test_word_bounds_at_end_of_word_minus_one():
    """_word_bounds_at works at last char of a word."""
    bounds = MultiCursorTextArea._word_bounds_at("hello world", 0, 4)
    assert bounds == (0, 5)


def test_word_bounds_at_whitespace_returns_none():
    """_word_bounds_at returns None when cursor is on whitespace."""
    bounds = MultiCursorTextArea._word_bounds_at("hello world", 0, 5)
    assert bounds is None


def test_word_bounds_at_eol_returns_none():
    """_word_bounds_at returns None when col is at or past end of line."""
    bounds = MultiCursorTextArea._word_bounds_at("hello", 0, 5)
    assert bounds is None


def test_word_bounds_at_empty_line():
    """_word_bounds_at returns None for empty line."""
    bounds = MultiCursorTextArea._word_bounds_at("", 0, 0)
    assert bounds is None


# ── Integration: double-click selects word ───────────────────────────────────


@pytest.fixture
def word_file(workspace: Path) -> Path:
    f = workspace / "words.txt"
    f.write_text("hello world\nfoo bar\n")
    return f


async def test_double_click_selects_word(workspace: Path, word_file: Path):
    """Double-click on a word selects that full word."""
    app = make_app(workspace, open_file=word_file, light=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.wait_for_scheduled_animations()
        _ce = app.main_view.get_active_code_editor()
        assert _ce is not None
        ta = _ce.editor

        # Place cursor on 'world' (col 6 of row 0), then simulate double-click
        ta.cursor_location = (0, 6)
        ta.on_click(_make_click(chain=2))
        await pilot.wait_for_scheduled_animations()

        assert ta.selection == Selection((0, 6), (0, 11))


async def test_double_click_whitespace_no_selection(workspace: Path, word_file: Path):
    """Double-click on whitespace does not change selection."""
    app = make_app(workspace, open_file=word_file, light=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.wait_for_scheduled_animations()
        _ce = app.main_view.get_active_code_editor()
        assert _ce is not None
        ta = _ce.editor

        # Place cursor on space between 'hello' and 'world' (col 5)
        ta.cursor_location = (0, 5)
        original_sel = ta.selection
        ta.on_click(_make_click(chain=2))
        await pilot.wait_for_scheduled_animations()

        # Selection should be unchanged (collapsed at (0,5))
        assert ta.selection == original_sel


async def test_double_click_eol_no_selection(workspace: Path, word_file: Path):
    """Double-click at EOL does not change selection."""
    app = make_app(workspace, open_file=word_file, light=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.wait_for_scheduled_animations()
        _ce = app.main_view.get_active_code_editor()
        assert _ce is not None
        ta = _ce.editor

        # Place cursor at EOL
        ta.cursor_location = (0, 11)
        ta.on_click(_make_click(chain=2))
        await pilot.wait_for_scheduled_animations()

        # Selection stays collapsed at EOL
        assert ta.selection.start == ta.selection.end


async def test_triple_click_selects_line(workspace: Path, word_file: Path):
    """Triple-click on a non-empty line selects the entire line."""
    app = make_app(workspace, open_file=word_file, light=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.wait_for_scheduled_animations()
        _ce = app.main_view.get_active_code_editor()
        assert _ce is not None
        ta = _ce.editor

        ta.cursor_location = (0, 3)
        ta.on_click(_make_click(chain=3))
        await pilot.wait_for_scheduled_animations()

        assert ta.selection == Selection((0, 0), (0, 11))


async def test_triple_click_empty_line(workspace: Path, workspace_with_empty: Path):
    """Triple-click on an empty line — cursor stays at (row, 0), no error."""
    app = make_app(workspace, open_file=workspace_with_empty, light=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.wait_for_scheduled_animations()
        _ce = app.main_view.get_active_code_editor()
        assert _ce is not None
        ta = _ce.editor

        # Line 1 is empty
        ta.cursor_location = (1, 0)
        ta.on_click(_make_click(chain=3))
        await pilot.wait_for_scheduled_animations()

        assert ta.selection == Selection((1, 0), (1, 0))


@pytest.fixture
def workspace_with_empty(workspace: Path) -> Path:
    f = workspace / "empty_line.txt"
    f.write_text("first line\n\nthird line\n")
    return f


async def test_double_click_clears_extra_cursors(workspace: Path, word_file: Path):
    """Double-click clears extra cursors and selects the word."""
    app = make_app(workspace, open_file=word_file, light=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.wait_for_scheduled_animations()
        _ce = app.main_view.get_active_code_editor()
        assert _ce is not None
        ta = _ce.editor

        # Add an extra cursor
        ta.add_cursor((1, 0))
        assert ta.extra_cursors != []

        # Double-click on 'hello'
        ta.cursor_location = (0, 2)
        ta.on_click(_make_click(chain=2))
        await pilot.wait_for_scheduled_animations()

        assert ta.extra_cursors == []
        assert ta.selection == Selection((0, 0), (0, 5))


async def test_single_click_clears_extra_cursors(workspace: Path, word_file: Path):
    """Single click clears extra cursors."""
    app = make_app(workspace, open_file=word_file, light=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.wait_for_scheduled_animations()
        _ce = app.main_view.get_active_code_editor()
        assert _ce is not None
        ta = _ce.editor

        # Add an extra cursor
        ta.add_cursor((1, 0))
        assert ta.extra_cursors != []

        # Simulate single click
        ta.on_click(_make_click(chain=1))
        await pilot.wait_for_scheduled_animations()

        assert ta.extra_cursors == []


async def test_single_click_clears_extra_cursors_integration(
    workspace: Path, word_file: Path
):
    """Single click via pilot.click clears extra cursors (full event flow)."""
    app = make_app(workspace, open_file=word_file, light=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.wait_for_scheduled_animations()
        _ce = app.main_view.get_active_code_editor()
        assert _ce is not None
        ta = _ce.editor

        # Add an extra cursor
        ta.add_cursor((1, 0))
        assert ta.extra_cursors != []

        # Click via pilot (triggers _on_mouse_down → on_click)
        await pilot.click(type(ta))
        await pilot.wait_for_scheduled_animations()

        assert ta.extra_cursors == []
