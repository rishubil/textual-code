"""
Cursor movement tests ported from VSCode's cursor.test.ts.

These tests verify basic cursor navigation (arrows, Home/End, selection,
select all) using the same scenarios as VSCode's editor test suite, adapted
for Textual's TextArea widget with 0-based position indexing.

Source: src/vs/editor/test/browser/controller/cursor.test.ts
VSCode uses 1-based positions; all values here are converted to 0-based.

All known behavioral differences from VSCode have been resolved:
- Smart home now uses VSCode-style toggle (first non-WS ↔ col 0).
- Sticky column is handled by Textual's TextArea via last_x_offset.
- ctrl+home / ctrl+end now bound in single-cursor mode via BINDINGS.
- Down at last line / Up at first line handled by Textual's navigator.
"""

from pathlib import Path

import pytest
from textual.widgets.text_area import Selection

from tests.conftest import make_app

# ── Test text ────────────────────────────────────────────────────────────────
# Adapted from VSCode cursor.test.ts.  Tabs replaced with spaces to avoid
# tab-width rendering differences between VSCode and Textual.

LINE0 = "     My First Line  "  # 20 chars
LINE1 = "  My Second Line"  # 16 chars
LINE2 = "    Third Line"  # 14 chars
LINE3 = ""  # 0 chars (empty line)
LINE4 = "1"  # 1 char

LINES = [LINE0, LINE1, LINE2, LINE3, LINE4]
TEXT = "\n".join(LINES)


@pytest.fixture
def cursor_test_file(workspace: Path) -> Path:
    f = workspace / "cursor_test.txt"
    f.write_text(TEXT)
    return f


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _setup(workspace, cursor_test_file, start=(0, 0)):
    """Create app and position cursor at *start*."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    return app, start


async def _get_ta(app, pilot, start=(0, 0)):
    """After entering run_test, pause and return the TextArea."""
    await pilot.pause()
    ce = app.main_view.get_active_code_editor()
    assert ce is not None, "No active code editor found"
    ta = ce.editor
    ta.selection = Selection.cursor(start)
    return ta


# ── Move Left ────────────────────────────────────────────────────────────────
# VSCode: cursor.test.ts "move left" section


@pytest.mark.parametrize(
    "start, expected",
    [
        pytest.param((0, 0), (0, 0), id="top-left-stays"),
        pytest.param((0, 2), (0, 1), id="basic"),
        pytest.param((1, 0), (0, len(LINE0)), id="wraps-to-prev-line"),
    ],
)
async def test_move_left(workspace, cursor_test_file, start, expected):
    """VSCode: 'move left on top left position', 'move left',
    'move left goes to previous row'."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, start)
        await pilot.press("left")
        assert ta.cursor_location == expected


async def test_move_left_selection(workspace: Path, cursor_test_file: Path):
    """VSCode: 'move left selection' — shift+left from line start wraps."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (1, 0))
        await pilot.press("shift+left")
        assert ta.selection == Selection((1, 0), (0, len(LINE0)))


# ── Move Right ───────────────────────────────────────────────────────────────
# VSCode: cursor.test.ts "move right" section


@pytest.mark.parametrize(
    "start, expected",
    [
        pytest.param((4, len(LINE4)), (4, len(LINE4)), id="bottom-right-stays"),
        pytest.param((0, 2), (0, 3), id="basic"),
        pytest.param((0, len(LINE0)), (1, 0), id="wraps-to-next-line"),
    ],
)
async def test_move_right(workspace, cursor_test_file, start, expected):
    """VSCode: 'move right on bottom right position', 'move right',
    'move right goes to next row'."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, start)
        await pilot.press("right")
        assert ta.cursor_location == expected


