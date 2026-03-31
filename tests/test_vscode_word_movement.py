"""
Word movement tests ported from VSCode's wordOperations.test.ts.

Covers Ctrl+Left (cursorWordLeft) and Ctrl+Right (cursorWordRight),
adapted for our Textual-based editor's word boundary logic.

VSCode source:
  src/vs/editor/contrib/wordOperations/test/browser/wordOperations.test.ts

Position convention:
  VSCode uses 1-based (line, column).
  Textual uses 0-based (row, col).

Word boundary logic:
  Our editor uses ``_WORD_PATTERN = re.compile(r"(?<=\\W)(?=\\w)|(?<=\\w)(?=\\W)")``
  which matches every transition between word (\\w) and non-word (\\W) characters.

  VSCode groups consecutive separator characters (operators, punctuation) as a
  single word unit.  Our simpler pattern stops at every \\w↔\\W boundary, so
  operator sequences like ``+=`` produce two stops (before ``+`` and before ``=``).

Behavioral differences from VSCode (documented, not bugs):
  1. **Emoji at word boundary**: ``Line🐶`` — our editor treats the emoji as a
     separate \\W token, creating extra stops around it.  VSCode treats the
     entire ``Line🐶`` as one unit.
  2. **Operator grouping**: ``+=`` creates one stop in VSCode but two in ours
     (before ``+`` and before ``=``).  Same for ``*/``, ``-3``, etc.
"""

from pathlib import Path

from textual.widgets.text_area import Selection

from tests.conftest import make_app
from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

# ── Helpers ──────────────────────────────────────────────────────────────────


def _collect_stops_left(
    lines: list[str], start_row: int, start_col: int
) -> list[tuple[int, int]]:
    """Repeatedly apply ctrl+left from *start* until (0, 0) and collect stops."""
    pos = (start_row, start_col)
    stops: list[tuple[int, int]] = []
    for _ in range(200):  # safety limit
        pos = MultiCursorTextArea._move_location(lines, *pos, "ctrl+left")
        stops.append(pos)
        if pos == (0, 0):
            break
    return stops


def _collect_stops_right(
    lines: list[str], start_row: int, start_col: int
) -> list[tuple[int, int]]:
    """Repeatedly apply ctrl+right from *start* until end-of-document."""
    last_row = len(lines) - 1
    last_col = len(lines[last_row])
    pos = (start_row, start_col)
    stops: list[tuple[int, int]] = []
    for _ in range(200):  # safety limit
        pos = MultiCursorTextArea._move_location(lines, *pos, "ctrl+right")
        stops.append(pos)
        if pos == (last_row, last_col):
            break
    return stops


# ── Unit tests: Ctrl+Left (cursorWordLeft) ───────────────────────────────────


class TestCtrlLeftSimple:
    """Adapted from VSCode 'cursorWordLeft - simple'.

    Text:
        '    \\tMy First Line\\t '
        '\\tMy Second Line'
        '    Third Line🐶'
        ''
        '1'
    """

    LINES = [
        "    \tMy First Line\t ",
        "\tMy Second Line",
        "    Third Line\U0001f436",
        "",
        "1",
    ]

    def test_stops_on_last_line(self):
        """From end of '1', ctrl+left stops at start of '1'."""
        stops = _collect_stops_left(self.LINES, 4, 1)
        assert stops[0] == (4, 0)

    def test_crosses_empty_line(self):
        """From start of '1', goes to empty line, then to end of line 2."""
        stops = _collect_stops_left(self.LINES, 4, 1)
        assert (3, 0) in stops

    def test_word_stops_on_line_2(self):
        """Line 2 '    Third Line🐶': stops before 'Line', before 'Third'."""
        stops = _collect_stops_left(self.LINES, 4, 1)
        # Extract only stops on row 2 (excluding line-end transition)
        row2_stops = [col for row, col in stops if row == 2]
        assert 10 in row2_stops  # before 'Line'
        assert 4 in row2_stops  # before 'Third'
        assert 0 in row2_stops  # start of line

    def test_word_stops_on_line_1(self):
        """Line 1 '\\tMy Second Line': stops before 'Line', 'Second', 'My'."""
        stops = _collect_stops_left(self.LINES, 4, 1)
        row1_stops = [col for row, col in stops if row == 1]
        assert 11 in row1_stops  # before 'Line'
        assert 4 in row1_stops  # before 'Second'
        assert 1 in row1_stops  # before 'My'
        assert 0 in row1_stops  # start of line

    def test_word_stops_on_line_0(self):
        """Line 0 '    \\tMy First Line\\t ': stops before 'Line', 'First', 'My'."""
        stops = _collect_stops_left(self.LINES, 4, 1)
        row0_stops = [col for row, col in stops if row == 0]
        assert 14 in row0_stops  # before 'Line'
        assert 8 in row0_stops  # before 'First'
        assert 5 in row0_stops  # before 'My'
        assert 0 in row0_stops  # start of line

    def test_reaches_document_start(self):
        """Repeated ctrl+left from end eventually reaches (0, 0)."""
        stops = _collect_stops_left(self.LINES, 4, 1)
        assert stops[-1] == (0, 0)


