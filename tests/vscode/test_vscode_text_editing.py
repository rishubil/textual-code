"""
Basic text editing tests ported from VSCode's cursor.test.ts.

These tests verify fundamental editing operations (type, backspace, delete,
enter) and undo stop boundaries using the same scenarios as VSCode's editor
test suite, adapted for Textual's TextArea widget.

Source: src/vs/editor/test/browser/controller/cursor.test.ts
VSCode uses 1-based positions; all values here are converted to 0-based.
"""

from pathlib import Path

import pytest
from textual.widgets.text_area import Selection

from tests.conftest import make_app

# ── Test text ────────────────────────────────────────────────────────────────
# Simple two-line text matching VSCode's basic editing tests.

EDIT_TEXT = "123456789\n123456789"


@pytest.fixture
def edit_test_file(workspace: Path) -> Path:
    f = workspace / "edit_test.txt"
    f.write_text(EDIT_TEXT)
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


# ── Simple Type ──────────────────────────────────────────────────────────────
# VSCode: cursor.test.ts "simple type"


async def test_simple_type(workspace: Path, edit_test_file: Path):
    """Type a character at cursor position (insert mode)."""
    app = make_app(workspace, light=True, open_file=edit_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 2))
        await pilot.press("a")
        assert ta.text == "12a3456789\n123456789"
        assert ta.cursor_location == (0, 3)


async def test_simple_type_at_end(workspace: Path, edit_test_file: Path):
    """VSCode: 'simple type' second assertion — type at end of line."""
    app = make_app(workspace, light=True, open_file=edit_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 9))
        # Type multiple characters one at a time (Pilot API sends one key at a time)
        await pilot.press("b", "b", "b")
        assert ta.text == "123456789bbb\n123456789"
        assert ta.cursor_location == (0, 12)


# ── Type Replaces Selection ──────────────────────────────────────────────────
# VSCode: cursor.test.ts "multi-line selection type"


async def test_type_replaces_single_line_selection(
    workspace: Path, edit_test_file: Path
):
    """Type with a single-line selection replaces the selected text."""
    app = make_app(workspace, light=True, open_file=edit_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        # Select "345" on line 0 (cols 2-5)
        ta.selection = Selection((0, 2), (0, 5))
        await pilot.press("x")
        assert ta.text == "12x6789\n123456789"
        assert ta.cursor_location == (0, 3)


async def test_type_replaces_multi_line_selection(
    workspace: Path, edit_test_file: Path
):
    """Type over multi-line selection replaces selected text (insert mode).

    Adapted from VSCode 'multi-line selection type' (Overtype Mode suite).
    In insert mode, the second character inserts rather than overtypes.
    """
    app = make_app(workspace, light=True, open_file=edit_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        # VSCode: Selection(1, 5, 2, 3) → 0-based: (0, 4) to (1, 2)
        ta.selection = Selection((0, 4), (1, 2))
        await pilot.press("c", "c")
        assert ta.text == "1234cc3456789"
        assert ta.cursor_location == (0, 6)


# ── Backspace ────────────────────────────────────────────────────────────────


async def test_backspace_basic(workspace: Path, edit_test_file: Path):
    """Backspace deletes the character before the cursor."""
    app = make_app(workspace, light=True, open_file=edit_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 5))
        await pilot.press("backspace")
        assert ta.text == "12346789\n123456789"
        assert ta.cursor_location == (0, 4)


async def test_backspace_at_document_start(workspace: Path, edit_test_file: Path):
    """Backspace at document start (0, 0) does nothing."""
    app = make_app(workspace, light=True, open_file=edit_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))
        await pilot.press("backspace")
        assert ta.text == EDIT_TEXT
        assert ta.cursor_location == (0, 0)


async def test_backspace_at_line_start_joins_lines(
    workspace: Path, edit_test_file: Path
):
    """Backspace at the start of a line joins it with the previous line."""
    app = make_app(workspace, light=True, open_file=edit_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (1, 0))
        await pilot.press("backspace")
        assert ta.text == "123456789123456789"
        assert ta.cursor_location == (0, 9)


async def test_backspace_with_selection_deletes_selection(
    workspace: Path, edit_test_file: Path
):
    """Backspace with active selection deletes the selection, not a character."""
    app = make_app(workspace, light=True, open_file=edit_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        ta.selection = Selection((0, 2), (0, 5))
        await pilot.press("backspace")
        assert ta.text == "126789\n123456789"
        assert ta.cursor_location == (0, 2)


async def test_backspace_with_multi_line_selection(
    workspace: Path, edit_test_file: Path
):
    """VSCode issue #1140: Backspace with multi-line selection deletes selection.

    Adapted from VSCode: 'issue #1140: Backspace stops prematurely'.
    Original used function/return code; simplified to our test text.
    """
    app = make_app(workspace, light=True, open_file=edit_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        # Select from (0, 4) to (1, 3) — backward selection
        ta.selection = Selection((1, 3), (0, 4))
        await pilot.press("backspace")
        assert ta.text == "1234456789"
        assert ta.cursor_location == (0, 4)


# ── Delete ───────────────────────────────────────────────────────────────────


async def test_delete_basic(workspace: Path, edit_test_file: Path):
    """Delete key removes the character at the cursor."""
    app = make_app(workspace, light=True, open_file=edit_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 4))
        await pilot.press("delete")
        assert ta.text == "12346789\n123456789"
        assert ta.cursor_location == (0, 4)


async def test_delete_at_line_end_joins_lines(workspace: Path, edit_test_file: Path):
    """Delete at end of line joins with the next line."""
    app = make_app(workspace, light=True, open_file=edit_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 9))
        await pilot.press("delete")
        assert ta.text == "123456789123456789"
        assert ta.cursor_location == (0, 9)


