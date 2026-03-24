"""
Undo/redo tests ported from VSCode's cursor.test.ts.

These tests verify undo/redo behavior including undo stop boundaries for
whitespace, full undo/redo cycles with cursor position tracking, and
multi-cursor undo.

Source: src/vs/editor/test/browser/controller/cursor.test.ts
VSCode uses 1-based positions; all values here are converted to 0-based.
"""

from pathlib import Path

import pytest
from textual.widgets.text_area import Selection

from tests.conftest import make_app

# -- Test text ----------------------------------------------------------------

UNDO_TEXT = "A  line\nAnother line"


@pytest.fixture
def undo_test_file(workspace: Path) -> Path:
    f = workspace / "undo_test.txt"
    f.write_text(UNDO_TEXT)
    return f


# -- Helpers ------------------------------------------------------------------


async def _get_ta(app, pilot, start=(0, 0)):
    """After entering run_test, pause and return the TextArea positioned at *start*."""
    await pilot.pause()
    ce = app.main_view.get_active_code_editor()
    assert ce is not None, "No active code editor found"
    ta = ce.editor
    ta.selection = Selection.cursor(start)
    return ta


# -- Undo Stops: Whitespace --------------------------------------------------
# VSCode creates undo boundaries when space characters are typed.
# Textual does NOT — all consecutive character insertions are batched into
# a single undo group regardless of whitespace.  These tests document the
# behavioral difference.


async def test_undo_stop_on_space_typing(workspace: Path, undo_test_file: Path):
    """VSCode: 'inserts undo stop when typing space'.

    VSCode: type 'first and interesting' → undo → 'first and line' →
    undo → 'first line' → undo → original.

    Behavioral difference from VSCode:
    Textual does NOT create undo boundaries for space characters.
    All consecutive typing is one undo group, undone in a single step.
    """
    app = make_app(workspace, light=True, open_file=undo_test_file)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 2))  # VSCode: (1, 3)
        for ch in "first and interesting":
            await pilot.press(ch)
        assert ta.text.split("\n")[0] == "A first and interesting line"
        assert ta.cursor_location == (0, 23)

        # Textual: single undo restores original (no space-based undo stops)
        await pilot.press("ctrl+z")
        assert ta.text.split("\n")[0] == "A  line"
        assert ta.cursor_location == (0, 2)


async def test_single_undo_stop_for_consecutive_whitespaces(workspace: Path):
    """VSCode: 'there is a single undo stop for consecutive whitespaces'.

    VSCode: type 'ab  cd' → undo → 'ab  ' → undo → 'ab' → undo → ''.

    Behavioral difference from VSCode:
    Textual batches all consecutive character insertions (including spaces)
    into a single undo group.  A single undo restores the empty state.
    """
    f = workspace / "empty.txt"
    f.write_text("")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))
        for ch in "ab  cd":
            await pilot.press(ch)
        assert ta.text == "ab  cd"

        # Textual: all typing undone in one step
        await pilot.press("ctrl+z")
        assert ta.text == ""


async def test_no_undo_stop_after_single_whitespace(workspace: Path):
    """VSCode: 'there is no undo stop after a single whitespace'.

    VSCode: type 'ab cd' → undo → 'ab' → undo → ''.

    Behavioral difference from VSCode:
    Same as Textual's native behavior — all consecutive typing is one group.
    A single undo restores all typing at once.
    """
    f = workspace / "empty.txt"
    f.write_text("")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))
        for ch in "ab cd":
            await pilot.press(ch)
        assert ta.text == "ab cd"

        # Textual: all typing undone in one step
        await pilot.press("ctrl+z")
        assert ta.text == ""


# -- Undo/Redo Full Cycle ---------------------------------------------------


async def test_undo_redo_full_cycle_with_cursor(workspace: Path):
    """VSCode: 'issue #46208: Allow empty selections in the undo/redo stack'.

    Adapted: type words separated by cursor movement (to create undo
    boundaries), then walk through the full undo/redo chain verifying
    both text content and cursor position at every step.

    In VSCode, spaces create undo boundaries.  In Textual, we use explicit
    cursor movement (arrow keys call move_cursor → history.checkpoint) to
    create equivalent boundaries between word groups.
    """
    f = workspace / "empty.txt"
    f.write_text("")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))

        # Type 'Hello'
        for ch in "Hello":
            await pilot.press(ch)
        assert ta.text == "Hello"
        assert ta.cursor_location == (0, 5)

        # Move cursor to create an undo boundary
        await pilot.press("left")
        await pilot.press("right")

        # Type ' world'
        for ch in " world":
            await pilot.press(ch)
        assert ta.text == "Hello world"
        assert ta.cursor_location == (0, 11)

        # Move cursor to create another undo boundary
        await pilot.press("left")
        await pilot.press("right")

        # Type '!' (third undo group)
        await pilot.press("!")
        assert ta.text == "Hello world!"
        assert ta.cursor_location == (0, 12)

        # Undo chain: walk back through all groups
        await pilot.press("ctrl+z")
        assert ta.text == "Hello world"
        assert ta.cursor_location == (0, 11)

        await pilot.press("ctrl+z")
        assert ta.text == "Hello"
        assert ta.cursor_location == (0, 5)

        await pilot.press("ctrl+z")
        assert ta.text == ""
        assert ta.cursor_location == (0, 0)

        # Redo chain: walk forward through all groups
        await pilot.press("ctrl+shift+z")
        assert ta.text == "Hello"
        assert ta.cursor_location == (0, 5)

        await pilot.press("ctrl+shift+z")
        assert ta.text == "Hello world"
        assert ta.cursor_location == (0, 11)

        await pilot.press("ctrl+shift+z")
        assert ta.text == "Hello world!"
        assert ta.cursor_location == (0, 12)

        # Extra redo does nothing
        await pilot.press("ctrl+shift+z")
        assert ta.text == "Hello world!"
        assert ta.cursor_location == (0, 12)