async def test_move_right_selection(workspace: Path, cursor_test_file: Path):
    """VSCode: 'move right selection' — shift+right from line end wraps."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, len(LINE0)))
        await pilot.press("shift+right")
        assert ta.selection == Selection((0, len(LINE0)), (1, 0))


# ── Move Down ────────────────────────────────────────────────────────────────
# VSCode: cursor.test.ts "move down" section


async def test_move_down_sequential(workspace: Path, cursor_test_file: Path):
    """VSCode: 'move down' — step through each line from top.

    Note: VSCode moves to end-of-line on last-line down press;
    our editor stays in place (behavioral difference).
    """
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))
        expected = [(1, 0), (2, 0), (3, 0), (4, 0)]
        for exp in expected:
            await pilot.press("down")
            assert ta.cursor_location == exp, (
                f"expected {exp}, got {ta.cursor_location}"
            )


async def test_move_down_with_selection_sequential(
    workspace: Path, cursor_test_file: Path
):
    """VSCode: 'move down with selection' — shift+down accumulates."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))
        expected_ends = [(1, 0), (2, 0), (3, 0), (4, 0)]
        for end in expected_ends:
            await pilot.press("shift+down")
            assert ta.selection == Selection((0, 0), end), (
                f"expected end={end}, got {ta.selection}"
            )


# ── Move Up ──────────────────────────────────────────────────────────────────
# VSCode: cursor.test.ts "move up" section


async def test_move_up(workspace: Path, cursor_test_file: Path):
    """VSCode: 'move up' — from line 2, col 4 move up twice.

    Note: without tabs, column stays at 4 (no visual-column difference).
    """
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (2, 4))
        await pilot.press("up")
        assert ta.cursor_location == (1, 4)
        await pilot.press("up")
        assert ta.cursor_location == (0, 4)


async def test_move_up_with_selection(workspace: Path, cursor_test_file: Path):
    """VSCode: 'move up with selection' — shift+up from line 2."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (2, 4))
        await pilot.press("shift+up")
        assert ta.selection == Selection((2, 4), (1, 4))
        await pilot.press("shift+up")
        assert ta.selection == Selection((2, 4), (0, 4))


# ── Move Up and Down with End of Lines ───────────────────────────────────────


async def test_move_down_clamps_to_shorter_line(
    workspace: Path, cursor_test_file: Path
):
    """Column is clamped to line length when moving to a shorter line.

    VSCode remembers the original column (sticky column) and restores it
    when returning to a longer line.  Our editor does not have sticky
    column, so the column stays clamped.  This test verifies our behavior.
    """
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))
        await pilot.press("end")
        assert ta.cursor_location == (0, len(LINE0))
        # Down to LINE1 (16 chars) — column clamped from 20 to 16
        await pilot.press("down")
        assert ta.cursor_location == (1, len(LINE1))
        # Down to LINE2 (14 chars) — column clamped from 16 to 14
        await pilot.press("down")
        assert ta.cursor_location == (2, len(LINE2))
        # Down to LINE3 (empty) — column clamped to 0
        await pilot.press("down")
        assert ta.cursor_location == (3, 0)


# ── Home / End ───────────────────────────────────────────────────────────────
# VSCode: cursor.test.ts "move to beginning/end of line" section
#
# TextArea has "smart home" (same as VSCode): Home toggles between the first
# non-whitespace character and column 0.
#   LINE0 first non-WS = 5  ("     My First Line  ")
#   LINE1 first non-WS = 2  ("  My Second Line")
#   LINE2 first non-WS = 4  ("    Third Line")
#   LINE3 first non-WS = 0  ("")
#   LINE4 first non-WS = 0  ("1")


@pytest.mark.parametrize(
    "start, expected",
    [
        # From after first non-WS → go to first non-WS
        pytest.param((0, 8), (0, 5), id="after-indent-to-first-non-ws"),
        # From first non-WS → go to column 0
        pytest.param((0, 5), (0, 0), id="from-first-non-ws-to-col-0"),
        # From column 0 → go to first non-WS
        pytest.param((0, 0), (0, 5), id="from-col-0-to-first-non-ws"),
        # From within indent (between col 0 and first non-WS) → go to first non-WS
        # (VSCode behavior: anything not at first-non-WS goes to first-non-WS)
        pytest.param((0, 2), (0, 5), id="from-indent-to-first-non-ws"),
        # Different line with different indent
        pytest.param((2, 7), (2, 4), id="line2-to-first-non-ws"),
        pytest.param((2, 4), (2, 0), id="line2-from-first-non-ws-to-col-0"),
        # Empty line — stays at 0
        pytest.param((3, 0), (3, 0), id="empty-line-stays"),
    ],
)
async def test_home(workspace, cursor_test_file, start, expected):
    """VSCode: 'move to beginning of line' — smart home behavior."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, start)
        await pilot.press("home")
        assert ta.cursor_location == expected