async def test_delete_at_document_end(workspace: Path, edit_test_file: Path):
    """Delete at the very end of the document does nothing."""
    app = make_app(workspace, light=True, open_file=edit_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (1, 9))
        await pilot.press("delete")
        assert ta.text == EDIT_TEXT
        assert ta.cursor_location == (1, 9)


async def test_delete_with_selection(workspace: Path, edit_test_file: Path):
    """Delete with selection removes the selected text."""
    app = make_app(workspace, light=True, open_file=edit_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        ta.selection = Selection((0, 2), (0, 7))
        await pilot.press("delete")
        assert ta.text == "1289\n123456789"
        assert ta.cursor_location == (0, 2)


# ── Enter ────────────────────────────────────────────────────────────────────


async def test_enter_splits_line(workspace: Path, edit_test_file: Path):
    """Enter in the middle of a line splits it into two."""
    app = make_app(workspace, light=True, open_file=edit_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 5))
        await pilot.press("enter")
        assert ta.text == "12345\n6789\n123456789"
        assert ta.cursor_location == (1, 0)


async def test_enter_at_line_start(workspace: Path, edit_test_file: Path):
    """Enter at the start of a line inserts an empty line before it."""
    app = make_app(workspace, light=True, open_file=edit_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))
        await pilot.press("enter")
        assert ta.text == "\n123456789\n123456789"
        assert ta.cursor_location == (1, 0)


async def test_enter_at_line_end(workspace: Path, edit_test_file: Path):
    """Enter at the end of a line inserts an empty line after it."""
    app = make_app(workspace, light=True, open_file=edit_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 9))
        await pilot.press("enter")
        assert ta.text == "123456789\n\n123456789"
        assert ta.cursor_location == (1, 0)


async def test_enter_with_selection_replaces_with_newline(
    workspace: Path, edit_test_file: Path
):
    """Enter with selection replaces the selected text with a newline."""
    app = make_app(workspace, light=True, open_file=edit_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        ta.selection = Selection((0, 3), (0, 7))
        await pilot.press("enter")
        assert ta.text == "123\n89\n123456789"
        assert ta.cursor_location == (1, 0)


async def test_enter_with_multi_line_selection(workspace: Path, edit_test_file: Path):
    """Enter with multi-line selection replaces all selected text with a newline."""
    app = make_app(workspace, light=True, open_file=edit_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot)
        ta.selection = Selection((0, 5), (1, 3))
        await pilot.press("enter")
        assert ta.text == "12345\n456789"
        assert ta.cursor_location == (1, 0)


# ── Undo Stops ───────────────────────────────────────────────────────────────
# VSCode: cursor.test.ts "Undo stops" suite
#
# VSCode creates an undo boundary (stop) when switching between different edit
# operation types (typing ↔ delete-left ↔ delete-right).  This means pressing
# Ctrl+Z undoes the most recent *group* of the same operation type, rather than
# each individual keystroke.

UNDO_TEXT = "A  line\nAnother line"


@pytest.fixture
def undo_test_file(workspace: Path) -> Path:
    f = workspace / "undo_test.txt"
    f.write_text(UNDO_TEXT)
    return f


async def test_undo_stop_between_typing_and_delete_left(
    workspace: Path, undo_test_file: Path
):
    """VSCode: 'there is an undo stop between typing and deleting left'.

    Type 'first' → delete-left × 2 → undo restores typed text → undo restores
    original.
    """
    app = make_app(workspace, light=True, open_file=undo_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 2))  # VSCode: (1, 3)
        # Type 'first'
        await pilot.press("f", "i", "r", "s", "t")
        assert ta.text.split("\n")[0] == "A first line"
        assert ta.cursor_location == (0, 7)

        # Delete left × 2
        await pilot.press("backspace", "backspace")
        assert ta.text.split("\n")[0] == "A fir line"
        assert ta.cursor_location == (0, 5)

        # Undo — should restore "A first line" (undo the delete-left group)
        await pilot.press("ctrl+z")
        assert ta.text.split("\n")[0] == "A first line"
        assert ta.cursor_location == (0, 7)

        # Undo — should restore "A  line" (undo the typing group)
        await pilot.press("ctrl+z")
        assert ta.text.split("\n")[0] == "A  line"
        assert ta.cursor_location == (0, 2)


