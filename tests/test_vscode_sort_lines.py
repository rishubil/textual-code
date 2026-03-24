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

Selection tracking: VSCode adjusts selection positions after sort using
character offset tracking — positions are converted to char offsets within
the sorted range, then mapped back to (row, col) in the new text. Our
editor now replicates this behavior.
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
# Selection(1,3, 1,1) → 0-based: (0,2)→(0,0)


async def test_noop_single_line_selection(workspace: Path, sort_test_file: Path):
    """VSCode: sort is a no-op when selection is within a single line."""
    app = make_app(workspace, light=True, open_file=sort_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        sel = Selection((0, 2), (0, 0))
        ta.selection = sel
        original = ta.text
        ta.action_sort_lines_ascending()
        await pilot.pause()
        assert ta.text == original, "Single-line selection should be a no-op"
        assert ta.selection == sel, "Selection should be unchanged"


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
        sel = Selection((0, 2), (1, 0))
        ta.selection = sel
        original = ta.text
        ta.action_sort_lines_ascending()
        await pilot.pause()
        assert ta.text == original, (
            "Selection ending at col 0 of next line should be single-line no-op"
        )
        assert ta.selection == sel, "Selection should be unchanged"


# ── Sort two lines ascending ────────────────────────────────────────────────
# VSCode: 'sorting two lines ascending'
# Selection(3,3, 4,2) → 0-based: (2,2)→(3,1)
# Lines 2-3 sorted ascending: ("fourth line", "third line")
# VSCode selection after: (3,3, 4,1) → 0-based: (2,2)→(3,0)
# The end col shifts because char offset tracking maps the position through
# the sorted text.


async def test_sort_two_lines_ascending(workspace: Path, sort_test_file: Path):
    """VSCode: sort lines 2-3 ascending with selection tracking."""
    app = make_app(workspace, light=True, open_file=sort_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        ta.selection = Selection((2, 2), (3, 1))
        ta.action_sort_lines_ascending()
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines == ["first", "second line", "fourth line", "third line", "fifth"]
        # VSCode: Selection(3,3, 4,1) → 0-based: (2,2)→(3,0)
        assert ta.selection == Selection((2, 2), (3, 0))


# ── Sort first 4 lines ascending ─────────────────────────────────────────────
# VSCode: 'sorting first 4 lines ascending'
# Selection(1,1, 5,1) → 0-based: (0,0)→(4,0)
# Col 0 exclusion: range is lines 0-3 only.
# VSCode selection after: unchanged (0,0)→(4,0) — end is outside sorted range


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
        # VSCode: Selection(1,1, 5,1) → 0-based: (0,0)→(4,0) unchanged
        assert ta.selection == Selection((0, 0), (4, 0))


# ── Sort all lines ascending ────────────────────────────────────────────────
# VSCode: 'sorting all lines ascending'
# Selection(1,1, 5,6) → 0-based: (0,0)→(4,5)
# VSCode selection after: (1,1, 5,11) → 0-based: (0,0)→(4,10)
# End tracks to end of new last line "third line" (10 chars)


async def test_sort_all_lines_ascending(workspace: Path, sort_test_file: Path):
    """VSCode: sort all 5 lines ascending with selection tracking."""
    app = make_app(workspace, light=True, open_file=sort_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        ta.selection = Selection((0, 0), (4, 5))
        ta.action_sort_lines_ascending()
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines == ["fifth", "first", "fourth line", "second line", "third line"]
        # VSCode: Selection(1,1, 5,11) → 0-based: (0,0)→(4,10)
        assert ta.selection == Selection((0, 0), (4, 10))


# ── Sort first 4 lines descending ───────────────────────────────────────────
# VSCode: 'sorting first 4 lines descending'
# Selection(1,1, 5,1) → 0-based: (0,0)→(4,0)
# VSCode selection after: unchanged (0,0)→(4,0)


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
        # VSCode: Selection(1,1, 5,1) → 0-based: (0,0)→(4,0) unchanged
        assert ta.selection == Selection((0, 0), (4, 0))


# ── Sort all lines descending ───────────────────────────────────────────────
# VSCode: 'sorting all lines descending'
# Selection(1,1, 5,6) → 0-based: (0,0)→(4,5)
# VSCode selection after: (1,1, 5,6) → 0-based: (0,0)→(4,5) unchanged
# "fifth" stays as last line in descending, so end col stays at 5


async def test_sort_all_lines_descending(workspace: Path, sort_test_file: Path):
    """VSCode: sort all 5 lines descending with selection tracking."""
    app = make_app(workspace, light=True, open_file=sort_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        ta.selection = Selection((0, 0), (4, 5))
        ta.action_sort_lines_descending()
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines == ["third line", "second line", "fourth line", "first", "fifth"]
        # VSCode: Selection(1,1, 5,6) → 0-based: (0,0)→(4,5) unchanged
        assert ta.selection == Selection((0, 0), (4, 5))