@pytest.mark.parametrize(
    "start, expected_end",
    [
        # Shift+Home from after indent → select to first non-WS
        pytest.param((0, 8), (0, 5), id="to-first-non-ws"),
        # Shift+Home from first non-WS → select to column 0
        pytest.param((0, 5), (0, 0), id="to-col-0"),
    ],
)
async def test_home_selection(workspace, cursor_test_file, start, expected_end):
    """VSCode: 'move to beginning of line from within line selection'."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, start)
        await pilot.press("shift+home")
        assert ta.selection == Selection(start, expected_end)


@pytest.mark.parametrize(
    "start, expected",
    [
        pytest.param((0, 0), (0, len(LINE0)), id="from-start"),
        pytest.param((0, 5), (0, len(LINE0)), id="from-within"),
        pytest.param((3, 0), (3, len(LINE3)), id="empty-line"),
        pytest.param((4, 0), (4, len(LINE4)), id="single-char-line"),
    ],
)
async def test_end(workspace, cursor_test_file, start, expected):
    """VSCode: 'move to end of line', 'move to end of line from within line'."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, start)
        await pilot.press("end")
        assert ta.cursor_location == expected


async def test_end_selection(workspace: Path, cursor_test_file: Path):
    """VSCode: 'move to end of line from within line selection'."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 5))
        await pilot.press("shift+end")
        assert ta.selection == Selection((0, 5), (0, len(LINE0)))


# ── Select All ───────────────────────────────────────────────────────────────
# VSCode: cursor.test.ts "select all" section


async def test_select_all(workspace: Path, cursor_test_file: Path):
    """VSCode: 'select all' — ctrl+a selects entire document."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (2, 3))
        await pilot.press("ctrl+a")
        assert ta.selection == Selection((0, 0), (4, len(LINE4)))


# ── Issue-based regression tests ─────────────────────────────────────────────
# VSCode: cursor.test.ts issue-based tests, adapted for our editor


async def test_end_key_collapses_selection_to_end(
    workspace: Path, cursor_test_file: Path
):
    """VSCode issue #15401: End key with active selection.

    When a multi-line selection is active and End is pressed (without Shift),
    the cursor moves to the end of the line where the cursor (end of
    selection) is, and the selection is collapsed.
    """
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))
        # Create forward selection from (0,0) to (2,5)
        ta.selection = Selection((0, 0), (2, 5))
        await pilot.press("end")
        # End collapses selection and moves to end of the cursor's line
        assert ta.cursor_location == (2, len(LINE2))
        assert ta.selection.start == ta.selection.end  # collapsed


async def test_home_key_collapses_selection_to_home(
    workspace: Path, cursor_test_file: Path
):
    """Adapted from VSCode issue #15401: Home key with active selection.

    When a multi-line selection is active and Home is pressed (without Shift),
    the cursor moves to the first non-whitespace of the cursor's line
    (smart home), and the selection is collapsed.
    """
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))
        # Create forward selection from (0,0) to (2,5)
        ta.selection = Selection((0, 0), (2, 5))
        await pilot.press("home")
        # Home collapses selection and moves to first non-WS of cursor's line
        assert ta.cursor_location == (2, 4)
        assert ta.selection.start == ta.selection.end  # collapsed


async def test_shift_end_extends_from_cursor_position(
    workspace: Path, cursor_test_file: Path
):
    """VSCode issue #17011: Shift+End extends selection from cursor position.

    With a multi-line selection active, Shift+End should extend the
    selection to the end of the line where the cursor (end of selection) is.
    """
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))
        # Create forward selection from (0,8) to (2,5)
        ta.selection = Selection((0, 8), (2, 5))
        await pilot.press("shift+end")
        # Shift+End extends from anchor (0,8) to end of cursor's line (2,14)
        assert ta.selection == Selection((0, 8), (2, len(LINE2)))


# ── VSCode behavioral difference tests ──────────────────────────────────────
# Tests below verify VSCode-matching behavior for known differences.
# Marked xfail where our editor intentionally or unavoidably differs.