class TestCtrlLeftDotSeparated:
    """Adapted from VSCode 'cursorWordLeft - issue #48046'.

    Text: 'deep.object.property'
    VSCode expected: |deep.|object.|property

    Our behavior matches: stops at every word↔dot boundary.
    """

    LINES = ["deep.object.property"]

    def test_stops_at_dot_boundaries(self):
        """Ctrl+left stops at: property→object.→deep.→start."""
        stops = _collect_stops_left(self.LINES, 0, 20)
        cols = [col for _, col in stops]
        assert 12 in cols  # before 'property'
        assert 5 in cols  # before 'object'
        assert 0 in cols  # start

    def test_stops_at_dot_positions(self):
        """Also stops at the dots themselves (word→non-word boundary)."""
        stops = _collect_stops_left(self.LINES, 0, 20)
        cols = [col for _, col in stops]
        assert 11 in cols  # after 'object', before '.'
        assert 4 in cols  # after 'deep', before '.'


class TestCtrlLeftOperators:
    """Adapted from VSCode 'cursorWordLeft - issue #832'.

    Text: '   /* Just some   more   text a+= 3 +5-3 + 7 */  '

    Our editor stops at every \\w↔\\W transition, while VSCode groups
    consecutive operators.  Core word stops (before words) match.
    """

    LINES = ["   /* Just some   more   text a+= 3 +5-3 + 7 */  "]

    def test_core_word_stops(self):
        """Stops before main words: Just, some, more, text, a."""
        stops = _collect_stops_left(self.LINES, 0, len(self.LINES[0]))
        cols = [col for _, col in stops]
        assert 6 in cols  # before 'Just'
        assert 11 in cols  # before 'some'
        assert 18 in cols  # before 'more'
        assert 25 in cols  # before 'text'
        assert 30 in cols  # before 'a'

    def test_digit_stops(self):
        """Stops before digits: 3, 5, 3, 7."""
        stops = _collect_stops_left(self.LINES, 0, len(self.LINES[0]))
        cols = [col for _, col in stops]
        assert 34 in cols  # before '3'
        assert 37 in cols  # before '5'
        assert 39 in cols  # before second '3'
        assert 43 in cols  # before '7'


class TestCtrlLeftWithSelection:
    """Adapted from VSCode 'cursorWordLeft - with selection'.

    Verifies that Ctrl+Shift+Left extends selection while moving by word.
    """

    async def test_shift_ctrl_left_extends_selection(self, workspace: Path):
        """From (4, 1) in '1', Shift+Ctrl+Left selects backward by word."""
        f = workspace / "test.txt"
        f.write_text(
            "    \tMy First Line\t \n\tMy Second Line\n    Third Line\U0001f436\n\n1\n",
            encoding="utf-8",
        )
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            ta.selection = Selection((4, 1), (4, 1))
            await pilot.pause()

            await pilot.press("ctrl+shift+left")

            # Should select from (4,1) back to (4,0)
            sel = ta.selection
            assert sel.start == (4, 1)
            assert sel.end == (4, 0)


