"""
Selection tests ported from VSCode's cursor.test.ts.

These tests verify selection behavior when using Home/End with existing
selections (collapse behavior), extending selections via shift+movement,
buffer-level selection (ctrl+shift+home/end), and combined move-then-select
patterns.

Source: src/vs/editor/test/browser/controller/cursor.test.ts
VSCode uses 1-based positions; all values here are converted to 0-based.

Test text adapted from VSCode (tabs replaced with spaces, emoji removed):
    LINE0 = "     My First Line  "   (20 chars, first non-WS at col 5)
    LINE1 = "  My Second Line"       (16 chars, first non-WS at col 2)
    LINE2 = "    Third Line"         (14 chars, first non-WS at col 4)
    LINE3 = ""                       (0 chars)
    LINE4 = "1"                      (1 char)
"""

from pathlib import Path

import pytest
from textual.widgets.text_area import Selection

from tests.conftest import make_app

# ── Test text ────────────────────────────────────────────────────────────────
# Same text as test_vscode_cursor_movement.py.

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


async def _get_ta(app, pilot, start=(0, 0)):
    """After entering run_test, pause and return the TextArea positioned at *start*."""
    await pilot.wait_for_scheduled_animations()
    ce = app.main_view.get_active_code_editor()
    assert ce is not None, "No active code editor found"
    ta = ce.editor
    ta.selection = Selection.cursor(start)
    return ta


# ── Home collapses selection ─────────────────────────────────────────────────
# VSCode: "move to beginning of line with selection (multiline|single line)
#          (forward|backward)"
#
# Pressing Home WITHOUT Shift while a selection is active collapses the
# selection and moves the cursor to the smart-home position of the cursor's
# line (first non-whitespace or column 0, using VSCode-style toggle).


@pytest.mark.parametrize(
    "selection, expected",
    [
        # Multiline forward: anchor before cursor
        # VSCode: anchor(1,8)→cursor(3,9), Home → (3,5) collapsed
        pytest.param(
            Selection((0, 7), (2, 8)),
            (2, 4),
            id="multiline-forward",
        ),
        # Multiline backward: anchor after cursor
        # VSCode: anchor(3,9)→cursor(1,8), Home → (1,6) collapsed
        pytest.param(
            Selection((2, 8), (0, 7)),
            (0, 5),
            id="multiline-backward",
        ),
        # Single-line forward: anchor before cursor on same line
        # VSCode: anchor(3,2)→cursor(3,9), Home → (3,5) collapsed
        pytest.param(
            Selection((2, 1), (2, 8)),
            (2, 4),
            id="single-line-forward",
        ),
        # Single-line backward: anchor after cursor on same line
        # VSCode: anchor(3,9)→cursor(3,2), Home → (3,5) collapsed
        pytest.param(
            Selection((2, 8), (2, 1)),
            (2, 4),
            id="single-line-backward",
        ),
    ],
)
async def test_home_collapses_selection(
    workspace: Path, cursor_test_file: Path, selection, expected
):
    """Home (no Shift) collapses an active selection to the smart-home position
    of the cursor's line."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        ta.selection = selection
        await pilot.press("home")
        assert ta.selection == Selection.cursor(expected), (
            f"Expected collapsed at {expected}, got {ta.selection}"
        )


# ── End collapses selection ──────────────────────────────────────────────────
# VSCode: "move to end of line with selection (multiline|single line)
#          (forward|backward)"
#
# Pressing End WITHOUT Shift while a selection is active collapses the
# selection and moves the cursor to the end of the cursor's line.


@pytest.mark.parametrize(
    "selection, expected",
    [
        # Multiline forward: anchor before cursor
        # VSCode: anchor(1,1)→cursor(3,9), End → (3,17) collapsed
        pytest.param(
            Selection((0, 0), (2, 8)),
            (2, len(LINE2)),
            id="multiline-forward",
        ),
        # Multiline backward: anchor after cursor
        # VSCode: anchor(3,9)→cursor(1,1), End → (1,21) collapsed
        pytest.param(
            Selection((2, 8), (0, 0)),
            (0, len(LINE0)),
            id="multiline-backward",
        ),
        # Single-line forward
        # VSCode: anchor(3,1)→cursor(3,9), End → (3,17) collapsed
        pytest.param(
            Selection((2, 0), (2, 8)),
            (2, len(LINE2)),
            id="single-line-forward",
        ),
        # Single-line backward
        # VSCode: anchor(3,9)→cursor(3,1), End → (3,17) collapsed
        pytest.param(
            Selection((2, 8), (2, 0)),
            (2, len(LINE2)),
            id="single-line-backward",
        ),
    ],
)
async def test_end_collapses_selection(
    workspace: Path, cursor_test_file: Path, selection, expected
):
    """End (no Shift) collapses an active selection to the end of the
    cursor's line."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        ta.selection = selection
        await pilot.press("end")
        assert ta.selection == Selection.cursor(expected), (
            f"Expected collapsed at {expected}, got {ta.selection}"
        )