async def test_down_at_last_line_moves_to_end(workspace: Path, cursor_test_file: Path):
    """VSCode: pressing Down on the last line should move cursor to end of line.

    VSCode cursor.test.ts 'move down': after reaching line 5 (content "1"),
    pressing Down again moves to (5, 2) in 1-based = (4, 1) in 0-based.
    """
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (4, 0))
        await pilot.press("down")
        assert ta.cursor_location == (4, len(LINE4)), (
            f"Down at last line should move to end; got {ta.cursor_location}"
        )


async def test_up_at_first_line_moves_to_start(workspace: Path, cursor_test_file: Path):
    """VSCode: pressing Up on the first line should move cursor to start of line.

    Symmetric to the Down-at-last-line behavior.
    """
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 5))
        await pilot.press("up")
        assert ta.cursor_location == (0, 0), (
            f"Up at first line should move to start; got {ta.cursor_location}"
        )


async def test_ctrl_home_single_cursor(workspace: Path, cursor_test_file: Path):
    """ctrl+home should move to document start even without extra cursors."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (2, 5))
        await pilot.press("ctrl+home")
        assert ta.cursor_location == (0, 0), (
            f"ctrl+home should go to (0,0); got {ta.cursor_location}"
        )


async def test_ctrl_end_single_cursor(workspace: Path, cursor_test_file: Path):
    """ctrl+end should move to document end even without extra cursors."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))
        await pilot.press("ctrl+end")
        assert ta.cursor_location == (4, len(LINE4)), (
            f"ctrl+end should go to end of document; got {ta.cursor_location}"
        )


async def test_ctrl_shift_home_single_cursor(workspace: Path, cursor_test_file: Path):
    """ctrl+shift+home should select from cursor to document start."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (2, 5))
        await pilot.press("ctrl+shift+home")
        assert ta.selection == Selection((2, 5), (0, 0)), (
            f"ctrl+shift+home should select to (0,0); got {ta.selection}"
        )


async def test_ctrl_shift_end_single_cursor(workspace: Path, cursor_test_file: Path):
    """ctrl+shift+end should select from cursor to document end."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))
        await pilot.press("ctrl+shift+end")
        assert ta.selection == Selection((0, 0), (4, len(LINE4))), (
            f"ctrl+shift+end should select to end; got {ta.selection}"
        )


async def test_smart_home_from_within_indent(workspace: Path, cursor_test_file: Path):
    """VSCode: Home from within indent should go to first non-WS, not col 0.

    VSCode smart home logic: if cursor == firstNonBlank → go to col 0;
    otherwise → go to firstNonBlank.  When cursor is between col 0 and
    firstNonBlank (but not at either), VSCode goes to firstNonBlank.
    Our editor currently goes to col 0.
    """
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 2))
        await pilot.press("home")
        # VSCode: from col 2 (within indent of LINE0, first non-WS at 5) → col 5
        assert ta.cursor_location == (0, 5), (
            f"Home from within indent should go to first non-WS; "
            f"got {ta.cursor_location}"
        )


async def test_smart_home_from_within_indent_line2(
    workspace: Path, cursor_test_file: Path
):
    """VSCode: Home from within indent on LINE2 should go to first non-WS."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (2, 2))
        await pilot.press("home")
        # LINE2 = "    Third Line", first non-WS at col 4
        assert ta.cursor_location == (2, 4), (
            f"Home from within indent should go to first non-WS; "
            f"got {ta.cursor_location}"
        )


async def test_sticky_column_down_and_up(workspace: Path, cursor_test_file: Path):
    """VSCode: column should be remembered when moving through shorter lines.

    Start at end of LINE0 (col 20), move down through shorter lines,
    then back up.  The original column should be restored on the longer line.
    """
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))
        await pilot.press("end")  # (0, 20)
        assert ta.cursor_location == (0, len(LINE0))

        await pilot.press("down")  # (1, 16) — clamped
        assert ta.cursor_location == (1, len(LINE1))

        await pilot.press("down")  # (2, 14) — clamped
        assert ta.cursor_location == (2, len(LINE2))

        # Now go back up — sticky column should restore
        await pilot.press("up")  # Back to LINE1 — should go to 16 (clamped from 20)
        assert ta.cursor_location == (1, len(LINE1))

        await pilot.press("up")  # Back to LINE0 — should restore to col 20
        assert ta.cursor_location == (0, len(LINE0)), (
            f"Sticky column should restore original column; got {ta.cursor_location}"
        )
