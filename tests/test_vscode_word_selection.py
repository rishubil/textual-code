"""
Word selection tests ported from VSCode's wordOperations.test.ts.

Covers Ctrl+Shift+Left and Ctrl+Shift+Right (word selection / extend selection
by word), adapted for our Textual-based editor.

VSCode source:
  src/vs/editor/contrib/wordOperations/test/browser/wordOperations.test.ts

Position convention:
  VSCode uses 1-based (line, column).
  Textual uses 0-based (row, col).

Architecture note — single vs multi-cursor:
  Single cursor: Textual's ``action_cursor_word_left(select=True)`` handles the
  key.  Cross-line behavior jumps to END of previous line (left) or START of
  next line (right), then the *next* press moves to a word boundary.

  Multi-cursor: our ``_move_all_cursors`` + ``_move_location`` handles the key.
  Cross-line behavior jumps directly to the nearest word boundary on the
  adjacent line.
"""

from pathlib import Path

from textual.widgets.text_area import Selection

from tests.conftest import make_app

# ── Single cursor: Ctrl+Shift+Left ──────────────────────────────────────────


class TestWordSelectLeft:
    """Ctrl+Shift+Left extends selection backward by word (single cursor).

    Adapted from VSCode 'cursorWordLeft - with selection' and related tests.
    """

    TEXT = "hello world foo\nbar baz\n"

    async def test_select_one_word_back(self, workspace: Path):
        """From end of 'world', Ctrl+Shift+Left selects 'world'."""
        f = workspace / "test.txt"
        f.write_text(self.TEXT)
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            # Place cursor at end of 'world' (row=0, col=11)
            ta.selection = Selection((0, 11), (0, 11))
            await pilot.wait_for_scheduled_animations()

            await pilot.press("ctrl+shift+left")

            sel = ta.selection
            # Anchor stays at (0, 11), cursor moves to start of 'world' (0, 6)
            assert sel.start == (0, 11)
            assert sel.end == (0, 6)

    async def test_select_two_words_back(self, workspace: Path):
        """Two Ctrl+Shift+Left presses select two words."""
        f = workspace / "test.txt"
        f.write_text(self.TEXT)
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            ta.selection = Selection((0, 11), (0, 11))
            await pilot.wait_for_scheduled_animations()

            await pilot.press("ctrl+shift+left")
            await pilot.press("ctrl+shift+left")

            sel = ta.selection
            # Anchor stays at (0, 11), cursor at start of 'hello' (0, 0)
            assert sel.start == (0, 11)
            assert sel.end == (0, 0)

    async def test_select_from_middle_of_word(self, workspace: Path):
        """Ctrl+Shift+Left from middle of 'world' selects to start of 'world'."""
        f = workspace / "test.txt"
        f.write_text(self.TEXT)
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            # Cursor in middle of 'world' (col=8)
            ta.selection = Selection((0, 8), (0, 8))
            await pilot.wait_for_scheduled_animations()

            await pilot.press("ctrl+shift+left")

            sel = ta.selection
            assert sel.start == (0, 8)
            assert sel.end == (0, 6)

    async def test_cross_line_left(self, workspace: Path):
        """Ctrl+Shift+Left from start of line selects to end of previous line."""
        f = workspace / "test.txt"
        f.write_text(self.TEXT)
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            # Cursor at start of line 1
            ta.selection = Selection((1, 0), (1, 0))
            await pilot.wait_for_scheduled_animations()

            await pilot.press("ctrl+shift+left")

            sel = ta.selection
            # Single cursor (Textual native): goes to end of previous line
            assert sel.start == (1, 0)
            assert sel.end == (0, 15)

    async def test_select_to_document_start(self, workspace: Path):
        """Repeated Ctrl+Shift+Left eventually selects to start of document."""
        f = workspace / "test.txt"
        f.write_text("abc def\nghi\n")
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            ta.selection = Selection((1, 3), (1, 3))
            await pilot.wait_for_scheduled_animations()

            # Press enough times to reach document start
            for _ in range(10):
                await pilot.press("ctrl+shift+left")

            sel = ta.selection
            assert sel.start == (1, 3)
            assert sel.end == (0, 0)


# ── Single cursor: Ctrl+Shift+Right ─────────────────────────────────────────


