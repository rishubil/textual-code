"""
Sort selected lines tests.

Tests for the sort lines ascending/descending feature (Issue #37).
Available via command palette only — no keybindings.
"""

from pathlib import Path

import pytest
from textual.widgets.text_area import Selection

from tests.conftest import make_app

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def unsorted_file(workspace: Path) -> Path:
    f = workspace / "unsorted.txt"
    f.write_text("cherry\napple\nbanana\ndelta\n")
    return f


@pytest.fixture
def single_line_file(workspace: Path) -> Path:
    f = workspace / "single.txt"
    f.write_text("only line")
    return f


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_editor(app):
    """Return the MultiCursorTextArea from the active code editor."""
    return app.main_view.get_active_code_editor().editor


# ── Sort ascending ────────────────────────────────────────────────────────────


async def test_sort_lines_ascending(workspace: Path, unsorted_file: Path):
    """Selecting lines 0-2 and sorting ascending produces alphabetical order."""
    app = make_app(workspace, light=True, open_file=unsorted_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_editor(app)
        ta.selection = Selection(start=(0, 0), end=(2, 6))
        ta.action_sort_lines_ascending()
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines[0] == "apple"
        assert lines[1] == "banana"
        assert lines[2] == "cherry"
        # Line 3 should be unchanged
        assert lines[3] == "delta"


# ── Sort descending ──────────────────────────────────────────────────────────


async def test_sort_lines_descending(workspace: Path, unsorted_file: Path):
    """Selecting lines 0-2 and sorting descending produces reverse order."""
    app = make_app(workspace, light=True, open_file=unsorted_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_editor(app)
        ta.selection = Selection(start=(0, 0), end=(2, 6))
        ta.action_sort_lines_descending()
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines[0] == "cherry"
        assert lines[1] == "banana"
        assert lines[2] == "apple"
        assert lines[3] == "delta"


# ── No-op cases ───────────────────────────────────────────────────────────────


async def test_sort_lines_single_line_noop(workspace: Path, unsorted_file: Path):
    """Sorting a single selected line is a no-op."""
    app = make_app(workspace, light=True, open_file=unsorted_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_editor(app)
        original = ta.text
        ta.selection = Selection(start=(0, 0), end=(0, 6))
        ta.action_sort_lines_ascending()
        await pilot.pause()
        assert ta.text == original


async def test_sort_lines_no_selection_noop(workspace: Path, unsorted_file: Path):
    """Sorting with just a cursor (no selection) is a no-op."""
    app = make_app(workspace, light=True, open_file=unsorted_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_editor(app)
        original = ta.text
        ta.cursor_location = (1, 0)
        ta.action_sort_lines_ascending()
        await pilot.pause()
        assert ta.text == original


# ── Case sensitivity ─────────────────────────────────────────────────────────


async def test_sort_lines_case_sensitive(workspace: Path):
    """Sort is case-sensitive: uppercase before lowercase (VS Code default)."""
    f = workspace / "mixed_case.txt"
    f.write_text("banana\nApple\ncherry\nBanana\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_editor(app)
        ta.selection = Selection(start=(0, 0), end=(3, 6))
        ta.action_sort_lines_ascending()
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines[0] == "Apple"
        assert lines[1] == "Banana"
        assert lines[2] == "banana"
        assert lines[3] == "cherry"


# ── Edge cases ────────────────────────────────────────────────────────────────


async def test_sort_lines_with_empty_lines(workspace: Path):
    """Empty lines within selection are sorted to the top."""
    f = workspace / "with_empty.txt"
    f.write_text("cherry\n\napple\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_editor(app)
        ta.selection = Selection(start=(0, 0), end=(2, 5))
        ta.action_sort_lines_ascending()
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines[0] == ""
        assert lines[1] == "apple"
        assert lines[2] == "cherry"


async def test_sort_lines_already_sorted(workspace: Path):
    """Sorting already-sorted text is idempotent."""
    f = workspace / "sorted.txt"
    f.write_text("apple\nbanana\ncherry\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_editor(app)
        original = ta.text
        ta.selection = Selection(start=(0, 0), end=(2, 6))
        ta.action_sort_lines_ascending()
        await pilot.pause()
        assert ta.text == original


async def test_sort_lines_with_duplicates(workspace: Path):
    """Duplicate lines are preserved in the output."""
    f = workspace / "dupes.txt"
    f.write_text("banana\napple\nbanana\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_editor(app)
        ta.selection = Selection(start=(0, 0), end=(2, 6))
        ta.action_sort_lines_ascending()
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines[0] == "apple"
        assert lines[1] == "banana"
        assert lines[2] == "banana"


async def test_sort_lines_partial_selection(workspace: Path, unsorted_file: Path):
    """Selection starting mid-line still sorts the full lines."""
    app = make_app(workspace, light=True, open_file=unsorted_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_editor(app)
        # Select from middle of line 0 to middle of line 2
        ta.selection = Selection(start=(0, 3), end=(2, 3))
        ta.action_sort_lines_ascending()
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines[0] == "apple"
        assert lines[1] == "banana"
        assert lines[2] == "cherry"


async def test_sort_lines_preserves_selection(workspace: Path, unsorted_file: Path):
    """After sorting, the selection covers the same row range."""
    app = make_app(workspace, light=True, open_file=unsorted_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_editor(app)
        ta.selection = Selection(start=(0, 0), end=(2, 6))
        ta.action_sort_lines_ascending()
        await pilot.pause()
        assert ta.selection.start == (0, 0)
        assert ta.selection.end == (2, 6)


# ── Command palette ──────────────────────────────────────────────────────────


async def test_sort_lines_command_palette(workspace: Path):
    """Sort commands are available in the system command palette."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        commands = list(app.get_system_commands(app.screen))
        titles = [cmd.title for cmd in commands]
        assert "Sort Lines Ascending" in titles
        assert "Sort Lines Descending" in titles
