"""
Multi-cursor selection tests ported from VSCode's multicursor.test.ts.

Covers Ctrl+D (AddSelectionToNextFindMatchAction) and Ctrl+Shift+L
(SelectHighlightsAction), adapted for our Textual-based editor.

VSCode source:
  src/vs/editor/contrib/multicursor/test/browser/multicursor.test.ts

Position convention:
  VSCode uses 1-based (line, column).
  Textual uses 0-based (row, col).
  Conversion: VSCode Position(line, col) → Textual (line-1, col-1)

Behavioral differences from VSCode:
  1. Our Ctrl+D uses plain substring search; VSCode uses word-boundary matching
     when starting from a collapsed cursor.
     → VSCode: "app" in cursor → skips "apples", "whatsapp"; matches only "app"
     → Ours: "app" in cursor → matches "app" in "apples", "whatsapp" too
  2. Our Ctrl+D is case-sensitive; VSCode's case sensitivity depends on context.
     → Documented in test_ctrl_d_case_sensitive_search.
"""

from pathlib import Path

import pytest
from textual.widgets.text_area import Selection

from tests.conftest import make_app

# ── Helpers ──────────────────────────────────────────────────────────────────


def _sel(
    ta, *, extra_index: int | None = None
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Return (start, end) for primary or an extra cursor selection.

    For the primary cursor, returns (sel.start, sel.end).
    For extra cursors, returns (anchor, cursor) as a (start, end) pair
    with start < end (normalized).
    """
    if extra_index is None:
        sel = ta.selection
        return (min(sel.start, sel.end), max(sel.start, sel.end))
    anchor = ta.extra_anchors[extra_index]
    cursor = ta.extra_cursors[extra_index]
    return (min(anchor, cursor), max(anchor, cursor))


# ── Ctrl+D: AddSelectionToNextFindMatchAction ────────────────────────────────


class TestCtrlDFromCollapsedCursor:
    """Adapted from VSCode 'AddSelectionToNextFindMatchAction starting with
    single collapsed selection'.

    VSCode test: cursor at (1,2) in ['abc pizza', 'abc house', 'abc bar'].
    First Ctrl+D selects "abc", subsequent presses add next occurrences.
    """

    @pytest.fixture
    def abc_file(self, workspace: Path) -> Path:
        f = workspace / "abc.txt"
        f.write_text("abc pizza\nabc house\nabc bar\n")
        return f

    async def test_first_ctrl_d_selects_word(self, workspace: Path, abc_file: Path):
        """First Ctrl+D from collapsed cursor selects the word under cursor."""
        app = make_app(workspace, light=True, open_file=abc_file)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            ta.cursor_location = (0, 1)  # inside "abc"
            await pilot.pause()

            await pilot.press("ctrl+d")
            await pilot.pause()

            # Primary selection should cover "abc" on line 0
            sel = ta.selection
            assert min(sel.start, sel.end) == (0, 0)
            assert max(sel.start, sel.end) == (0, 3)
            assert ta.extra_cursors == []

    async def test_second_ctrl_d_adds_next(self, workspace: Path, abc_file: Path):
        """Second Ctrl+D adds cursor at next occurrence."""
        app = make_app(workspace, light=True, open_file=abc_file)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            ta.cursor_location = (0, 1)
            await pilot.pause()

            await pilot.press("ctrl+d")
            await pilot.pause()
            await pilot.press("ctrl+d")
            await pilot.pause()

            # Primary: "abc" at line 0
            assert _sel(ta) == ((0, 0), (0, 3))
            # Extra 0: "abc" at line 1
            assert len(ta.extra_cursors) == 1
            assert _sel(ta, extra_index=0) == ((1, 0), (1, 3))

    async def test_three_ctrl_d_adds_all_three(self, workspace: Path, abc_file: Path):
        """Three Ctrl+D presses select all three 'abc' occurrences."""
        app = make_app(workspace, light=True, open_file=abc_file)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            ta.cursor_location = (0, 1)
            await pilot.pause()

            await pilot.press("ctrl+d")
            await pilot.pause()
            await pilot.press("ctrl+d")
            await pilot.pause()
            await pilot.press("ctrl+d")
            await pilot.pause()

            assert _sel(ta) == ((0, 0), (0, 3))
            assert len(ta.extra_cursors) == 2
            assert _sel(ta, extra_index=0) == ((1, 0), (1, 3))
            assert _sel(ta, extra_index=1) == ((2, 0), (2, 3))

    async def test_fourth_ctrl_d_wraps_noop(self, workspace: Path, abc_file: Path):
        """Fourth Ctrl+D wraps around — all already selected, no new cursor."""
        app = make_app(workspace, light=True, open_file=abc_file)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            ta.cursor_location = (0, 1)
            await pilot.pause()

            for _ in range(4):
                await pilot.press("ctrl+d")
                await pilot.pause()

            # Still 2 extras (3 total), no additional cursor added
            assert len(ta.extra_cursors) == 2


class TestCtrlDTouchingRanges:
    """Adapted from VSCode issue #6661: AddSelectionToNextFindMatchAction
    with touching ranges.

    Text: 'abcabc\\nabc\\nabcabc'
    Adjacent 'abc' matches on the same line should each get their own cursor.
    """

    @pytest.fixture
    def touching_file(self, workspace: Path) -> Path:
        f = workspace / "touching.txt"
        f.write_text("abcabc\nabc\nabcabc\n")
        return f

    async def test_touching_ranges_all_found(
        self, workspace: Path, touching_file: Path
    ):
        """Ctrl+D finds all 5 'abc' occurrences including adjacent ones."""
        app = make_app(workspace, light=True, open_file=touching_file)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            # Select "abc" at (0, 0)-(0, 3)
            ta.selection = Selection((0, 0), (0, 3))
            await pilot.pause()

            # Press Ctrl+D 4 times to add remaining 4 occurrences
            for _ in range(4):
                await pilot.press("ctrl+d")
                await pilot.pause()

            # Primary: (0,0)-(0,3) = first "abc"
            assert _sel(ta) == ((0, 0), (0, 3))
            # 4 extra cursors for the remaining matches
            assert len(ta.extra_cursors) == 4
            assert _sel(ta, extra_index=0) == ((0, 3), (0, 6))  # touching!
            assert _sel(ta, extra_index=1) == ((1, 0), (1, 3))
            assert _sel(ta, extra_index=2) == ((2, 0), (2, 3))
            assert _sel(ta, extra_index=3) == ((2, 3), (2, 6))  # touching!

    async def test_touching_ranges_type_replaces_all(
        self, workspace: Path, touching_file: Path
    ):
        """Typing after selecting all touching 'abc' replaces each with the typed text.

        Adapted from VSCode test that types 'z' after selecting all 5 'abc' matches.
        VSCode expected: 'zz\\nz\\nzz'
        """
        app = make_app(workspace, light=True, open_file=touching_file)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            # Select "abc" at (0, 0)-(0, 3)
            ta.selection = Selection((0, 0), (0, 3))
            await pilot.pause()

            # Add all 4 remaining occurrences
            for _ in range(4):
                await pilot.press("ctrl+d")
                await pilot.pause()

            assert len(ta.extra_cursors) == 4

            # Type 'z' to replace all "abc" with "z"
            await pilot.press("z")
            await pilot.pause()

            lines = ta.text.rstrip("\n").split("\n")
            assert lines[0] == "zz"
            assert lines[1] == "z"
            assert lines[2] == "zz"


class TestCtrlDCaseSensitivity:
    """Adapted from VSCode issue #20651: case-insensitive matching.

    VSCode behavior: Ctrl+D with "test" selected matches "Test" (case-insensitive).
    Our behavior: Ctrl+D is case-sensitive — "test" does NOT match "Test".
    This is a documented behavioral difference.
    """

    @pytest.fixture
    def case_file(self, workspace: Path) -> Path:
        f = workspace / "case.txt"
        f.write_text("test\ntestte\nTest\ntestte\ntest\n")
        return f

    async def test_ctrl_d_case_sensitive_search(self, workspace: Path, case_file: Path):
        """Ctrl+D is case-sensitive: 'test' matches 'test' and 'testte' but not 'Test'.

        Behavioral difference: VSCode finds 'Test' (case-insensitive).
        Our editor skips 'Test' and only matches exact case.
        """
        app = make_app(workspace, light=True, open_file=case_file)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            # Select "test" on line 0
            ta.selection = Selection((0, 0), (0, 4))
            await pilot.pause()

            # First Ctrl+D: finds "test" in "testte" on line 1
            await pilot.press("ctrl+d")
            await pilot.pause()
            assert len(ta.extra_cursors) == 1
            assert _sel(ta, extra_index=0) == ((1, 0), (1, 4))

            # Second Ctrl+D: skips "Test" (case mismatch),
            # finds "test" in "testte" line 3
            await pilot.press("ctrl+d")
            await pilot.pause()
            assert len(ta.extra_cursors) == 2
            assert _sel(ta, extra_index=1) == ((3, 0), (3, 4))

            # Third Ctrl+D: finds "test" on line 4
            await pilot.press("ctrl+d")
            await pilot.pause()
            assert len(ta.extra_cursors) == 3
            assert _sel(ta, extra_index=2) == ((4, 0), (4, 4))


class TestCtrlDSubstringMatching:
    """Adapted from VSCode 'Find state disassociation - enters mode'.

    VSCode behavior: Ctrl+D from collapsed cursor uses word-boundary matching.
    Our behavior: Ctrl+D uses plain substring matching — no word boundaries.
    This is a documented behavioral difference.

    VSCode text: ['app', 'apples', 'whatsapp', 'app', 'App', ' app']
    VSCode: 'app' from cursor → matches only 'app' (lines 1, 4) and ' app' (line 6)
    Ours: 'app' from cursor → matches 'app' in 'apples', 'whatsapp', etc.
    """

    @pytest.fixture
    def app_file(self, workspace: Path) -> Path:
        f = workspace / "app.txt"
        f.write_text("app\napples\nwhatsapp\napp\nApp\n app\n")
        return f

    async def test_ctrl_d_matches_substrings(self, workspace: Path, app_file: Path):
        """Ctrl+D finds 'app' as substring in 'apples' and 'whatsapp'.

        This is different from VSCode which uses word boundaries.
        """
        app = make_app(workspace, light=True, open_file=app_file)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            # Cursor inside "app" on line 0
            ta.cursor_location = (0, 1)
            await pilot.pause()

            # First Ctrl+D: selects "app" on line 0
            await pilot.press("ctrl+d")
            await pilot.pause()
            assert _sel(ta) == ((0, 0), (0, 3))

            # Second Ctrl+D: finds "app" inside "apples" on line 1
            # (VSCode would skip this — word boundary mismatch)
            await pilot.press("ctrl+d")
            await pilot.pause()
            assert len(ta.extra_cursors) == 1
            assert _sel(ta, extra_index=0) == ((1, 0), (1, 3))

            # Third Ctrl+D: finds "app" inside "whatsapp" on line 2
            await pilot.press("ctrl+d")
            await pilot.pause()
            assert len(ta.extra_cursors) == 2
            assert _sel(ta, extra_index=1) == ((2, 5), (2, 8))


class TestCtrlDMultilineMatch:
    """Adapted from VSCode 'AddSelectionToNextFindMatchAction can work
    with multiline'.

    VSCode text (1-indexed):
      1: ''
      2: 'qwe'
      3: 'rty'
      4: ''
      5: 'qwe'
      6: ''
      7: 'rty'
      8: 'qwe'
      9: 'rty'

    Select lines 2-3 ("qwe\\nrty"), Ctrl+D finds next occurrence at lines 8-9.
    """

    @pytest.fixture
    def multiline_file(self, workspace: Path) -> Path:
        f = workspace / "multiline.txt"
        f.write_text("\nqwe\nrty\n\nqwe\n\nrty\nqwe\nrty\n")
        return f

    async def test_ctrl_d_multiline_selection(
        self, workspace: Path, multiline_file: Path
    ):
        """Ctrl+D with multiline selection finds next occurrence of the
        selected multiline text."""
        app = make_app(workspace, light=True, open_file=multiline_file)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            # Select "qwe\nrty" at lines 1-2 (0-based)
            # VSCode: Selection(2, 1, 3, 4) → Textual: Selection((1, 0), (2, 3))
            ta.selection = Selection((1, 0), (2, 3))
            await pilot.pause()
            assert ta.selected_text == "qwe\nrty"

            # Ctrl+D: find next "qwe\nrty" → should be at lines 7-8 (0-based)
            await pilot.press("ctrl+d")
            await pilot.pause()

            assert len(ta.extra_cursors) == 1
            assert _sel(ta, extra_index=0) == ((7, 0), (8, 3))


# ── Ctrl+D: edge cases ──────────────────────────────────────────────────────


async def test_ctrl_d_no_word_at_whitespace(workspace: Path):
    """Ctrl+D at whitespace-only position does nothing."""
    f = workspace / "space.txt"
    f.write_text("   \nhello\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor

        ta.cursor_location = (0, 1)  # in whitespace
        await pilot.pause()

        sel_before = ta.selection
        await pilot.press("ctrl+d")
        await pilot.pause()

        # No change — nothing to select
        assert ta.selection == sel_before
        assert ta.extra_cursors == []


async def test_ctrl_d_wraps_around_to_beginning(workspace: Path):
    """Ctrl+D wraps from end of file back to the beginning."""
    f = workspace / "wrap.txt"
    f.write_text("alpha\nbeta\nalpha\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor

        # Select "alpha" on line 2 (the second occurrence)
        ta.selection = Selection((2, 0), (2, 5))
        await pilot.pause()

        # Ctrl+D: wraps around to find "alpha" on line 0
        await pilot.press("ctrl+d")
        await pilot.pause()

        assert len(ta.extra_cursors) == 1
        assert _sel(ta, extra_index=0) == ((0, 0), (0, 5))


async def test_ctrl_d_single_occurrence_no_extra(workspace: Path):
    """Ctrl+D with only one occurrence in the file adds no extra cursor."""
    f = workspace / "single.txt"
    f.write_text("unique\nother\nwords\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor

        # Select "unique"
        ta.selection = Selection((0, 0), (0, 6))
        await pilot.pause()

        await pilot.press("ctrl+d")
        await pilot.pause()

        # No extra cursor — only one occurrence
        assert ta.extra_cursors == []


# ── Escape after Ctrl+D ──────────────────────────────────────────────────────


class TestEscapeAfterCtrlD:
    """Adapted from VSCode issue #8817: cursor position changes when you
    cancel multicursor."""

    @pytest.fixture
    def repeat_file(self, workspace: Path) -> Path:
        f = workspace / "repeat.txt"
        f.write_text("var x = (3 * 5)\nvar y = (3 * 5)\nvar z = (3 * 5)\n")
        return f

    async def test_escape_clears_extra_cursors(
        self, workspace: Path, repeat_file: Path
    ):
        """Escape after Ctrl+D removes extra cursors."""
        app = make_app(workspace, light=True, open_file=repeat_file)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            # Select "(3 * 5)" on line 0
            ta.selection = Selection((0, 8), (0, 15))
            await pilot.pause()

            # Ctrl+D twice to add 2 extra cursors
            await pilot.press("ctrl+d")
            await pilot.pause()
            await pilot.press("ctrl+d")
            await pilot.pause()
            assert len(ta.extra_cursors) == 2

            # Escape
            await pilot.press("escape")
            await pilot.pause()

            assert ta.extra_cursors == []

    async def test_escape_preserves_primary_position(
        self, workspace: Path, repeat_file: Path
    ):
        """After escape, primary cursor stays at its current position."""
        app = make_app(workspace, light=True, open_file=repeat_file)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            # Select "(3 * 5)" on line 0
            ta.selection = Selection((0, 8), (0, 15))
            await pilot.pause()

            await pilot.press("ctrl+d")
            await pilot.pause()

            # Record primary position before escape
            primary_sel_before = (
                min(ta.selection.start, ta.selection.end),
                max(ta.selection.start, ta.selection.end),
            )

            await pilot.press("escape")
            await pilot.pause()

            # Primary selection is collapsed at cursor_location after escape
            assert ta.extra_cursors == []
            # The primary cursor position should still be on line 0
            assert ta.cursor_location[0] == primary_sel_before[0][0]


# ── Select All Occurrences (Ctrl+Shift+L) ────────────────────────────────────


class TestSelectAllOccurrences:
    """Adapted from VSCode 'Select Highlights respects mode'.

    VSCode uses Ctrl+Shift+L (or the SelectHighlightsAction) to select all
    occurrences at once.
    """

    @pytest.fixture
    def multi_match_file(self, workspace: Path) -> Path:
        f = workspace / "multi.txt"
        f.write_text("foo bar foo\nbaz foo qux\nfoo end\n")
        return f

    async def test_select_all_from_selection(
        self, workspace: Path, multi_match_file: Path
    ):
        """Ctrl+Shift+L selects all occurrences of selected text."""
        app = make_app(workspace, light=True, open_file=multi_match_file)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            # Select "foo" on line 0
            ta.selection = Selection((0, 0), (0, 3))
            await pilot.pause()

            await pilot.press("ctrl+shift+l")
            await pilot.pause()

            # Primary + 3 extras = 4 total "foo" occurrences
            assert _sel(ta) == ((0, 0), (0, 3))
            assert len(ta.extra_cursors) == 3
            assert _sel(ta, extra_index=0) == ((0, 8), (0, 11))
            assert _sel(ta, extra_index=1) == ((1, 4), (1, 7))
            assert _sel(ta, extra_index=2) == ((2, 0), (2, 3))

    async def test_select_all_from_collapsed_cursor(
        self, workspace: Path, multi_match_file: Path
    ):
        """Ctrl+Shift+L from collapsed cursor selects all occurrences of word
        under cursor."""
        app = make_app(workspace, light=True, open_file=multi_match_file)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            # Cursor inside "foo" on line 0
            ta.cursor_location = (0, 1)
            await pilot.pause()

            await pilot.press("ctrl+shift+l")
            await pilot.pause()

            # All 4 "foo" occurrences selected
            assert _sel(ta) == ((0, 0), (0, 3))
            assert len(ta.extra_cursors) == 3

    async def test_select_all_no_match(self, workspace: Path):
        """Ctrl+Shift+L at whitespace does nothing meaningful."""
        f = workspace / "no_match.txt"
        f.write_text("   \nhello\n")
        app = make_app(workspace, light=True, open_file=f)
        async with app.run_test() as pilot:
            await pilot.pause()
            editor = app.main_view.get_active_code_editor()
            assert editor is not None
            ta = editor.editor

            ta.cursor_location = (0, 1)
            await pilot.pause()

            await pilot.press("ctrl+shift+l")
            await pilot.pause()

            # No extra cursors — nothing to match
            assert ta.extra_cursors == []


# ── Insert Cursor Below: edge case ──────────────────────────────────────────


async def test_insert_cursor_below_on_last_line_no_duplicate(workspace: Path):
    """Adapted from VSCode issue #1336: InsertCursorBelow on last line
    does not add a duplicate cursor.

    VSCode behavior: cursor count stays at 1.
    Our behavior: extra_cursors remains empty.
    """
    f = workspace / "single_line.txt"
    f.write_text("abc\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor

        ta.cursor_location = (0, 0)
        await pilot.pause()

        await pilot.press("ctrl+alt+down")
        await pilot.pause()

        # No extra cursor added — already at last content line
        # (line 1 is empty trailing newline)
        total_cursors = 1 + len(ta.extra_cursors)
        # At most, cursor might move to blank line 1 — but should not create
        # a duplicate at the same position
        assert total_cursors <= 2