async def test_undo_redo_cursor_position(workspace: Path):
    """VSCode: 'issue #15761: Cursor doesn't move in a redo operation'.

    After a programmatic edit with cursor adjustment, undo should restore
    the old cursor position and redo should re-apply the new position.
    """
    f = workspace / "hello.txt"
    f.write_text("hello")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 3))  # VSCode: (1, 4)

        # Programmatic insert at start of line — cursor should shift right
        ta.insert("*", (0, 0))
        assert ta.text == "*hello"
        # After insert at (0,0), cursor stays at (0,3) since the API
        # insert doesn't auto-move the user's cursor
        cursor_after_insert = ta.cursor_location

        # Undo
        await pilot.press("ctrl+z")
        assert ta.text == "hello"

        # Redo
        await pilot.press("ctrl+shift+z")
        assert ta.text == "*hello"
        assert ta.cursor_location == cursor_after_insert


# -- Enter Creates Undo Boundary ---------------------------------------------


async def test_enter_creates_undo_boundary(workspace: Path):
    """Verify that pressing Enter creates an undo boundary.

    Textual creates a new undo batch when an edit contains a newline.
    This means typing before and after Enter are separate undo groups.
    """
    f = workspace / "empty.txt"
    f.write_text("")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))

        # Type 'hello' then Enter then 'world'
        for ch in "hello":
            await pilot.press(ch)
        await pilot.press("enter")
        for ch in "world":
            await pilot.press(ch)
        assert ta.text == "hello\nworld"
        assert ta.cursor_location == (1, 5)

        # Undo 'world' (second group, after Enter boundary)
        await pilot.press("ctrl+z")
        assert ta.text == "hello\n"
        assert ta.cursor_location == (1, 0)

        # Undo Enter
        await pilot.press("ctrl+z")
        assert ta.text == "hello"
        assert ta.cursor_location == (0, 5)

        # Undo 'hello'
        await pilot.press("ctrl+z")
        assert ta.text == ""
        assert ta.cursor_location == (0, 0)


# -- Multi-Cursor Undo -------------------------------------------------------


async def test_undo_multi_cursor_edit(workspace: Path):
    """VSCode: 'issue #93585: Undo multi cursor edit corrupts document'.

    Type with multiple cursors, then undo.  The document should be fully
    restored to its original state.

    Textual creates an undo boundary between the first keystroke (which
    replaces the selection) and the second keystroke (a pure insertion),
    because is_replacement changes from True to False.  Two undos are
    needed to fully restore the document.
    """
    f = workspace / "hello_world.txt"
    f.write_text("hello world\nhello world")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 6))  # VSCode: (1, 7)

        # Select 'world' on line 0: (0,6) to (0,11)
        ta.selection = Selection((0, 6), (0, 11))
        # Add cursor on line 1 selecting 'world': (1,6) to (1,11)
        ta.add_cursor((1, 6), (1, 11))

        # Type 'no' — replaces both selections
        await pilot.press("n", "o")
        assert ta.text == "hello no\nhello no"

        # Undo 'o' insertion (second batch — pure insertion)
        await pilot.press("ctrl+z")
        assert ta.text == "hello n\nhello n"

        # Undo 'n' replacement (first batch — replaced selection)
        await pilot.press("ctrl+z")
        assert ta.text == "hello world\nhello world"


# -- Read-Only Undo Blocked ---------------------------------------------------


async def test_undo_blocked_in_read_only_mode(workspace: Path):
    """VSCode: 'issue #44805: Should not be able to undo in readonly editor'.

    Undo and redo should be blocked when the editor is in read-only mode,
    matching VSCode behavior.
    """
    f = workspace / "readonly.txt"
    f.write_text("")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))

        # Make a programmatic edit, then set read-only
        ta.insert("Hello world!")
        assert ta.text == "Hello world!"

        ta.read_only = True

        # Undo should be blocked in read-only mode
        await pilot.press("ctrl+z")
        assert ta.text == "Hello world!"

        # Redo should also be blocked
        await pilot.press("ctrl+shift+z")
        assert ta.text == "Hello world!"


# -- Undo After Selection Delete + Type --------------------------------------


async def test_undo_after_selection_replace(workspace: Path):
    """Verify undo correctly handles selection replacement followed by typing.

    Type text → select part → type replacement → undo chain.

    Textual creates an undo boundary between the first keystroke (replaces
    the selection, is_replacement=True) and subsequent keystrokes (pure
    insertion, is_replacement=False).  Three undos are needed to fully
    restore the original text.
    """
    f = workspace / "test.txt"
    f.write_text("abcdef")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))

        # Select 'bcd' (cols 1-4)
        ta.selection = Selection((0, 1), (0, 4))

        # Type 'XY' — first press replaces selection, second is pure insert
        await pilot.press("X", "Y")
        assert ta.text == "aXYef"
        assert ta.cursor_location == (0, 3)

        # Move cursor to create boundary
        await pilot.press("end")

        # Type more
        await pilot.press("!")
        assert ta.text == "aXYef!"
        assert ta.cursor_location == (0, 6)

        # Undo the '!' (third batch)
        await pilot.press("ctrl+z")
        assert ta.text == "aXYef"

        # Undo the 'Y' insertion (second batch — pure insertion)
        await pilot.press("ctrl+z")
        assert ta.text == "aXef"

        # Undo the 'X' replacement (first batch — replaced selection)
        await pilot.press("ctrl+z")
        assert ta.text == "abcdef"
