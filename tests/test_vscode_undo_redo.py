"""
Undo/redo tests ported from VSCode's cursor.test.ts.

These tests verify undo/redo behavior including undo stop boundaries for
whitespace, full undo/redo cycles with cursor position tracking,
multi-cursor undo, backspace undo chains, and unicode undo correctness.

Source: src/vs/editor/test/browser/controller/cursor.test.ts
VSCode uses 1-based positions; all values here are converted to 0-based.

Textual's EditHistory creates new undo batches when:
  - _force_end_batch (cursor movement, redo, etc.)
  - edit contains newline (in inserted or replaced text)
  - multi-character paste (>1 char inserted)
  - is_replacement flag changes (typing → backspace transition)
  - timer expired or max character count reached
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


# -- Backspace Across Lines: Undo/Redo Chain --------------------------------
# Adapted from VSCode Bug 9121: 'Auto indent + undo + redo is funky'.
# Original test uses Tab indentation (insertSpaces: false); we use spaces.


async def test_undo_redo_backspace_across_lines(workspace: Path):
    """VSCode: 'Bug 9121: Auto indent + undo + redo is funky'.

    Adapted: type text across two lines, then backspace across the line
    boundary.  Textual batches consecutive same-line backspaces together
    but creates a new batch when a backspace removes a newline character.

    Undo groups:
      batch 1: typing 'hi'
      batch 2: Enter (newline)
      batch 3: typing 'bye'
      (cursor movement creates checkpoint)
      batch 4: backspace 'e', 'y', 'b' (same-line, batched)
      batch 5: backspace '\\n' (newline removal = new batch)
    """
    f = workspace / "test.txt"
    f.write_text("")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))

        # Type 'hi' + Enter + 'bye'
        for ch in "hi":
            await pilot.press(ch)
        await pilot.press("enter")
        for ch in "bye":
            await pilot.press(ch)
        assert ta.text == "hi\nbye"
        assert ta.cursor_location == (1, 3)

        # Move cursor to create checkpoint, then back
        await pilot.press("left")
        await pilot.press("right")

        # Backspace 3 times to delete 'bye' (same-line, one batch)
        await pilot.press("backspace")
        await pilot.press("backspace")
        await pilot.press("backspace")
        assert ta.text == "hi\n"
        assert ta.cursor_location == (1, 0)

        # Backspace to delete newline (new batch — contains newline)
        await pilot.press("backspace")
        assert ta.text == "hi"
        assert ta.cursor_location == (0, 2)

        # Undo: restore newline (batch 5)
        await pilot.press("ctrl+z")
        assert ta.text == "hi\n"
        assert ta.cursor_location == (1, 0)

        # Undo: restore 'bye' (batch 4 — all 3 backspaces undone together)
        await pilot.press("ctrl+z")
        assert ta.text == "hi\nbye"
        assert ta.cursor_location == (1, 3)

        # Redo: delete 'bye' again (batch 4)
        await pilot.press("ctrl+shift+z")
        assert ta.text == "hi\n"

        # Redo: delete newline again (batch 5)
        await pilot.press("ctrl+shift+z")
        assert ta.text == "hi"


# -- Programmatic Delete + Undo Cursor Position ----------------------------
# Adapted from VSCode issue #42783.


async def test_undo_programmatic_delete_cursor(workspace: Path):
    """VSCode: 'issue #42783: API Calls with Undo Leave Cursor in Wrong Position'.

    Programmatic delete of text via API, then undo — cursor should be
    restored to its pre-undo position.
    """
    f = workspace / "ab.txt"
    f.write_text("ab")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))
        assert ta.text == "ab"

        # Programmatic delete: remove all text
        ta.delete((0, 0), (0, 2))
        assert ta.text == ""

        # Undo restores text
        await pilot.press("ctrl+z")
        assert ta.text == "ab"

        # Second programmatic delete: remove only 'a'
        ta.delete((0, 0), (0, 1))
        assert ta.text == "b"
        assert ta.cursor_location[1] == 0  # cursor stays at col 0


# -- Unicode Undo Correctness -----------------------------------------------
# Adapted from VSCode issue #47733.


async def test_undo_after_unicode_edit(workspace: Path):
    """VSCode: 'issue #47733: Undo mangles unicode characters'.

    Adapted: original test uses surroundingPairs to auto-wrap selected
    text with '%'.  We test that editing text containing emoji/unicode
    and then undoing restores the characters correctly without mangling.
    """
    f = workspace / "emoji.txt"
    f.write_text("'👁'")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))
        assert ta.text == "'👁'"

        # Select the first quote character
        ta.selection = Selection((0, 0), (0, 1))

        # Type replacement — replaces the quote with 'X'
        await pilot.press("X")
        assert ta.text == "X👁'"

        # Undo should restore the original quote without mangling emoji
        await pilot.press("ctrl+z")
        assert ta.text == "'👁'"


# -- Backspace Creates Boundary From Typing ---------------------------------


async def test_undo_backspace_boundary_from_typing(workspace: Path):
    """Verify that switching from typing to backspace creates an undo boundary.

    Textual's EditHistory tracks is_replacement: typing is a pure insertion
    (is_replacement=False), while backspace is a deletion (is_replacement=True).
    When the mode changes, a new batch is created.
    """
    f = workspace / "empty.txt"
    f.write_text("")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))

        # Type 'hello'
        for ch in "hello":
            await pilot.press(ch)
        assert ta.text == "hello"

        # Immediately backspace twice (no cursor movement in between)
        await pilot.press("backspace")
        await pilot.press("backspace")
        assert ta.text == "hel"

        # Undo: restores the two deleted characters (backspace batch)
        await pilot.press("ctrl+z")
        assert ta.text == "hello"
        assert ta.cursor_location == (0, 5)

        # Undo: removes 'hello' (typing batch)
        await pilot.press("ctrl+z")
        assert ta.text == ""


# -- Newline Backspace Creates Separate Batches -----------------------------


async def test_undo_newline_backspaces_separate_batches(workspace: Path):
    """Verify that backspacing over a newline is a separate undo group.

    When backspace deletes a '\\n', the edit's replaced_text contains a
    newline, triggering a new batch.  Additionally, checkpoint() is called
    after, so the next edit also starts a new batch.
    """
    f = workspace / "lines.txt"
    f.write_text("a\nb\nc")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (2, 1))
        assert ta.text == "a\nb\nc"

        # Backspace 'c' — is_replacement, starts new batch (force_end_batch
        # from initial cursor_location assignment)
        await pilot.press("backspace")
        assert ta.text == "a\nb\n"

        # Backspace newline — contains_newline → new batch
        await pilot.press("backspace")
        assert ta.text == "a\nb"
        assert ta.cursor_location == (1, 1)

        # Backspace 'b' — new batch (checkpoint after newline removal)
        await pilot.press("backspace")
        assert ta.text == "a\n"

        # Backspace newline — contains_newline → new batch
        await pilot.press("backspace")
        assert ta.text == "a"
        assert ta.cursor_location == (0, 1)

        # Undo chain: each step is a separate batch
        await pilot.press("ctrl+z")
        assert ta.text == "a\n"

        await pilot.press("ctrl+z")
        assert ta.text == "a\nb"

        await pilot.press("ctrl+z")
        assert ta.text == "a\nb\n"

        await pilot.press("ctrl+z")
        assert ta.text == "a\nb\nc"

        # Redo chain
        await pilot.press("ctrl+shift+z")
        assert ta.text == "a\nb\n"

        await pilot.press("ctrl+shift+z")
        assert ta.text == "a\nb"

        await pilot.press("ctrl+shift+z")
        assert ta.text == "a\n"

        await pilot.press("ctrl+shift+z")
        assert ta.text == "a"


# -- Delete Right (Forward Delete) + Undo -----------------------------------


async def test_undo_delete_right(workspace: Path):
    """Verify that forward delete (Delete key) can be undone.

    Forward delete removes the character to the right of the cursor.
    Like backspace, it is a replacement edit (is_replacement=True).
    """
    f = workspace / "test.txt"
    f.write_text("abcde")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 1))

        # Delete 'b' and 'c' (forward delete)
        await pilot.press("delete")
        await pilot.press("delete")
        assert ta.text == "ade"
        assert ta.cursor_location == (0, 1)

        # Undo restores both characters (batched together)
        await pilot.press("ctrl+z")
        assert ta.text == "abcde"
        assert ta.cursor_location == (0, 1)

        # Redo
        await pilot.press("ctrl+shift+z")
        assert ta.text == "ade"


# -- Paste Creates Isolated Undo Batch --------------------------------------


async def test_undo_paste_isolated_batch(workspace: Path):
    """Verify that pasting text creates an isolated undo batch.

    Textual's EditHistory creates a new batch when edit_characters > 1
    (multi-char insert = paste).  After such an edit, checkpoint() is
    also called, so the next edit starts yet another batch.
    """
    f = workspace / "test.txt"
    f.write_text("")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))

        # Type 'ab'
        for ch in "ab":
            await pilot.press(ch)
        assert ta.text == "ab"

        # Move to create checkpoint
        await pilot.press("left")
        await pilot.press("right")

        # Paste 'XYZ' via clipboard
        app.copy_to_clipboard("XYZ")
        await pilot.press("ctrl+v")
        await pilot.pause()
        assert ta.text == "abXYZ"

        # Move and type more
        await pilot.press("left")
        await pilot.press("right")
        await pilot.press("!")
        assert ta.text == "abXYZ!"

        # Undo: removes '!' (post-paste typing batch)
        await pilot.press("ctrl+z")
        assert ta.text == "abXYZ"

        # Undo: removes 'XYZ' (paste batch — isolated)
        await pilot.press("ctrl+z")
        assert ta.text == "ab"

        # Undo: removes 'ab' (initial typing batch)
        await pilot.press("ctrl+z")
        assert ta.text == ""


# -- Helpers (edge case tests) -----------------------------------------------


async def _paste(app, pilot, text: str) -> None:
    """Copy *text* to the system clipboard and paste it via Ctrl+V."""
    app.copy_to_clipboard(text)
    await pilot.press("ctrl+v")
    await pilot.pause()


# -- Emoji Undo Correctness (Edge Cases) ------------------------------------


async def test_undo_emoji_zwj_sequence_insert(workspace: Path):
    """Verify that undoing a ZWJ emoji removes all codepoints atomically.

    A ZWJ (Zero-Width Joiner) emoji like 👨‍👩‍👧‍👦 consists of multiple
    codepoints joined by U+200D.  When inserted via the API (which is
    the same path used by paste), a single undo should remove the entire
    sequence — not individual codepoints.
    """
    zwj_emoji = "\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466"  # 👨‍👩‍👧‍👦
    f = workspace / "emoji.txt"
    f.write_text("hello ")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 6))

        # Insert ZWJ emoji via API (same undo path as paste)
        ta.insert(zwj_emoji)
        assert zwj_emoji in ta.text
        cursor_after_insert = ta.cursor_location

        # Undo: entire emoji removed in one step
        await pilot.press("ctrl+z")
        assert ta.text == "hello "
        assert ta.cursor_location == (0, 6)

        # Redo: entire emoji restored
        await pilot.press("ctrl+shift+z")
        assert zwj_emoji in ta.text
        assert ta.cursor_location == cursor_after_insert


async def test_undo_mixed_emoji_and_ascii(workspace: Path):
    """Verify that emoji and ASCII text in separate undo batches round-trip correctly.

    Typing ASCII, pasting emoji, and typing more ASCII should create three
    independent undo groups that can be walked through in order.
    """
    f = workspace / "empty.txt"
    f.write_text("")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))

        # Group 1: type "abc"
        for ch in "abc":
            await pilot.press(ch)
        assert ta.text == "abc"

        # Create checkpoint via cursor movement
        await pilot.press("left")
        await pilot.press("right")

        # Group 2: paste emoji via clipboard (multi-char → isolated batch)
        await _paste(app, pilot, "\U0001f389")  # 🎉
        assert "\U0001f389" in ta.text

        # Create checkpoint via cursor movement
        await pilot.press("left")
        await pilot.press("right")

        # Group 3: type "xyz"
        for ch in "xyz":
            await pilot.press(ch)
        full_text = ta.text
        assert "abc" in full_text and "xyz" in full_text

        # Undo group 3: "xyz" removed
        await pilot.press("ctrl+z")
        assert "xyz" not in ta.text
        assert "\U0001f389" in ta.text

        # Undo group 2: emoji removed
        await pilot.press("ctrl+z")
        assert ta.text == "abc"
        assert ta.cursor_location == (0, 3)

        # Undo group 1: "abc" removed
        await pilot.press("ctrl+z")
        assert ta.text == ""

        # Redo chain: restore everything
        await pilot.press("ctrl+shift+z")
        assert ta.text == "abc"

        await pilot.press("ctrl+shift+z")
        assert "\U0001f389" in ta.text

        await pilot.press("ctrl+shift+z")
        assert ta.text == full_text


# -- Paste Undo Edge Cases ---------------------------------------------------


async def test_undo_multiline_paste_single_step(workspace: Path):
    """Verify that pasting multi-line text is undone in a single step.

    Multi-character inserts (including multi-line pastes) get an isolated
    batch in EditHistory.  A single undo should remove all pasted lines.
    """
    f = workspace / "start.txt"
    f.write_text("start")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 5))

        # Paste multi-line text
        await _paste(app, pilot, "\nline1\nline2\nline3")
        assert ta.text == "start\nline1\nline2\nline3"
        assert ta.cursor_location == (3, 5)

        # Single undo removes entire multi-line paste
        await pilot.press("ctrl+z")
        assert ta.text == "start"
        assert ta.cursor_location == (0, 5)

        # Redo restores all pasted lines
        await pilot.press("ctrl+shift+z")
        assert ta.text == "start\nline1\nline2\nline3"


async def test_undo_paste_over_selection_restores_original(workspace: Path):
    """Verify that pasting over a selection can be undone to restore the original.

    When text is selected and a paste replaces it, undo should restore both
    the original text and the original selection.
    """
    f = workspace / "hello.txt"
    f.write_text("hello world")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 6))

        # Select "world" (cols 6-11)
        ta.selection = Selection((0, 6), (0, 11))

        # Paste "universe" — replaces the selection
        await _paste(app, pilot, "universe")
        assert ta.text == "hello universe"

        # Undo: restores "hello world" and the original selection
        await pilot.press("ctrl+z")
        assert ta.text == "hello world"


async def test_undo_large_paste_exceeding_char_limit(workspace: Path):
    """Verify that a paste exceeding checkpoint_max_characters is a single undo batch.

    EditHistory creates new batches when the character count exceeds
    checkpoint_max_characters, but multi-character inserts (edit_characters > 1)
    always get an isolated batch regardless.  A large paste should still be
    undone in one step.
    """
    f = workspace / "empty.txt"
    f.write_text("")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))

        # Type "a" first, create checkpoint
        await pilot.press("a")
        await pilot.press("left")
        await pilot.press("right")

        # Paste text exceeding checkpoint_max_characters
        char_limit = ta.history.checkpoint_max_characters
        large_text = "X" * (char_limit + 50)
        await _paste(app, pilot, large_text)
        assert ta.text == "a" + large_text

        # Single undo removes the entire large paste
        await pilot.press("ctrl+z")
        assert ta.text == "a"
        assert ta.cursor_location == (0, 1)

        # Undo the "a"
        await pilot.press("ctrl+z")
        assert ta.text == ""


async def test_undo_paste_at_multi_cursor_primary_only(workspace: Path):
    """Document that paste only applies to the primary cursor.

    Behavioral documentation: when multiple cursors are active, Ctrl+V
    pastes text only at the primary cursor position.  Extra cursors are
    not involved in paste operations.  Undo reverts only the primary paste.
    """
    f = workspace / "multi.txt"
    f.write_text("aaa\nbbb")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 3))

        # Add a second cursor at end of line 2
        ta.add_cursor((1, 3), (1, 3))

        # Paste "ZZ" — only applies to primary cursor
        await _paste(app, pilot, "ZZ")

        # Verify paste happened at primary cursor only
        lines = ta.text.split("\n")
        assert "ZZ" in lines[0]

        # Undo: revert the paste
        await pilot.press("ctrl+z")
        assert ta.text == "aaa\nbbb"


# -- Undo History Limits (Integration) ----------------------------------------


async def test_undo_stack_max_capacity_drops_oldest(workspace: Path):
    """Verify that the undo stack respects max_checkpoints capacity.

    When the undo stack is full and new edits are made, the oldest entries
    should be dropped (deque with maxlen behavior).  After undoing all
    available entries, no further undo is possible.
    """
    f = workspace / "capacity.txt"
    f.write_text("")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))

        max_cp = ta.history.max_checkpoints

        # Fill the undo stack to exactly max_checkpoints using API inserts
        # (faster than key presses).  Each insert + checkpoint = 1 batch.
        for i in range(max_cp):
            ta.insert(str(i % 10))
            ta.history.checkpoint()
        assert len(ta.history.undo_stack) == max_cp

        # Add one more — oldest entry should be dropped
        ta.insert("!")
        ta.history.checkpoint()
        assert len(ta.history.undo_stack) == max_cp

        # Undo all available entries
        await pilot.press(*["ctrl+z"] * max_cp)

        # No further undo possible — text should not be empty since the
        # oldest batch was dropped
        text_after_all_undos = ta.text
        assert len(ta.history.undo_stack) == 0

        # Extra undo does nothing
        await pilot.press("ctrl+z")
        assert ta.text == text_after_all_undos


async def test_redo_stack_cleared_after_new_edit_following_undo(workspace: Path):
    """Verify that the redo stack is cleared when a new edit is made after undo.

    After undoing and then making a new edit, the redo stack should be
    emptied — you cannot redo the previously undone operations.
    """
    f = workspace / "redo_clear.txt"
    f.write_text("")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))

        # Type "abc" (group 1)
        for ch in "abc":
            await pilot.press(ch)
        # Create checkpoint via cursor movement
        await pilot.press("left")
        await pilot.press("right")

        # Type "def" (group 2)
        for ch in "def":
            await pilot.press(ch)
        assert ta.text == "abcdef"

        # Undo twice — removes "def" and "abc"
        await pilot.press("ctrl+z")
        assert ta.text == "abc"
        await pilot.press("ctrl+z")
        assert ta.text == ""

        assert len(ta.history.redo_stack) == 2

        # New edit: type "new"
        for ch in "new":
            await pilot.press(ch)
        assert ta.text == "new"

        # Redo stack should be cleared
        assert len(ta.history.redo_stack) == 0

        # Redo via keyboard does nothing
        await pilot.press("ctrl+shift+z")
        assert ta.text == "new"
        assert ta.cursor_location == (0, 3)


# -- Rapid Typing Undo -------------------------------------------------------


async def test_undo_rapid_typing_then_immediate_undo(workspace: Path):
    """Verify that rapid consecutive typing is undone in a single step.

    Textual does NOT create undo boundaries for space characters (unlike
    VSCode).  All consecutive character insertions — including spaces —
    are batched into a single undo group.  This test documents that behavior
    with a longer sequence than the existing whitespace tests.
    """
    f = workspace / "rapid.txt"
    f.write_text("")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        ta = await _get_ta(app, pilot, (0, 0))

        # Type 24 characters including spaces — no cursor movement
        typed_text = "the quick brown fox jumps"
        for ch in typed_text:
            await pilot.press(ch)
        assert ta.text == typed_text
        assert ta.cursor_location == (0, len(typed_text))

        # Single undo removes ALL typed characters (one batch)
        await pilot.press("ctrl+z")
        assert ta.text == ""
        assert ta.cursor_location == (0, 0)