class TestCtrlLeftMultiCursor:
    """Adapted from VSCode 'cursorWordLeft - issue #169904: cursors out of sync'.

    Multiple cursors should all move by word simultaneously.
    """

    LINES = [
        ".grid1 {",
        "  display: grid;",
        "  grid-template-columns:",
        "    [full-start] minmax(1em, 1fr)",
        "    [main-start] minmax(0, 40em) [main-end]",
        "    minmax(1em, 1fr) [full-end];",
        "}",
    ]

    async def test_multi_cursor_word_left(self, workspace: Path):
        """All cursors move left by word in sync."""
        f = workspace / "grid.css"
        f.write_text("\n".join(self.LINES) + "\n")
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            # Place primary at line 4 col 20, extra at line 5 col 20
            ta.selection = Selection((4, 20), (4, 20))
            ta.add_cursor((5, 20))
            await pilot.pause()

            await pilot.press("ctrl+left")
            await pilot.pause()

            # Both cursors should have moved left by one word
            primary = ta.cursor_location
            assert primary[0] == 4
            assert primary[1] < 20

            extras = ta.extra_cursors
            assert len(extras) == 1
            assert extras[0][0] == 5
            assert extras[0][1] < 20


# ── Unit tests: Ctrl+Right (cursorWordRight) ─────────────────────────────────


class TestCtrlRightSimple:
    """Adapted from VSCode 'cursorWordRight - simple'.

    Text:
        '    \\tMy First Line\\t '
        '\\tMy Second Line'
        '    Third Line🐶'
        ''
        '1'
    """

    LINES = [
        "    \tMy First Line\t ",
        "\tMy Second Line",
        "    Third Line\U0001f436",
        "",
        "1",
    ]

    def test_first_stop_after_first_word(self):
        """From (0,0), ctrl+right skips whitespace and stops after 'My'."""
        stops = _collect_stops_right(self.LINES, 0, 0)
        assert stops[0] == (0, 7)  # after 'My' (boundary between 'y' and ' ')

    def test_word_stops_on_line_0(self):
        """Line 0: stops after 'My', 'First', 'Line'."""
        stops = _collect_stops_right(self.LINES, 0, 0)
        row0_stops = [col for row, col in stops if row == 0]
        assert 7 in row0_stops  # after 'My'
        assert 13 in row0_stops  # after 'First'
        assert 18 in row0_stops  # after 'Line'

    def test_word_stops_on_line_1(self):
        """Line 1 '\\tMy Second Line': stops after 'My', 'Second', 'Line'."""
        stops = _collect_stops_right(self.LINES, 0, 0)
        row1_stops = [col for row, col in stops if row == 1]
        assert 3 in row1_stops  # after 'My'
        assert 10 in row1_stops  # after 'Second'
        assert 15 in row1_stops  # after 'Line' (end of line)

    def test_word_stops_on_line_2(self):
        """Line 2 '    Third Line🐶': stops after 'Third', with emoji boundary."""
        stops = _collect_stops_right(self.LINES, 0, 0)
        row2_stops = [col for row, col in stops if row == 2]
        assert 9 in row2_stops  # after 'Third'

    def test_traverses_empty_line(self):
        """Empty line 3 is crossed; cursor proceeds to line 4."""
        stops = _collect_stops_right(self.LINES, 0, 0)
        rows = [row for row, _ in stops]
        assert 3 in rows
        assert 4 in rows

    def test_reaches_document_end(self):
        """Repeated ctrl+right reaches end of document."""
        stops = _collect_stops_right(self.LINES, 0, 0)
        assert stops[-1] == (4, 1)


class TestCtrlRightConsoleDotLog:
    """Adapted from VSCode 'cursorWordRight - issue #41199'.

    Text: 'console.log(err)'
    VSCode expected: console|.log|(err|)|

    Our editor stops at every word↔non-word boundary.
    """

    LINES = ["console.log(err)"]

    def test_stops_at_dot_and_paren_boundaries(self):
        """Ctrl+right stops at word/symbol boundaries in method call."""
        stops = _collect_stops_right(self.LINES, 0, 0)
        cols = [col for _, col in stops]
        assert 7 in cols  # after 'console'
        assert 11 in cols  # after 'log'
        assert 15 in cols  # after 'err'