# ── Shift+Home extends selection (smart toggle) ─────────────────────────────
# VSCode: "move to beginning of line from within line selection"
#
# Shift+Home from within a line extends the selection with smart-home toggle:
# first press → first non-whitespace, second press → column 0.


async def test_shift_home_smart_toggle_selection(
    workspace: Path, cursor_test_file: Path
):
    """VSCode: shift+home toggles between first non-WS and col 0 while
    extending selection.

    Start at (0,7), first shift+home → Selection((0,7), (0,5)),
    second shift+home → Selection((0,7), (0,0)).
    """
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 7))
        # First press: extend to first non-WS (col 5)
        await pilot.press("shift+home")
        assert ta.selection == Selection((0, 7), (0, 5)), (
            f"First shift+home should go to first non-WS; got {ta.selection}"
        )
        # Second press: extend to col 0
        await pilot.press("shift+home")
        assert ta.selection == Selection((0, 7), (0, 0)), (
            f"Second shift+home should go to col 0; got {ta.selection}"
        )


# ── Shift+Home extends multiline selection ───────────────────────────────────
# VSCode issue #17011: "Shift+home/end now go to the end of the selection
# start's line, not the selection's end"
#
# When a multiline selection is active, Shift+Home should extend the
# selection to the smart-home position of the CURSOR's line, not the
# anchor's line.


async def test_shift_home_extends_multiline_selection(
    workspace: Path, cursor_test_file: Path
):
    """VSCode #17011: shift+home from multiline selection extends to cursor
    line's smart-home.

    Selection from (0,7) to (2,8), shift+home → Selection((0,7), (2,4)).
    """
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        ta.selection = Selection((0, 7), (2, 8))
        await pilot.press("shift+home")
        assert ta.selection == Selection((0, 7), (2, 4)), (
            f"Shift+home should extend to cursor line's first non-WS; "
            f"got {ta.selection}"
        )


# ── Shift+End idempotent ────────────────────────────────────────────────────
# VSCode: "move to end of line from within line selection"
#
# Pressing Shift+End twice from the same position should produce the same
# selection both times (idempotent once at line end).


async def test_shift_end_idempotent(workspace: Path, cursor_test_file: Path):
    """VSCode: shift+end from within line is idempotent on second press."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 5))
        await pilot.press("shift+end")
        expected = Selection((0, 5), (0, len(LINE0)))
        assert ta.selection == expected, f"First shift+end; got {ta.selection}"
        await pilot.press("shift+end")
        assert ta.selection == expected, (
            f"Second shift+end should be idempotent; got {ta.selection}"
        )


# ── Ctrl+Shift+Home from various positions ──────────────────────────────────
# VSCode: "move to beginning of buffer from within (first line|another line)
#          selection"


@pytest.mark.parametrize(
    "start, expected_selection",
    [
        # From first line — short selection to doc start
        # VSCode: start(1,3), ctrl+shift+home → Selection(1,3, 1,1)
        pytest.param(
            (0, 2),
            Selection((0, 2), (0, 0)),
            id="from-first-line",
        ),
        # From another line — long selection to doc start
        # VSCode: start(3,3), ctrl+shift+home → Selection(3,3, 1,1)
        pytest.param(
            (2, 2),
            Selection((2, 2), (0, 0)),
            id="from-another-line",
        ),
    ],
)
async def test_ctrl_shift_home_selection(
    workspace: Path, cursor_test_file: Path, start, expected_selection
):
    """ctrl+shift+home selects from cursor to document start."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, start)
        await pilot.press("ctrl+shift+home")
        assert ta.selection == expected_selection, (
            f"Expected {expected_selection}, got {ta.selection}"
        )


# ── Ctrl+Shift+End from various positions ───────────────────────────────────
# VSCode: "move to end of buffer from within (last line|another line)
#          selection"