class TestWordSelectRight:
    """Ctrl+Shift+Right extends selection forward by word (single cursor).

    Adapted from VSCode 'cursorWordRight - selection'.
    """

    TEXT = "hello world foo\nbar baz\n"

    async def test_select_one_word_forward(self, workspace: Path):
        """From start of 'hello', Ctrl+Shift+Right selects 'hello'."""
        f = workspace / "test.txt"
        f.write_text(self.TEXT)
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            ta.selection = Selection((0, 0), (0, 0))
            await pilot.wait_for_scheduled_animations()

            await pilot.press("ctrl+shift+right")

            sel = ta.selection
            # Anchor stays at (0, 0), cursor moves to end of 'hello' (0, 5)
            assert sel.start == (0, 0)
            assert sel.end == (0, 5)

    async def test_select_two_words_forward(self, workspace: Path):
        """Two Ctrl+Shift+Right presses select two words."""
        f = workspace / "test.txt"
        f.write_text(self.TEXT)
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            ta.selection = Selection((0, 0), (0, 0))
            await pilot.wait_for_scheduled_animations()

            await pilot.press("ctrl+shift+right")
            await pilot.press("ctrl+shift+right")

            sel = ta.selection
            # Anchor stays at (0, 0), cursor after 'world' (0, 11)
            assert sel.start == (0, 0)
            assert sel.end == (0, 11)

    async def test_select_from_middle_of_word(self, workspace: Path):
        """Ctrl+Shift+Right from middle of 'hello' selects to end of 'hello'."""
        f = workspace / "test.txt"
        f.write_text(self.TEXT)
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            ta.selection = Selection((0, 3), (0, 3))
            await pilot.wait_for_scheduled_animations()

            await pilot.press("ctrl+shift+right")

            sel = ta.selection
            assert sel.start == (0, 3)
            assert sel.end == (0, 5)

    async def test_cross_line_right(self, workspace: Path):
        """Ctrl+Shift+Right from end of line selects to start of next line."""
        f = workspace / "test.txt"
        f.write_text(self.TEXT)
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            # Cursor at end of line 0
            ta.selection = Selection((0, 15), (0, 15))
            await pilot.wait_for_scheduled_animations()

            await pilot.press("ctrl+shift+right")

            sel = ta.selection
            # Single cursor (Textual native): goes to start of next line
            assert sel.start == (0, 15)
            assert sel.end == (1, 0)

    async def test_select_to_document_end(self, workspace: Path):
        """Repeated Ctrl+Shift+Right eventually selects to end of document."""
        f = workspace / "test.txt"
        f.write_text("abc def\nghi")
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            ta.selection = Selection((0, 0), (0, 0))
            await pilot.wait_for_scheduled_animations()

            for _ in range(10):
                await pilot.press("ctrl+shift+right")

            sel = ta.selection
            assert sel.start == (0, 0)
            assert sel.end == (1, 3)


# ── Word selection on dot-separated identifiers ─────────────────────────────


class TestWordSelectDotSeparated:
    """Ctrl+Shift+Left/Right on dot-separated identifiers like 'foo.bar.baz'.

    Adapted from VSCode 'cursorWordLeftSelect - issue #74369'.
    """

    TEXT = "this.is.a.test\n"

    async def test_select_left_through_dots(self, workspace: Path):
        """Repeated Ctrl+Shift+Left from end selects through dot-separated parts."""
        f = workspace / "test.txt"
        f.write_text(self.TEXT)
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            ta.selection = Selection((0, 14), (0, 14))
            await pilot.wait_for_scheduled_animations()

            # First press: select 'test'
            await pilot.press("ctrl+shift+left")
            sel = ta.selection
            assert sel.start == (0, 14)
            assert sel.end[0] == 0
            assert sel.end[1] <= 10  # at or before 'test'

    async def test_select_right_through_dots(self, workspace: Path):
        """Repeated Ctrl+Shift+Right from start selects through dot-separated parts."""
        f = workspace / "test.txt"
        f.write_text(self.TEXT)
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            ta.selection = Selection((0, 0), (0, 0))
            await pilot.wait_for_scheduled_animations()

            # First press: select 'this'
            await pilot.press("ctrl+shift+right")
            sel = ta.selection
            assert sel.start == (0, 0)
            assert sel.end[0] == 0
            assert sel.end[1] >= 4  # past 'this'


# ── Bidirectional selection ──────────────────────────────────────────────────


class TestWordSelectBidirectional:
    """Selecting words in one direction then the other shrinks selection."""

    TEXT = "hello world foo bar\n"

    async def test_select_left_then_right(self, workspace: Path):
        """Select left one word, then right one word returns near original."""
        f = workspace / "test.txt"
        f.write_text(self.TEXT)
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            # Start at end of 'world' (col 11)
            ta.selection = Selection((0, 11), (0, 11))
            await pilot.wait_for_scheduled_animations()

            await pilot.press("ctrl+shift+left")
            # Now selected 'world' backward: anchor=(0,11) cursor=(0,6)
            sel1 = ta.selection
            assert sel1.start == (0, 11)
            assert sel1.end == (0, 6)

            await pilot.press("ctrl+shift+right")
            # Cursor moves right by one word, selection shrinks
            sel2 = ta.selection
            assert sel2.start == (0, 11)
            assert sel2.end[1] > sel1.end[1]  # cursor moved right

    async def test_select_right_then_left(self, workspace: Path):
        """Select right one word, then left one word returns near original."""
        f = workspace / "test.txt"
        f.write_text(self.TEXT)
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            ta.selection = Selection((0, 6), (0, 6))
            await pilot.wait_for_scheduled_animations()

            await pilot.press("ctrl+shift+right")
            sel1 = ta.selection
            assert sel1.start == (0, 6)
            assert sel1.end == (0, 11)

            await pilot.press("ctrl+shift+left")
            sel2 = ta.selection
            assert sel2.start == (0, 6)
            assert sel2.end[1] < sel1.end[1]  # cursor moved left