async def test_undo_stop_between_typing_and_delete_right(
    workspace: Path, undo_test_file: Path
):
    """VSCode: 'there is an undo stop between typing and deleting right'.

    Type 'first' → delete-right × 2 → undo restores after-type text → undo
    restores original.
    """
    app = make_app(workspace, light=True, open_file=undo_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 2))
        await pilot.press("f", "i", "r", "s", "t")
        assert ta.text.split("\n")[0] == "A first line"
        assert ta.cursor_location == (0, 7)

        await pilot.press("delete", "delete")
        assert ta.text.split("\n")[0] == "A firstine"
        assert ta.cursor_location == (0, 7)

        await pilot.press("ctrl+z")
        assert ta.text.split("\n")[0] == "A first line"
        assert ta.cursor_location == (0, 7)

        await pilot.press("ctrl+z")
        assert ta.text.split("\n")[0] == "A  line"
        assert ta.cursor_location == (0, 2)


async def test_undo_stop_between_delete_left_and_typing(
    workspace: Path, undo_test_file: Path
):
    """VSCode: 'there is an undo stop between deleting left and typing'.

    Delete-left × 7 on line 2 → type 'Second' → undo typing → undo deletes.
    """
    app = make_app(workspace, light=True, open_file=undo_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (1, 7))  # VSCode: (2, 8)
        # Delete left × 7 to remove "Another"
        for _ in range(7):
            await pilot.press("backspace")
        assert ta.text.split("\n")[1] == " line"
        assert ta.cursor_location == (1, 0)

        await pilot.press("S", "e", "c", "o", "n", "d")
        assert ta.text.split("\n")[1] == "Second line"
        assert ta.cursor_location == (1, 6)

        await pilot.press("ctrl+z")
        assert ta.text.split("\n")[1] == " line"
        assert ta.cursor_location == (1, 0)

        await pilot.press("ctrl+z")
        assert ta.text.split("\n")[1] == "Another line"
        assert ta.cursor_location == (1, 7)


async def test_undo_stop_between_delete_right_and_typing(
    workspace: Path, undo_test_file: Path
):
    """VSCode: 'there is an undo stop between deleting right and typing'.

    Delete-right × 4 on line 2 → type 'text' → undo typing → undo deletes.
    """
    app = make_app(workspace, light=True, open_file=undo_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (1, 8))  # VSCode: (2, 9)
        for _ in range(4):
            await pilot.press("delete")
        assert ta.text.split("\n")[1] == "Another "
        assert ta.cursor_location == (1, 8)

        await pilot.press("t", "e", "x", "t")
        assert ta.text.split("\n")[1] == "Another text"
        assert ta.cursor_location == (1, 12)

        await pilot.press("ctrl+z")
        assert ta.text.split("\n")[1] == "Another "
        assert ta.cursor_location == (1, 8)

        await pilot.press("ctrl+z")
        assert ta.text.split("\n")[1] == "Another line"
        assert ta.cursor_location == (1, 8)


async def test_undo_stop_between_delete_left_and_delete_right(
    workspace: Path, undo_test_file: Path
):
    """VSCode: 'there is an undo stop between deleting left and deleting right'.

    Delete-left × 7 on line 2 → delete-right × 5 → undo → undo.

    Behavioral difference from VSCode:
    VSCode creates an undo boundary when switching from delete-left to
    delete-right, so undo restores each group separately.  Textual's TextArea
    does NOT distinguish between delete-left and delete-right for undo
    batching — both are treated as the same edit type.  As a result, a single
    undo restores all 12 deletes at once.
    """
    app = make_app(workspace, light=True, open_file=undo_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (1, 7))
        for _ in range(7):
            await pilot.press("backspace")
        assert ta.text.split("\n")[1] == " line"
        assert ta.cursor_location == (1, 0)

        for _ in range(5):
            await pilot.press("delete")
        assert ta.text.split("\n")[1] == ""
        assert ta.cursor_location == (1, 0)

        # Textual undoes all deletes (both directions) in one step
        await pilot.press("ctrl+z")
        assert ta.text.split("\n")[1] == "Another line"
        assert ta.cursor_location == (1, 7)


async def test_undo_stop_between_delete_right_and_delete_left(
    workspace: Path, undo_test_file: Path
):
    """VSCode: 'there is an undo stop between deleting right and deleting left'.

    Delete-right × 4 on line 2 → delete-left × 6 → undo.

    Behavioral difference from VSCode:
    Same as test_undo_stop_between_delete_left_and_delete_right — Textual
    does not create an undo boundary between delete-left and delete-right.
    A single undo restores all 10 deletes at once.
    """
    app = make_app(workspace, light=True, open_file=undo_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (1, 8))  # VSCode: (2, 9)
        for _ in range(4):
            await pilot.press("delete")
        assert ta.text.split("\n")[1] == "Another "
        assert ta.cursor_location == (1, 8)

        for _ in range(6):
            await pilot.press("backspace")
        assert ta.text.split("\n")[1] == "An"
        assert ta.cursor_location == (1, 2)

        # Textual undoes all deletes (both directions) in one step
        await pilot.press("ctrl+z")
        assert ta.text.split("\n")[1] == "Another line"
        assert ta.cursor_location == (1, 8)
