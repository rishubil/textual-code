"""
Sort lines tests ported from VSCode's sortLinesCommand.test.ts.

Source: src/vs/editor/contrib/linesOperations/test/browser/sortLinesCommand.test.ts
VSCode uses 1-based positions; all values here are converted to 0-based.

Test text (same as VSCode):
    LINE0 = "first"         (5 chars)
    LINE1 = "second line"   (11 chars)
    LINE2 = "third line"    (10 chars)
    LINE3 = "fourth line"   (11 chars)
    LINE4 = "fifth"         (5 chars)

Behavioral differences from VSCode:
    1. Selection end column adjustment: VSCode adjusts the selection end column
       after sort (e.g., if line content at cursor end changes length). Our editor
       preserves the original selection coordinates unchanged.
"""

from pathlib import Path

import pytest
from textual.widgets.text_area import Selection

from tests.conftest import make_app

# ── Test text ────────────────────────────────────────────────────────────────
# Same 5-line text used by VSCode's sortLinesCommand.test.ts

LINE0 = "first"  # 5 chars
LINE1 = "second line"  # 11 chars
LINE2 = "third line"  # 10 chars
LINE3 = "fourth line"  # 11 chars
LINE4 = "fifth"  # 5 chars

LINES = [LINE0, LINE1, LINE2, LINE3, LINE4]
TEXT = "\n".join(LINES)


@pytest.fixture
def sort_test_file(workspace: Path) -> Path:
    f = workspace / "sort_test.txt"
    f.write_text(TEXT)
    return f


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _get_ta(app, pilot):
    """After entering run_test, pause and return the TextArea."""
    await pilot.pause()
    ce = app.main_view.get_active_code_editor()
    assert ce is not None, "No active code editor found"
    return ce.editor


# ── No-op: single line selection ─────────────────────────────────────────────
# VSCode: 'no op unless at least two lines selected 1'
# Selection entirely within line 0: Selection(1,3, 1,1) → 0-based: (0,2)→(0,0)


async def test_noop_single_line_selection(workspace: Path, sort_test_file: Path):
    """VSCode: sort is a no-op when selection is within a single line."""
    app = make_app(workspace, light=True, open_file=sort_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        ta.selection = Selection((0, 2), (0, 0))
        original = ta.text
        ta.action_sort_lines_ascending()
        await pilot.pause()
        assert ta.text == original, "Single-line selection should be a no-op"


# ── No-op: selection ends at col 0 of next line ─────────────────────────────
# VSCode: 'no op unless at least two lines selected 2'
# Selection(1,3, 2,1) → 0-based: (0,2)→(1,0)
# When selection ends at col 0 of the next line, _row_range excludes that line,
# leaving only line 0 selected → single line → no-op.


async def test_noop_selection_ends_at_col0_next_line(
    workspace: Path, sort_test_file: Path
):
    """VSCode: selection ending at col 0 of next line counts as single line."""
    app = make_app(workspace, light=True, open_file=sort_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        ta.selection = Selection((0, 2), (1, 0))
        original = ta.text
        ta.action_sort_lines_ascending()
        await pilot.pause()
        assert ta.text == original, (
            "Selection ending at col 0 of next line should be single-line no-op"
        )


# ── Sort two lines ascending ────────────────────────────────────────────────
# VSCode: 'sorting two lines ascending'
# Selection(3,3, 4,2) → 0-based: (2,2)→(3,1)
# Lines 2-3 ("third line", "fourth line") → sorted: ("fourth line", "third line")


async def test_sort_two_lines_ascending(workspace: Path, sort_test_file: Path):
    """VSCode: sort lines 2-3 ascending swaps 'third line' and 'fourth line'."""
    app = make_app(workspace, light=True, open_file=sort_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        ta.selection = Selection((2, 2), (3, 1))
        ta.action_sort_lines_ascending()
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines == ["first", "second line", "fourth line", "third line", "fifth"]


# ── Sort first 4 lines ascending ─────────────────────────────────────────────
# VSCode: 'sorting first 4 lines ascending'
# Selection(1,1, 5,1) → 0-based: (0,0)→(4,0)
# Col 0 exclusion: range is lines 0-3 only.
# Lines 0-3: ["first", "second line", "third line", "fourth line"]
# Sorted ascending: ["first", "fourth line", "second line", "third line"]


async def test_sort_first_4_lines_ascending(workspace: Path, sort_test_file: Path):
    """VSCode: sort first 4 lines ascending (col 0 exclusion on line 4)."""
    app = make_app(workspace, light=True, open_file=sort_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        ta.selection = Selection((0, 0), (4, 0))
        ta.action_sort_lines_ascending()
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines == ["first", "fourth line", "second line", "third line", "fifth"]


# ── Sort all lines ascending ────────────────────────────────────────────────
# VSCode: 'sorting all lines ascending'
# Selection(1,1, 5,6) → 0-based: (0,0)→(4,5)
# All 5 lines sorted: ["fifth", "first", "fourth line", "second line", "third line"]


async def test_sort_all_lines_ascending(workspace: Path, sort_test_file: Path):
    """VSCode: sort all 5 lines ascending."""
    app = make_app(workspace, light=True, open_file=sort_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        ta.selection = Selection((0, 0), (4, 5))
        ta.action_sort_lines_ascending()
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines == ["fifth", "first", "fourth line", "second line", "third line"]


# ── Sort first 4 lines descending ───────────────────────────────────────────
# VSCode: 'sorting first 4 lines descending'
# Selection(1,1, 5,1) → 0-based: (0,0)→(4,0)
# Col 0 exclusion: range is lines 0-3.
# Lines 0-3 sorted descending: ["third line", "second line", "fourth line", "first"]


async def test_sort_first_4_lines_descending(workspace: Path, sort_test_file: Path):
    """VSCode: sort first 4 lines descending (col 0 exclusion on line 4)."""
    app = make_app(workspace, light=True, open_file=sort_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        ta.selection = Selection((0, 0), (4, 0))
        ta.action_sort_lines_descending()
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines == ["third line", "second line", "fourth line", "first", "fifth"]


# ── Sort all lines descending ───────────────────────────────────────────────
# VSCode: 'sorting all lines descending'
# Selection(1,1, 5,6) → 0-based: (0,0)→(4,5)
# All 5 lines sorted descending:
# ["third line", "second line", "fourth line", "first", "fifth"]


async def test_sort_all_lines_descending(workspace: Path, sort_test_file: Path):
    """VSCode: sort all 5 lines descending."""
    app = make_app(workspace, light=True, open_file=sort_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        ta.selection = Selection((0, 0), (4, 5))
        ta.action_sort_lines_descending()
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines == ["third line", "second line", "fourth line", "first", "fifth"]