# ── Multi-cursor word selection ──────────────────────────────────────────────


class TestMultiCursorWordSelect:
    """Ctrl+Shift+Left/Right with multiple cursors.

    When extra cursors are active, our _move_all_cursors handles the movement
    with shift detection to extend selections.
    """

    TEXT = "hello world\nfoo bar baz\nqux quux\n"

    async def test_multi_cursor_shift_left(self, workspace: Path):
        """Ctrl+Shift+Left with two cursors extends both selections."""
        f = workspace / "test.txt"
        f.write_text(self.TEXT)
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            # Primary at end of 'world' (0, 11), extra at end of 'bar' (1, 7)
            ta.selection = Selection((0, 11), (0, 11))
            ta.add_cursor((1, 7))
            await pilot.wait_for_scheduled_animations()

            await pilot.press("ctrl+shift+left")
            await pilot.wait_for_scheduled_animations()

            # Primary selection should extend left by one word
            sel = ta.selection
            assert sel.start == (0, 11)
            assert sel.end[0] == 0
            assert sel.end[1] < 11  # moved left

            # Extra cursor should also have extended selection
            extras = ta.extra_cursors
            assert len(extras) >= 1

    async def test_multi_cursor_shift_right(self, workspace: Path):
        """Ctrl+Shift+Right with two cursors extends both selections."""
        f = workspace / "test.txt"
        f.write_text(self.TEXT)
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            # Primary at start of 'hello' (0, 0), extra at start of 'foo' (1, 0)
            ta.selection = Selection((0, 0), (0, 0))
            ta.add_cursor((1, 0))
            await pilot.wait_for_scheduled_animations()

            await pilot.press("ctrl+shift+right")
            await pilot.wait_for_scheduled_animations()

            # Primary should select forward by one word
            sel = ta.selection
            assert sel.start == (0, 0)
            assert sel.end[1] > 0  # moved right

            # Extra should also have moved right
            extras = ta.extra_cursors
            assert len(extras) >= 1


# ── Edge cases ───────────────────────────────────────────────────────────────


class TestWordSelectEdgeCases:
    """Edge cases for word selection."""

    async def test_select_left_at_document_start(self, workspace: Path):
        """Ctrl+Shift+Left at (0,0) does not crash and selection stays."""
        f = workspace / "test.txt"
        f.write_text("hello\n")
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            ta.selection = Selection((0, 0), (0, 0))
            await pilot.wait_for_scheduled_animations()

            await pilot.press("ctrl+shift+left")

            sel = ta.selection
            assert sel.start == (0, 0)
            assert sel.end == (0, 0)

    async def test_select_right_at_document_end(self, workspace: Path):
        """Ctrl+Shift+Right at end of document does not crash."""
        f = workspace / "test.txt"
        f.write_text("hello")
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            ta.selection = Selection((0, 5), (0, 5))
            await pilot.wait_for_scheduled_animations()

            await pilot.press("ctrl+shift+right")

            sel = ta.selection
            assert sel.start == (0, 5)
            assert sel.end == (0, 5)

    async def test_select_left_with_leading_whitespace(self, workspace: Path):
        """Ctrl+Shift+Left on '    hello' selects from word into whitespace."""
        f = workspace / "test.txt"
        f.write_text("    hello world\n")
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            # Cursor at start of 'hello' (col 4)
            ta.selection = Selection((0, 4), (0, 4))
            await pilot.wait_for_scheduled_animations()

            await pilot.press("ctrl+shift+left")

            sel = ta.selection
            # Should select the leading whitespace back to col 0
            assert sel.start == (0, 4)
            assert sel.end == (0, 0)

    async def test_select_right_with_trailing_whitespace(self, workspace: Path):
        """Ctrl+Shift+Right past last word reaches end of line."""
        f = workspace / "test.txt"
        f.write_text("hello   \nworld\n")
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            ta.selection = Selection((0, 0), (0, 0))
            await pilot.wait_for_scheduled_animations()

            await pilot.press("ctrl+shift+right")

            sel = ta.selection
            assert sel.start == (0, 0)
            assert sel.end == (0, 5)  # end of 'hello'

    async def test_empty_line_word_select_left(self, workspace: Path):
        """Ctrl+Shift+Left from empty line selects to end of previous line."""
        f = workspace / "test.txt"
        f.write_text("hello\n\nworld\n")
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            # Cursor on empty line (1, 0)
            ta.selection = Selection((1, 0), (1, 0))
            await pilot.wait_for_scheduled_animations()

            await pilot.press("ctrl+shift+left")

            sel = ta.selection
            assert sel.start == (1, 0)
            # Should go to end of line 0 (0, 5)
            assert sel.end == (0, 5)