@pytest.mark.parametrize(
    "start, expected_selection",
    [
        # From last line — short selection to doc end
        # VSCode: start(5,1), ctrl+shift+end → Selection(5,1, 5,2)
        pytest.param(
            (4, 0),
            Selection((4, 0), (4, len(LINE4))),
            id="from-last-line",
        ),
        # From another line — long selection to doc end
        # VSCode: start(3,3), ctrl+shift+end → Selection(3,3, 5,2)
        pytest.param(
            (2, 2),
            Selection((2, 2), (4, len(LINE4))),
            id="from-another-line",
        ),
    ],
)
async def test_ctrl_shift_end_selection(
    workspace: Path, cursor_test_file: Path, start, expected_selection
):
    """ctrl+shift+end selects from cursor to document end."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, start)
        await pilot.press("ctrl+shift+end")
        assert ta.selection == expected_selection, (
            f"Expected {expected_selection}, got {ta.selection}"
        )


# ── Shift+Down at last line ─────────────────────────────────────────────────
# VSCode: "move down with selection" continues past the last line boundary
# to the end of the last line.


async def test_shift_down_reaches_end_of_last_line(
    workspace: Path, cursor_test_file: Path
):
    """VSCode: shift+down from last line extends selection to end of line.

    Starting from (0,0), pressing shift+down 5 times should reach (4,1)
    on the 5th press (end of last line "1").
    """
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))
        # First 4 presses: to lines 1-4 col 0
        for i in range(1, 5):
            await pilot.press("shift+down")
            assert ta.selection == Selection((0, 0), (i, 0)), (
                f"Press {i}: expected end=({i}, 0), got {ta.selection}"
            )
        # 5th press: cursor moves to end of last line
        await pilot.press("shift+down")
        assert ta.selection == Selection((0, 0), (4, len(LINE4))), (
            f"5th press should reach end of last line; got {ta.selection}"
        )


# ── Shift+Up at first line ──────────────────────────────────────────────────
# Symmetric to shift+down at last line: shift+up from first line extends
# selection to start of document.


async def test_shift_up_reaches_start_of_first_line(
    workspace: Path, cursor_test_file: Path
):
    """shift+up from first line extends selection to start of document."""
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 5))
        await pilot.press("shift+up")
        assert ta.selection == Selection((0, 5), (0, 0)), (
            f"Shift+up at first line should select to (0,0); got {ta.selection}"
        )


# ── Move and then select ────────────────────────────────────────────────────
# VSCode: "move and then select"
#
# Navigate to a position, then use shift+movement to create a selection
# anchored at the navigated position.


async def test_move_and_then_select(workspace: Path, cursor_test_file: Path):
    """VSCode: navigate to a position, then shift+movement extends selection
    from that position.

    Move to (1,2), then shift+end should select from (1,2) to end of line 1.
    Then shift+up should extend selection upward.
    """
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (1, 2))

        # Shift+End: select from (1,2) to end of LINE1
        await pilot.press("shift+end")
        assert ta.selection == Selection((1, 2), (1, len(LINE1))), (
            f"Shift+end from (1,2); got {ta.selection}"
        )

        # Shift+Up: extend selection upward — anchor stays at (1,2),
        # cursor moves to same column on line 0
        await pilot.press("shift+up")
        assert ta.selection == Selection((1, 2), (0, len(LINE1))), (
            f"Shift+up after shift+end; got {ta.selection}"
        )


async def test_move_and_then_select_bidirectional(
    workspace: Path, cursor_test_file: Path
):
    """VSCode: 'move and then select' — shift+movement in both directions.

    Start at (1,2). Shift+right extends forward, then shift+left reverses.
    Selection anchor stays at (1,2) throughout.
    """
    app = make_app(workspace, light=True, open_file=cursor_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (1, 2))

        # Shift+Right 3 times: select 3 chars forward
        for _ in range(3):
            await pilot.press("shift+right")
        assert ta.selection == Selection((1, 2), (1, 5)), (
            f"3x shift+right from (1,2); got {ta.selection}"
        )

        # Shift+Left 5 times: reverse past anchor, select 2 chars backward
        for _ in range(5):
            await pilot.press("shift+left")
        assert ta.selection == Selection((1, 2), (1, 0)), (
            f"5x shift+left reverses selection; got {ta.selection}"
        )