class TestCtrlRightWithSelection:
    """Adapted from VSCode 'cursorWordRight - selection'.

    Verifies that Ctrl+Shift+Right extends selection while moving by word.
    """

    async def test_shift_ctrl_right_extends_selection(self, workspace: Path):
        """From (0,0), Shift+Ctrl+Right selects the first word."""
        f = workspace / "test.txt"
        f.write_text("    \tMy First Line\t \n")
        app = make_app(workspace, open_file=f, light=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            ta.selection = Selection((0, 0), (0, 0))
            await pilot.pause()

            await pilot.press("ctrl+shift+right")

            # Should select from (0,0) forward to first word boundary
            sel = ta.selection
            assert sel.start == (0, 0)
            assert sel.end[1] > 0  # cursor moved right


class TestCtrlRightOperators:
    """Adapted from VSCode 'cursorWordRight - issue #832'.

    Text: '   /* Just some   more   text a+= 3 +5-3 + 7 */  '
    """

    LINES = ["   /* Just some   more   text a+= 3 +5-3 + 7 */  "]

    def test_core_word_stops(self):
        """Stops after main words: Just, some, more, text."""
        stops = _collect_stops_right(self.LINES, 0, 0)
        cols = [col for _, col in stops]
        assert 10 in cols  # after 'Just'
        assert 15 in cols  # after 'some'
        assert 22 in cols  # after 'more'
        assert 29 in cols  # after 'text'


# ── Edge cases ────────────────────────────────────────────────────────────────


class TestCtrlLeftEdgeCases:
    """Edge cases for ctrl+left word movement."""

    def test_at_document_start_stays(self):
        """Ctrl+left at (0,0) stays at (0,0)."""
        result = MultiCursorTextArea._move_location(["hello"], 0, 0, "ctrl+left")
        assert result == (0, 0)

    def test_empty_document(self):
        """Ctrl+left in empty document stays at (0,0)."""
        result = MultiCursorTextArea._move_location([""], 0, 0, "ctrl+left")
        assert result == (0, 0)

    def test_single_word(self):
        """Ctrl+left from end of single word goes to start."""
        result = MultiCursorTextArea._move_location(["hello"], 0, 5, "ctrl+left")
        assert result == (0, 0)

    def test_from_middle_of_word(self):
        """Ctrl+left from middle of 'hello' goes to start of 'hello'."""
        result = MultiCursorTextArea._move_location(["hello world"], 0, 3, "ctrl+left")
        assert result == (0, 0)

    def test_from_space_between_words(self):
        """Ctrl+left from the space after 'hello' goes to start of 'hello'."""
        result = MultiCursorTextArea._move_location(["hello world"], 0, 5, "ctrl+left")
        assert result == (0, 0)

    def test_leading_whitespace(self):
        """Ctrl+left from word start skips leading whitespace to col 0."""
        result = MultiCursorTextArea._move_location(["    hello"], 0, 4, "ctrl+left")
        assert result == (0, 0)

    def test_line_start_goes_to_prev_line_word_boundary(self):
        """Ctrl+left from col 0 goes to last word boundary on previous line."""
        lines = ["hello world", "test"]
        result = MultiCursorTextArea._move_location(lines, 1, 0, "ctrl+left")
        assert result == (0, 6)  # before 'world' (last word start)

    def test_line_start_single_word_prev_line(self):
        """Ctrl+left from col 0, previous line has one word → go to start."""
        lines = ["hello", "world"]
        result = MultiCursorTextArea._move_location(lines, 1, 0, "ctrl+left")
        assert result == (0, 0)

    def test_line_start_prev_line_empty(self):
        """Ctrl+left from col 0, previous line is empty → stop at (row-1, 0)."""
        lines = ["", "world"]
        result = MultiCursorTextArea._move_location(lines, 1, 0, "ctrl+left")
        assert result == (0, 0)

    def test_line_start_prev_line_trailing_whitespace(self):
        """Ctrl+left from col 0 skips trailing whitespace on previous line."""
        lines = ["hello world   ", "test"]
        result = MultiCursorTextArea._move_location(lines, 1, 0, "ctrl+left")
        assert result == (0, 6)  # before 'world', skip trailing spaces

    def test_trailing_whitespace_skipped(self):
        """Ctrl+left from end of 'hello   ' skips trailing spaces."""
        lines = ["hello   "]
        result = MultiCursorTextArea._move_location(lines, 0, 8, "ctrl+left")
        assert result == (0, 0)


class TestCtrlRightEdgeCases:
    """Edge cases for ctrl+right word movement."""

    def test_at_document_end_stays(self):
        """Ctrl+right at end of last line stays there."""
        result = MultiCursorTextArea._move_location(["hello"], 0, 5, "ctrl+right")
        assert result == (0, 5)

    def test_empty_document(self):
        """Ctrl+right in empty document stays at (0,0)."""
        result = MultiCursorTextArea._move_location([""], 0, 0, "ctrl+right")
        assert result == (0, 0)

    def test_single_word(self):
        """Ctrl+right from start of single word goes to end."""
        result = MultiCursorTextArea._move_location(["hello"], 0, 0, "ctrl+right")
        assert result == (0, 5)

    def test_from_middle_of_word(self):
        """Ctrl+right from middle of 'hello' goes to word boundary."""
        result = MultiCursorTextArea._move_location(["hello world"], 0, 3, "ctrl+right")
        assert result == (0, 5)

    def test_line_end_goes_to_next_line_word_boundary(self):
        """Ctrl+right from end of line goes to first word boundary on next line."""
        lines = ["hello", "foo bar"]
        result = MultiCursorTextArea._move_location(lines, 0, 5, "ctrl+right")
        assert result == (1, 3)  # after 'foo' (first word end)

    def test_line_end_next_line_single_word(self):
        """Ctrl+right from end of line, next line has one word → go to end."""
        lines = ["hello", "world"]
        result = MultiCursorTextArea._move_location(lines, 0, 5, "ctrl+right")
        assert result == (1, 5)  # end of 'world'

    def test_line_end_next_line_empty(self):
        """Ctrl+right from end of line, next line is empty → stop at start."""
        lines = ["hello", ""]
        result = MultiCursorTextArea._move_location(lines, 0, 5, "ctrl+right")
        assert result == (1, 0)

    def test_line_end_next_line_leading_whitespace(self):
        """Ctrl+right from end of line skips leading whitespace on next line."""
        lines = ["hello", "   world test"]
        result = MultiCursorTextArea._move_location(lines, 0, 5, "ctrl+right")
        assert result == (1, 8)  # after 'world' (skip "   ", end of word)

    def test_skips_leading_whitespace(self):
        """Ctrl+right from start of '   hello' skips whitespace to word end."""
        lines = ["   hello"]
        result = MultiCursorTextArea._move_location(lines, 0, 0, "ctrl+right")
        assert result == (0, 8)

    def test_underscore_is_word_char(self):
        """Underscore is treated as word character (\\w)."""
        lines = ["hello_world test"]
        result = MultiCursorTextArea._move_location(lines, 0, 0, "ctrl+right")
        assert result == (0, 11)  # 'hello_world' is one word


class TestCtrlLeftSelectIssue74369:
    """Adapted from VSCode 'cursorWordLeftSelect - issue #74369'.

    Text: 'this.is.a.test'

    Verifies consistent word-left behavior with dot-separated identifiers.
    Our editor stops at every word↔dot boundary.
    """

    LINES = ["this.is.a.test"]

    def test_all_stops(self):
        """Ctrl+left traverses all word/dot boundaries."""
        stops = _collect_stops_left(self.LINES, 0, 14)
        cols = [col for _, col in stops]
        # Should stop at boundaries: before 'test', '.', 'a', '.', 'is', '.', 'this'
        assert 10 in cols  # before 'test'
        assert 7 in cols  # before 'a'
        assert 5 in cols  # before 'is'
        assert 0 in cols  # before 'this'

    def test_dot_boundaries(self):
        """Stops at dot positions too (word→non-word transitions)."""
        stops = _collect_stops_left(self.LINES, 0, 14)
        cols = [col for _, col in stops]
        assert 9 in cols  # before '.' (after 'a')
        assert 4 in cols  # before '.' (after 'this')
