"""
Move lines up/down tests ported from VSCode's moveLinesCommand.test.ts.

Source: src/vs/editor/contrib/linesOperations/test/browser/moveLinesCommand.test.ts
VSCode uses 1-based positions; all values here are converted to 0-based.

Ported: "Editor Contrib - Move Lines Command" suite (10 tests, no indent rules).
Skipped: "honors Indentation Rules" suite (3 tests) and "honors onEnter Rules"
suite (1 test) — our editor does not support auto-indent rules.

Test text (same as VSCode):
    LINE0 = "first"         (5 chars)
    LINE1 = "second line"   (11 chars)
    LINE2 = "third line"    (10 chars)
    LINE3 = "fourth line"   (11 chars)
    LINE4 = "fifth"         (5 chars)
"""

from pathlib import Path

import pytest
from textual.widgets.text_area import Selection

from tests.conftest import make_app

# ── Test text ────────────────────────────────────────────────────────────────
# Same 5-line text used by VSCode's moveLinesCommand.test.ts.

LINE0 = "first"  # 5 chars
LINE1 = "second line"  # 11 chars
LINE2 = "third line"  # 10 chars
LINE3 = "fourth line"  # 11 chars
LINE4 = "fifth"  # 5 chars

LINES = [LINE0, LINE1, LINE2, LINE3, LINE4]
TEXT = "\n".join(LINES)


@pytest.fixture
def move_lines_file(workspace: Path) -> Path:
    f = workspace / "move_lines.txt"
    f.write_text(TEXT)
    return f


async def _get_ta(app, pilot):
    """After entering run_test, pause and return the TextArea."""
    await pilot.pause()
    ce = app.main_view.get_active_code_editor()
    assert ce is not None, "No active code editor found"
    return ce.editor


# ── No-op boundaries ────────────────────────────────────────────────────────
# VSCode: 'move first up / last down disabled'


async def test_move_first_line_up_noop(workspace: Path, move_lines_file: Path):
    """Moving the first line up is a no-op."""
    app = make_app(workspace, light=True, open_file=move_lines_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        # VSCode: Selection(1, 1, 1, 1) → cursor at (0, 0)
        ta.selection = Selection.cursor((0, 0))
        ta.action_move_line_up()
        assert ta.text == TEXT
        assert ta.selection == Selection.cursor((0, 0))


async def test_move_last_line_down_noop(workspace: Path, move_lines_file: Path):
    """Moving the last line down is a no-op."""
    app = make_app(workspace, light=True, open_file=move_lines_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        # VSCode: Selection(5, 1, 5, 1) → cursor at (4, 0)
        ta.selection = Selection.cursor((4, 0))
        ta.action_move_line_down()
        assert ta.text == TEXT
        assert ta.selection == Selection.cursor((4, 0))


# ── Single line moves ───────────────────────────────────────────────────────
# VSCode: 'move first line down'


async def test_move_first_line_down(workspace: Path, move_lines_file: Path):
    """Move first line down with backward selection; selection follows."""
    app = make_app(workspace, light=True, open_file=move_lines_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        # VSCode: Selection(1, 4, 1, 1) → anchor=(0,3), cursor=(0,0) — backward
        ta.selection = Selection(start=(0, 3), end=(0, 0))
        ta.action_move_line_down()
        expected = "\n".join([LINE1, LINE0, LINE2, LINE3, LINE4])
        assert ta.text == expected
        # VSCode: Selection(2, 4, 2, 1) → anchor=(1,3), cursor=(1,0)
        assert ta.selection == Selection(start=(1, 3), end=(1, 0))


# VSCode: 'move 2nd line up'


async def test_move_2nd_line_up(workspace: Path, move_lines_file: Path):
    """Move second line up; cursor at start of line."""
    app = make_app(workspace, light=True, open_file=move_lines_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        # VSCode: Selection(2, 1, 2, 1) → cursor at (1, 0)
        ta.selection = Selection.cursor((1, 0))
        ta.action_move_line_up()
        expected = "\n".join([LINE1, LINE0, LINE2, LINE3, LINE4])
        assert ta.text == expected
        assert ta.selection == Selection.cursor((0, 0))


# VSCode: 'issue #1322a: move 2nd line up'


async def test_issue_1322a_move_2nd_line_up_col_preserved(
    workspace: Path, move_lines_file: Path
):
    """Issue #1322a: cursor column at end of line preserved after move up."""
    app = make_app(workspace, light=True, open_file=move_lines_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        # VSCode: Selection(2, 12, 2, 12) → cursor at (1, 11)
        # "second line" has 11 chars, so col 11 (0-based) = end of line
        ta.selection = Selection.cursor((1, 11))
        ta.action_move_line_up()
        expected = "\n".join([LINE1, LINE0, LINE2, LINE3, LINE4])
        assert ta.text == expected
        # VSCode: Selection(1, 12, 1, 12) → cursor at (0, 11)
        assert ta.selection == Selection.cursor((0, 11))


# VSCode: 'issue #1322b: move last line up'


async def test_issue_1322b_move_last_line_up(workspace: Path, move_lines_file: Path):
    """Issue #1322b: move last line up; cursor column preserved."""
    app = make_app(workspace, light=True, open_file=move_lines_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        # VSCode: Selection(5, 6, 5, 6) → cursor at (4, 5)
        # "fifth" has 5 chars, col 5 (0-based) = end of line
        ta.selection = Selection.cursor((4, 5))
        ta.action_move_line_up()
        expected = "\n".join([LINE0, LINE1, LINE2, LINE4, LINE3])
        assert ta.text == expected
        # VSCode: Selection(4, 6, 4, 6) → cursor at (3, 5)
        assert ta.selection == Selection.cursor((3, 5))


# VSCode: 'issue #1322c: move last line selected up'


async def test_issue_1322c_move_last_line_selected_up(
    workspace: Path, move_lines_file: Path
):
    """Issue #1322c: move last line up with backward selection."""
    app = make_app(workspace, light=True, open_file=move_lines_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        # VSCode: Selection(5, 6, 5, 1) → anchor=(4,5), cursor=(4,0)
        ta.selection = Selection(start=(4, 5), end=(4, 0))
        ta.action_move_line_up()
        expected = "\n".join([LINE0, LINE1, LINE2, LINE4, LINE3])
        assert ta.text == expected
        # VSCode: Selection(4, 6, 4, 1) → anchor=(3,5), cursor=(3,0)
        assert ta.selection == Selection(start=(3, 5), end=(3, 0))


# VSCode: 'move last line up'


async def test_move_last_line_up(workspace: Path, move_lines_file: Path):
    """Move last line up; cursor at start of line."""
    app = make_app(workspace, light=True, open_file=move_lines_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        # VSCode: Selection(5, 1, 5, 1) → cursor at (4, 0)
        ta.selection = Selection.cursor((4, 0))
        ta.action_move_line_up()
        expected = "\n".join([LINE0, LINE1, LINE2, LINE4, LINE3])
        assert ta.text == expected
        # VSCode: Selection(4, 1, 4, 1) → cursor at (3, 0)
        assert ta.selection == Selection.cursor((3, 0))


# VSCode: 'move 4th line down'


async def test_move_4th_line_down(workspace: Path, move_lines_file: Path):
    """Move 4th line (0-based: line 3) down; swaps with last line."""
    app = make_app(workspace, light=True, open_file=move_lines_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        # VSCode: Selection(4, 1, 4, 1) → cursor at (3, 0)
        ta.selection = Selection.cursor((3, 0))
        ta.action_move_line_down()
        expected = "\n".join([LINE0, LINE1, LINE2, LINE4, LINE3])
        assert ta.text == expected
        # VSCode: Selection(5, 1, 5, 1) → cursor at (4, 0)
        assert ta.selection == Selection.cursor((4, 0))


# ── Multi-line selection moves ──────────────────────────────────────────────
# VSCode: 'move multiple lines down'


async def test_move_multiple_lines_down(workspace: Path, move_lines_file: Path):
    """Move lines 1-3 (0-based) down with backward selection; block shifts."""
    app = make_app(workspace, light=True, open_file=move_lines_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        # VSCode: Selection(4, 4, 2, 2) → anchor=(3,3), cursor=(1,1) — backward
        ta.selection = Selection(start=(3, 3), end=(1, 1))
        ta.action_move_line_down()
        # Lines 1-3 shift down by one, line 4 goes above them
        expected = "\n".join([LINE0, LINE4, LINE1, LINE2, LINE3])
        assert ta.text == expected
        # VSCode: Selection(5, 4, 3, 2) → anchor=(4,3), cursor=(2,1)
        assert ta.selection == Selection(start=(4, 3), end=(2, 1))


# VSCode: 'invisible selection is ignored'


async def test_invisible_selection_is_ignored(workspace: Path, move_lines_file: Path):
    """Backward selection ending at col 0: that row is excluded from the move.

    VSCode calls this "invisible selection" — the selection technically spans
    two lines, but the second line is only touched at column 0 (beginning of
    line), so it should not be included in the moved block.
    """
    app = make_app(workspace, light=True, open_file=move_lines_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        # VSCode: Selection(2, 1, 1, 1) → anchor=(1,0), cursor=(0,0) — backward
        # Normalized range: (0,0) to (1,0) — col 0 exclusion → only row 0
        ta.selection = Selection(start=(1, 0), end=(0, 0))
        ta.action_move_line_down()
        expected = "\n".join([LINE1, LINE0, LINE2, LINE3, LINE4])
        assert ta.text == expected
        # VSCode: Selection(3, 1, 2, 1) → anchor=(2,0), cursor=(1,0)
        assert ta.selection == Selection(start=(2, 0), end=(1, 0))


# ── Indent rules suite (skipped) ────────────────────────────────────────────
# The following VSCode test suites are NOT ported because our editor does not
# support auto-indent rules:
#
# - "Editor contrib - Move Lines Command honors Indentation Rules" (3 tests)
#   - 'first line indentation adjust to 0' (issue #28552)
#   - 'move lines across block' (issue #28552)
#   - 'move line should still work as before if there is no indentation rules'
#
# - "Editor - contrib - Move Lines Command honors onEnter Rules" (1 test)
#   - 'issue #54829. move block across block'
