"""
Multi-cursor feature tests.

Unit-level tests exercise MultiCursorTextArea directly (API + editing logic).
Integration-level tests run the full app via pilot (CodeEditor + key bindings).
"""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.widgets.code_editor import CodeEditorFooter
from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def two_line_file(workspace: Path) -> Path:
    f = workspace / "two.txt"
    f.write_text("Hello world\nFoo bar\n")
    return f


@pytest.fixture
def three_line_file(workspace: Path) -> Path:
    f = workspace / "three.txt"
    f.write_text("line1\nline2\nline3\n")
    return f


# ── Unit: extra_cursors list ──────────────────────────────────────────────────


async def test_no_extra_cursors_initially(workspace: Path, two_line_file: Path):
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.editor.extra_cursors == []


async def test_add_cursor_adds_to_list(workspace: Path, two_line_file: Path):
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        ta.add_cursor((1, 0))
        assert (1, 0) in ta.extra_cursors


async def test_add_cursor_same_as_primary_is_noop(workspace: Path, two_line_file: Path):
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        primary = ta.cursor_location
        ta.add_cursor(primary)
        assert ta.extra_cursors == []


async def test_add_cursor_duplicate_is_noop(workspace: Path, two_line_file: Path):
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        ta.add_cursor((1, 0))
        ta.add_cursor((1, 0))  # duplicate
        assert ta.extra_cursors.count((1, 0)) == 1


async def test_clear_cursors_removes_all(workspace: Path, two_line_file: Path):
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        ta.add_cursor((1, 0))
        ta.add_cursor((1, 3))
        ta.clear_extra_cursors()
        assert ta.extra_cursors == []


# ── Unit: _new_positions (position maths) ─────────────────────────────────────


def test_new_positions_insert_same_row():
    """Insert on the same row: each cursor shifts right by 1 + num before it."""
    cursors = [(0, 3), (0, 6)]
    result = MultiCursorTextArea._new_positions(cursors, "insert")
    assert result[(0, 3)] == (0, 4)  # 0 cursors before col 3 → +1
    assert result[(0, 6)] == (0, 8)  # 1 cursor before col 6 → +1+1=+2


def test_new_positions_insert_different_rows():
    """Insert on different rows: independent shift (+1 each)."""
    cursors = [(0, 3), (1, 6)]
    result = MultiCursorTextArea._new_positions(cursors, "insert")
    assert result[(0, 3)] == (0, 4)
    assert result[(1, 6)] == (1, 7)


def test_new_positions_backspace_same_row():
    """Backspace on same row: each cursor shifts left by 1 + num before it."""
    cursors = [(0, 6), (0, 3)]
    result = MultiCursorTextArea._new_positions(cursors, "backspace")
    assert result[(0, 3)] == (0, 2)  # 0 cursors before → -1
    assert result[(0, 6)] == (0, 4)  # 1 cursor before → -1-1=-2


def test_new_positions_delete_same_row():
    """Delete on same row: cursor stays put but shifts left for deletes before it."""
    cursors = [(0, 3), (0, 6)]
    result = MultiCursorTextArea._new_positions(cursors, "delete")
    assert result[(0, 3)] == (0, 3)  # 0 cursors before → no shift
    assert result[(0, 6)] == (0, 5)  # 1 cursor before → -1


# ── Integration: Ctrl+Alt+Down / Up ───────────────────────────────────────────


async def test_ctrl_alt_down_adds_cursor_below(workspace: Path, two_line_file: Path):
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        primary_row, primary_col = ta.cursor_location

        await pilot.press("ctrl+alt+down")
        await pilot.pause()

        assert (primary_row + 1, primary_col) in ta.extra_cursors


async def test_ctrl_alt_up_adds_cursor_above(workspace: Path, three_line_file: Path):
    app = make_app(workspace, light=True, open_file=three_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        # Move primary to row 1 first
        await pilot.press("down")
        await pilot.pause()
        primary_row, primary_col = ta.cursor_location

        await pilot.press("ctrl+alt+up")
        await pilot.pause()

        assert (primary_row - 1, primary_col) in ta.extra_cursors


async def test_ctrl_alt_down_at_last_line_is_noop(workspace: Path, two_line_file: Path):
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        # Move primary to last content line manually
        last_line = ta.document.line_count - 1
        ta.cursor_location = (last_line, 0)
        await pilot.pause()

        await pilot.press("ctrl+alt+down")
        await pilot.pause()

        assert ta.extra_cursors == []


async def test_ctrl_alt_up_at_first_line_is_noop(workspace: Path, two_line_file: Path):
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        await pilot.press("ctrl+alt+up")
        await pilot.pause()

        assert ta.extra_cursors == []


# ── Integration: escape clears extra cursors ──────────────────────────────────


async def test_escape_clears_extra_cursors(workspace: Path, two_line_file: Path):
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        ta.add_cursor((1, 0))
        assert ta.extra_cursors != []

        await pilot.press("escape")
        await pilot.pause()

        assert ta.extra_cursors == []


# ── Integration: movement key clears extra cursors ────────────────────────────


async def test_movement_key_clears_extra_cursors(workspace: Path, two_line_file: Path):
    """Movement key now moves all cursors (not clears). Extra cursor moved to (1,1)."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        ta.add_cursor((1, 0))

        await pilot.press("right")
        await pilot.pause()

        # Cursor moved to (1,1), not cleared
        assert ta.extra_cursors != []
        assert ta.extra_cursors[0] == (1, 1)


# ── Integration: multi-cursor typing ─────────────────────────────────────────


async def test_typing_inserts_at_two_cursors(workspace: Path, two_line_file: Path):
    """Type 'X' with cursors on both lines inserts on both lines."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        # Move primary to (0, 0) and add extra at (1, 0)
        await pilot.press("ctrl+home")
        await pilot.pause()
        ta.add_cursor((1, 0))
        await pilot.pause()

        await pilot.press("X")
        await pilot.pause()

        lines = ta.text.split("\n")
        assert lines[0].startswith("X")
        assert lines[1].startswith("X")


async def test_backspace_deletes_at_two_cursors(workspace: Path, two_line_file: Path):
    """Backspace with cursors at col>0 on both lines deletes from both."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        # Move primary to (0, 1) and add extra at (1, 1)
        await pilot.press("ctrl+home")
        await pilot.pause()
        await pilot.press("right")
        await pilot.pause()
        ta.add_cursor((1, 1))
        await pilot.pause()

        original_lines = ta.text.split("\n")
        orig_line0 = original_lines[0]
        orig_line1 = original_lines[1]

        await pilot.press("backspace")
        await pilot.pause()

        lines = ta.text.split("\n")
        # Each line should be shorter by 1 character
        assert len(lines[0]) == len(orig_line0) - 1
        assert len(lines[1]) == len(orig_line1) - 1


async def test_delete_deletes_at_two_cursors(workspace: Path, two_line_file: Path):
    """Delete (forward) with cursors at col<EOL on both lines deletes from both."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        await pilot.press("ctrl+home")
        await pilot.pause()
        ta.add_cursor((1, 0))
        await pilot.pause()

        original_lines = ta.text.split("\n")
        orig_line0 = original_lines[0]
        orig_line1 = original_lines[1]

        await pilot.press("delete")
        await pilot.pause()

        lines = ta.text.split("\n")
        assert len(lines[0]) == len(orig_line0) - 1
        assert len(lines[1]) == len(orig_line1) - 1


# ── Integration: footer cursor count ─────────────────────────────────────────


async def test_footer_shows_cursor_count_in_multicursor_mode(
    workspace: Path, two_line_file: Path
):
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        # Single cursor: no bracket suffix
        cursor_btn = app.query_one(CodeEditorFooter).cursor_button
        assert "[" not in str(cursor_btn.label)

        ta.add_cursor((1, 0))
        await pilot.pause()

        # Multi-cursor: "[2]" suffix appears
        assert "[2]" in str(cursor_btn.label)


async def test_footer_hides_cursor_count_after_escape(
    workspace: Path, two_line_file: Path
):
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        ta.add_cursor((1, 0))
        await pilot.pause()
        assert "[2]" in str(app.query_one(CodeEditorFooter).cursor_button.label)

        await pilot.press("escape")
        await pilot.pause()

        assert "[" not in str(app.query_one(CodeEditorFooter).cursor_button.label)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def five_line_file(workspace: Path) -> Path:
    f = workspace / "five.txt"
    f.write_text("line0\nline1\nline2\nline3\nline4\n")
    return f


# ── Integration: Enter (line splits) ─────────────────────────────────────────


async def test_enter_splits_two_different_rows(workspace: Path, two_line_file: Path):
    """Enter with cursors on different rows splits both lines."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        await pilot.press("ctrl+home")
        await pilot.pause()
        await pilot.press("right", "right", "right")  # move to col 3
        await pilot.pause()
        ta.add_cursor((1, 3))
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        lines = ta.text.split("\n")
        # Original "Hello world" → "Hel" + "\n" + "lo world"
        assert lines[0] == "Hel"
        assert lines[1] == "lo world"
        # Original "Foo bar" → "Foo" + "\n" + " bar"
        assert lines[2] == "Foo"
        assert lines[3] == " bar"


async def test_enter_splits_same_row_two_cursors(workspace: Path, two_line_file: Path):
    """Enter with two cursors on the same row splits into three pieces."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        await pilot.press("ctrl+home")
        await pilot.pause()
        await pilot.press("right", "right")  # col 2
        await pilot.pause()
        ta.add_cursor((0, 5))
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        lines = ta.text.split("\n")
        # "Hello world" split at col 2 and col 5 → "He", "llo", " world"
        assert lines[0] == "He"
        assert lines[1] == "llo"
        assert lines[2] == " world"


async def test_enter_splits_same_row_three_cursors(
    workspace: Path, two_line_file: Path
):
    """Enter with three cursors on the same row produces four pieces."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        await pilot.press("ctrl+home")
        await pilot.pause()
        await pilot.press("right", "right")  # col 2
        await pilot.pause()
        ta.add_cursor((0, 5))
        ta.add_cursor((0, 8))
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        lines = ta.text.split("\n")
        # "Hello world" → "He", "llo", " wo", "rld"
        assert lines[0] == "He"
        assert lines[1] == "llo"
        assert lines[2] == " wo"
        assert lines[3] == "rld"


async def test_enter_at_col_0(workspace: Path, two_line_file: Path):
    """Enter at col 0 inserts a blank line before the current line."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        await pilot.press("ctrl+home")
        await pilot.pause()
        ta.add_cursor((1, 0))
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        lines = ta.text.split("\n")
        assert lines[0] == ""
        assert lines[1] == "Hello world"
        assert lines[2] == ""
        assert lines[3] == "Foo bar"


async def test_enter_at_eol(workspace: Path, two_line_file: Path):
    """Enter at EOL inserts a blank line after the current line."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        await pilot.press("ctrl+home")
        await pilot.pause()
        await pilot.press("end")  # move to EOL of line 0
        await pilot.pause()
        ta.add_cursor((1, 7))  # EOL of "Foo bar"
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        lines = ta.text.split("\n")
        assert lines[0] == "Hello world"
        assert lines[1] == ""
        assert lines[2] == "Foo bar"
        assert lines[3] == ""


async def test_enter_primary_position_correct(workspace: Path, two_line_file: Path):
    """Primary cursor ends at (row+1, 0) after Enter."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        await pilot.press("ctrl+home")
        await pilot.pause()
        await pilot.press("right", "right", "right")  # col 3
        await pilot.pause()
        ta.add_cursor((1, 3))
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        assert ta.cursor_location == (1, 0)


async def test_enter_extra_cursor_positions_correct(
    workspace: Path, two_line_file: Path
):
    """Extra cursors end at (row+2, 0) (shifted by primary's newline) after Enter."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        await pilot.press("ctrl+home")
        await pilot.pause()
        await pilot.press("right", "right", "right")  # col 3
        await pilot.pause()
        ta.add_cursor((1, 3))
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        assert (3, 0) in ta.extra_cursors


async def test_enter_three_different_rows(workspace: Path, five_line_file: Path):
    """3 cursors on 3 different rows — all split correctly."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        await pilot.press("ctrl+home")
        await pilot.pause()
        await pilot.press("right", "right")  # (0, 2)
        await pilot.pause()
        ta.add_cursor((1, 2))
        ta.add_cursor((2, 2))
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        lines = ta.text.split("\n")
        # Each "lineN" split at col 2 → "li" + "neN"
        assert lines[0] == "li"
        assert lines[1] == "ne0"
        assert lines[2] == "li"
        assert lines[3] == "ne1"
        assert lines[4] == "li"
        assert lines[5] == "ne2"


async def test_enter_consecutive_rows(workspace: Path, five_line_file: Path):
    """Cursors on consecutive rows split correctly with row_offset tracking."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        await pilot.press("ctrl+home")
        await pilot.pause()
        await pilot.press("down")  # row 1
        await pilot.pause()
        await pilot.press("right", "right")  # (1, 2)
        await pilot.pause()
        ta.add_cursor((2, 2))
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        lines = ta.text.split("\n")
        assert lines[0] == "line0"
        assert lines[1] == "li"
        assert lines[2] == "ne1"
        assert lines[3] == "li"
        assert lines[4] == "ne2"


async def test_enter_single_cursor_not_intercepted(
    workspace: Path, two_line_file: Path
):
    """With no extra cursors, Enter behaves normally (inserts newline via TextArea)."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        await pilot.press("ctrl+home")
        await pilot.pause()
        await pilot.press("right", "right")  # col 2
        await pilot.pause()

        original_line_count = ta.text.count("\n")
        await pilot.press("enter")
        await pilot.pause()

        assert ta.text.count("\n") == original_line_count + 1


# ── Integration: Backspace at col 0 (line merge) ──────────────────────────────


async def test_backspace_col0_two_cursors_merges(workspace: Path, five_line_file: Path):
    """Backspace at col 0 with 2 cursors merges both lines with the ones above."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        ta.cursor_location = (1, 0)
        await pilot.pause()
        ta.add_cursor((2, 0))
        await pilot.pause()

        await pilot.press("backspace")
        await pilot.pause()

        assert "line0line1" in ta.text
        assert "line1line2" in ta.text or "line0line1line2" in ta.text


async def test_backspace_col0_document_content(workspace: Path, five_line_file: Path):
    """Verify exact merged document content after backspace at col 0."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        ta.cursor_location = (1, 0)
        await pilot.pause()
        ta.add_cursor((3, 0))
        await pilot.pause()

        await pilot.press("backspace")
        await pilot.pause()

        lines = ta.text.split("\n")
        # (1,0) merges row1 into row0 → "line0line1"; then (3,0) actual_row=2
        # merges row3("line3") into row2("line2") → "line2line3"
        assert lines[0] == "line0line1"
        assert lines[1] == "line2line3"
        assert lines[2] == "line4"


async def test_backspace_col0_row0_stays(workspace: Path, two_line_file: Path):
    """Backspace at (0,0) is a no-op (can't merge above row 0)."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        await pilot.press("ctrl+home")
        await pilot.pause()
        ta.add_cursor((1, 0))
        await pilot.pause()

        await pilot.press("backspace")
        await pilot.pause()

        # Row 0 cursor is no-op; row 1 cursor merges with row 0
        assert ta.cursor_location[0] == 0


async def test_backspace_col0_mixed_clears_cursors(
    workspace: Path, five_line_file: Path
):
    """Mixed cursors (some at col 0, some not): clears extra cursors and delegates."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        ta.cursor_location = (1, 0)
        await pilot.pause()
        ta.add_cursor((0, 3))  # not at col 0
        await pilot.pause()

        await pilot.press("backspace")
        await pilot.pause()

        # Extra cursors cleared, primary handled by TextArea
        assert ta.extra_cursors == []


async def test_backspace_col0_primary_position(workspace: Path, five_line_file: Path):
    """Primary cursor ends at (prev_row, prev_len) after merge."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        ta.cursor_location = (2, 0)
        await pilot.pause()
        ta.add_cursor((3, 0))
        await pilot.pause()

        await pilot.press("backspace")
        await pilot.pause()

        # Primary (2,0) → merges with row 1 ("line1"), ends at (1, 5)
        assert ta.cursor_location == (1, 5)


async def test_backspace_col0_extra_positions(workspace: Path, five_line_file: Path):
    """Extra cursor ends at correct position after merge."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        ta.cursor_location = (2, 0)
        await pilot.pause()
        ta.add_cursor((3, 0))
        await pilot.pause()

        await pilot.press("backspace")
        await pilot.pause()

        # Extra (3,0): actual_row=3-1=2 (after primary merged row 2→1),
        # prev_len = len("line1line2") = 10, ends at (1, 10)
        assert (1, 10) in ta.extra_cursors


# ── Integration: Delete at EOL (line merge) ───────────────────────────────────


async def test_delete_eol_two_cursors_merges(workspace: Path, five_line_file: Path):
    """Delete at EOL with 2 cursors merges both lines with the ones below."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        ta.cursor_location = (0, 5)  # EOL of "line0"
        await pilot.pause()
        ta.add_cursor((1, 5))  # EOL of "line1"
        await pilot.pause()

        await pilot.press("delete")
        await pilot.pause()

        assert "line0line1" in ta.text
        assert "line1line2" in ta.text or "line0line1line2" in ta.text


async def test_delete_eol_document_content(workspace: Path, five_line_file: Path):
    """Verify exact merged document after delete at EOL."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        ta.cursor_location = (0, 5)  # EOL of "line0"
        await pilot.pause()
        ta.add_cursor((2, 5))  # EOL of "line2"
        await pilot.pause()

        await pilot.press("delete")
        await pilot.pause()

        lines = ta.text.split("\n")
        assert lines[0] == "line0line1"
        assert lines[1] == "line2line3"
        assert lines[2] == "line4"


async def test_delete_eol_last_line_stays(workspace: Path, two_line_file: Path):
    """Delete at EOL of the last line is a no-op."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        # Move to last content line, EOL
        await pilot.press("ctrl+end")
        await pilot.pause()

        ta.add_cursor((0, 11))  # EOL of "Hello world"
        await pilot.pause()

        await pilot.press("delete")
        await pilot.pause()

        # Last-line cursor is no-op; the other cursor merges
        assert ta.extra_cursors == []


async def test_delete_eol_mixed_clears_cursors(workspace: Path, five_line_file: Path):
    """Mixed cursors (some at EOL, some not): clears extra cursors and delegates."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        ta.cursor_location = (0, 5)  # EOL of "line0"
        await pilot.pause()
        ta.add_cursor((1, 2))  # not at EOL
        await pilot.pause()

        await pilot.press("delete")
        await pilot.pause()

        assert ta.extra_cursors == []


async def test_delete_eol_cursor_positions(workspace: Path, five_line_file: Path):
    """Cursor stays at EOL position (which is now mid-merged-line)."""
    app = make_app(workspace, light=True, open_file=five_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        ta.cursor_location = (0, 5)  # EOL of "line0"
        await pilot.pause()
        ta.add_cursor((1, 5))  # EOL of "line1"
        await pilot.pause()

        await pilot.press("delete")
        await pilot.pause()

        # Primary stays at (0, 5) — same position in merged line
        assert ta.cursor_location == (0, 5)
        # Extra: actual_row=1-1=0, eol_col=len("line0line1")=10 → (0, 10)
        assert (0, 10) in ta.extra_cursors


# ── Regression ────────────────────────────────────────────────────────────────


async def test_enter_regression_single_cursor(workspace: Path, two_line_file: Path):
    """Single cursor Enter still inserts a newline normally."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        await pilot.press("ctrl+home", "right", "right")
        await pilot.pause()
        line_count_before = ta.document.line_count

        await pilot.press("enter")
        await pilot.pause()

        assert ta.document.line_count == line_count_before + 1


async def test_backspace_col0_regression_single_cursor(
    workspace: Path, two_line_file: Path
):
    """Single cursor backspace at col 0 still merges with previous line normally."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        await pilot.press("ctrl+home", "down")
        await pilot.pause()
        assert ta.cursor_location == (1, 0)
        line_count_before = ta.document.line_count

        await pilot.press("backspace")
        await pilot.pause()

        assert ta.document.line_count == line_count_before - 1


async def test_delete_eol_regression_single_cursor(
    workspace: Path, two_line_file: Path
):
    """Single cursor delete at EOL still merges with next line normally."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        await pilot.press("ctrl+home", "end")
        await pilot.pause()
        line_count_before = ta.document.line_count

        await pilot.press("delete")
        await pilot.pause()

        assert ta.document.line_count == line_count_before - 1


# ── Group: extra cursor line cache invalidation ───────────────────────────────


async def test_add_cursor_clears_line_cache(workspace: Path, two_line_file: Path):
    """add_cursor() must clear _line_cache so get_line() is called on next render."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        # Trigger a render to populate the cache first
        ta.refresh()
        await pilot.pause()
        # add_cursor() must immediately clear the cache (before next render)
        ta.add_cursor((1, 0))
        assert len(ta._line_cache) == 0  # verified immediately, before next render


async def test_clear_extra_cursors_clears_line_cache(
    workspace: Path, two_line_file: Path
):
    """clear_extra_cursors() must clear _line_cache so stale highlights vanish."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        ta.add_cursor((1, 0))
        await pilot.pause()
        # Populate the cache again after add_cursor
        ta.refresh()
        await pilot.pause()
        # clear_extra_cursors() must immediately clear the cache (before next render)
        ta.clear_extra_cursors()
        assert len(ta._line_cache) == 0  # verified immediately, before next render


# ── NEW: Movement moves all cursors ──────────────────────────────────────────


async def test_arrow_key_moves_all_cursors(workspace: Path, two_line_file: Path):
    """Right arrow with extra cursor: both cursors move right."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        await pilot.press("ctrl+home")
        await pilot.pause()
        ta.add_cursor((1, 0))
        await pilot.pause()

        await pilot.press("right")
        await pilot.pause()

        assert ta.cursor_location == (0, 1)
        assert ta.extra_cursors != []
        assert ta.extra_cursors[0] == (1, 1)


async def test_home_moves_all_cursors(workspace: Path, two_line_file: Path):
    """Home key moves all cursors to col 0."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        await pilot.press("ctrl+home")
        await pilot.pause()
        await pilot.press("right", "right", "right")
        await pilot.pause()
        ta.add_cursor((1, 3))
        await pilot.pause()

        await pilot.press("home")
        await pilot.pause()

        assert ta.cursor_location == (0, 0)
        assert (1, 0) in ta.extra_cursors


async def test_ctrl_end_moves_all_cursors(workspace: Path, two_line_file: Path):
    """Ctrl+End moves all cursors to last line."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        await pilot.press("ctrl+home")
        await pilot.pause()
        ta.add_cursor((1, 0))
        await pilot.pause()

        await pilot.press("ctrl+end")
        await pilot.pause()

        lines = ta.text.split("\n")
        last_row = len(lines) - 1
        assert ta.cursor_location[0] == last_row
        # Extra cursor deduplicated (same position) → empty
        assert ta.extra_cursors == []


# ── NEW: Shift movement creates selections ────────────────────────────────────


async def test_shift_left_creates_extra_selection(workspace: Path, two_line_file: Path):
    """Shift+Left with extra cursor: extra cursor gets anchor != cursor."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        await pilot.press("ctrl+home")
        await pilot.pause()
        await pilot.press("right", "right")
        await pilot.pause()
        ta.add_cursor((1, 2))
        await pilot.pause()

        await pilot.press("shift+left")
        await pilot.pause()

        anchors = ta.extra_anchors
        assert len(anchors) == 1
        assert anchors[0] == (1, 2)
        assert ta.extra_cursors[0] == (1, 1)


async def test_ctrl_shift_right_creates_word_selection(
    workspace: Path, two_line_file: Path
):
    """Ctrl+Shift+Right on extra cursor creates a word-level selection."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        await pilot.press("ctrl+home")
        await pilot.pause()
        ta.add_cursor((1, 0))
        await pilot.pause()

        await pilot.press("ctrl+shift+right")
        await pilot.pause()

        anchors = ta.extra_anchors
        assert len(anchors) == 1
        assert anchors[0] == (1, 0)
        assert ta.extra_cursors[0][1] > 0


async def test_ctrl_shift_left_creates_word_selection(
    workspace: Path, two_line_file: Path
):
    """Ctrl+Shift+Left on extra cursor creates a word-level selection leftward."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        await pilot.press("ctrl+home")
        await pilot.pause()
        await pilot.press("right", "right", "right", "right", "right")
        await pilot.pause()
        ta.add_cursor((1, 5))
        await pilot.pause()

        await pilot.press("ctrl+shift+left")
        await pilot.pause()

        anchors = ta.extra_anchors
        assert len(anchors) == 1
        assert anchors[0] == (1, 5)
        assert ta.extra_cursors[0][1] < 5


# ── NEW: add_cursor with anchor ───────────────────────────────────────────────


async def test_add_cursor_with_anchor(workspace: Path, two_line_file: Path):
    """add_cursor(loc, anchor=a) stores the given anchor."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        ta.add_cursor((1, 3), anchor=(1, 0))
        assert ta.extra_cursors == [(1, 3)]
        assert ta.extra_anchors == [(1, 0)]


async def test_extra_anchor_default_equals_cursor(workspace: Path, two_line_file: Path):
    """add_cursor(loc) without anchor → anchor == cursor (collapsed)."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        ta.add_cursor((1, 2))
        assert ta.extra_anchors == [(1, 2)]


# ── NEW: Editing with selections ──────────────────────────────────────────────


async def test_typing_with_selection_replaces(workspace: Path, two_line_file: Path):
    """Type 'X' with selection on extra cursor replaces the selection."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        await pilot.press("ctrl+home")
        await pilot.pause()
        # Primary at (0,0) collapsed, extra selects "Foo" on line 1
        ta.add_cursor((1, 3), anchor=(1, 0))
        await pilot.pause()

        await pilot.press("X")
        await pilot.pause()

        lines = ta.text.split("\n")
        assert lines[0].startswith("X")
        assert lines[1].startswith("X")


async def test_backspace_with_selection_deletes(workspace: Path, two_line_file: Path):
    """Backspace with selection on extra cursor deletes the selection."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        await pilot.press("ctrl+home")
        await pilot.pause()
        await pilot.press("right")
        await pilot.pause()
        # Primary at (0,1) collapsed, extra selects "Foo" on line 1
        ta.add_cursor((1, 3), anchor=(1, 0))
        await pilot.pause()

        await pilot.press("backspace")
        await pilot.pause()

        assert " bar" in ta.text


async def test_typing_with_overlapping_selections(workspace: Path, two_line_file: Path):
    """Overlapping selections deduped — text replaced once per region."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        ta = editor.editor
        from textual.widgets.text_area import Selection

        await pilot.press("ctrl+home")
        await pilot.pause()
        editor.editor.selection = Selection(start=(0, 0), end=(0, 3))
        ta.add_cursor((0, 5), anchor=(0, 1))
        await pilot.pause()

        original_line = ta.text.split("\n")[0]

        await pilot.press("Z")
        await pilot.pause()

        line0 = ta.text.split("\n")[0]
        assert len(line0) < len(original_line)


# ── NEW: Deduplication after movement ────────────────────────────────────────


async def test_movement_deduplicates_cursors(workspace: Path, two_line_file: Path):
    """Home key: two cursors on same row both land at col 0 → deduplicated."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        await pilot.press("ctrl+home")
        await pilot.pause()
        await pilot.press("right", "right")
        await pilot.pause()
        ta.add_cursor((0, 3))
        await pilot.pause()

        await pilot.press("home")
        await pilot.pause()

        assert ta.extra_cursors == []


async def test_movement_primary_extra_collision(workspace: Path, two_line_file: Path):
    """No extra cursor equals primary cursor after movement."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        await pilot.press("ctrl+home")
        await pilot.pause()
        await pilot.press("right")
        await pilot.pause()
        ta.add_cursor((0, 0))
        await pilot.pause()

        await pilot.press("right")
        await pilot.pause()

        primary = ta.cursor_location
        for ec in ta.extra_cursors:
            assert ec != primary


# ── NEW: Unit tests for _move_location ───────────────────────────────────────


def test_move_location_left():
    from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

    lines = ["hello", "world"]
    assert MultiCursorTextArea._move_location(lines, 0, 3, "left") == (0, 2)
    assert MultiCursorTextArea._move_location(lines, 0, 0, "left") == (0, 0)
    assert MultiCursorTextArea._move_location(lines, 1, 0, "left") == (0, 5)


def test_move_location_right():
    from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

    lines = ["hello", "world"]
    assert MultiCursorTextArea._move_location(lines, 0, 3, "right") == (0, 4)
    assert MultiCursorTextArea._move_location(lines, 0, 5, "right") == (1, 0)
    assert MultiCursorTextArea._move_location(lines, 1, 5, "right") == (1, 5)


def test_move_location_ctrl_left():
    from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

    lines = ["hello world"]
    result = MultiCursorTextArea._move_location(lines, 0, 8, "ctrl+left")
    assert result == (0, 6)


def test_move_location_ctrl_right():
    from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

    lines = ["hello world"]
    result = MultiCursorTextArea._move_location(lines, 0, 0, "ctrl+right")
    assert result[1] > 0
    assert result[0] == 0


# ── NEW: Unit tests for module-level helpers ──────────────────────────────────


def test_build_offsets():
    from textual_code.widgets.multi_cursor_text_area import _build_offsets

    lines = ["abc", "de", "f"]
    offsets = _build_offsets(lines)
    assert offsets[0] == 0
    assert offsets[1] == 4
    assert offsets[2] == 7


def test_offset_to_loc():
    from textual_code.widgets.multi_cursor_text_area import (
        _build_offsets,
        _offset_to_loc,
    )

    lines = ["abc", "de", "f"]
    offsets = _build_offsets(lines)
    assert _offset_to_loc(0, lines, offsets) == (0, 0)
    assert _offset_to_loc(2, lines, offsets) == (0, 2)
    assert _offset_to_loc(4, lines, offsets) == (1, 0)
    assert _offset_to_loc(6, lines, offsets) == (1, 2)


def test_loc_to_offset():
    from textual_code.widgets.multi_cursor_text_area import (
        _build_offsets,
        _loc_to_offset,
    )

    lines = ["abc", "de", "f"]
    offsets = _build_offsets(lines)
    assert _loc_to_offset(lines, 0, 0, offsets) == 0
    assert _loc_to_offset(lines, 0, 2, offsets) == 2
    assert _loc_to_offset(lines, 1, 0, offsets) == 4
    assert _loc_to_offset(lines, 1, 2, offsets) == 6


# ── UPDATE: movement moves cursors, not clears ────────────────────────────────


async def test_movement_key_moves_not_clears(workspace: Path, two_line_file: Path):
    """Movement key now moves all cursors instead of clearing them."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        await pilot.press("ctrl+home")
        await pilot.pause()
        ta.add_cursor((1, 0))
        await pilot.pause()

        await pilot.press("right")
        await pilot.pause()

        assert ta.extra_cursors != []
        assert ta.extra_cursors[0] == (1, 1)


# ── Ctrl+A: select all ────────────────────────────────────────────────────────


async def test_ctrl_a_selects_all_text(workspace: Path, two_line_file: Path):
    """Ctrl+A selects the entire document text."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        await pilot.press("ctrl+a")
        await pilot.pause()
        # selection should span from (0,0) to end of document
        sel = ta.selection
        assert sel.start == (0, 0)
        assert sel.end[0] == ta.document.line_count - 1


async def test_ctrl_a_clears_extra_cursors(workspace: Path, two_line_file: Path):
    """Ctrl+A removes extra cursors."""
    app = make_app(workspace, light=True, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        ta.add_cursor((1, 0))
        await pilot.pause()
        assert ta.extra_cursors != []

        await pilot.press("ctrl+a")
        await pilot.pause()
        assert ta.extra_cursors == []


async def test_ctrl_a_on_empty_document(workspace: Path):
    """Ctrl+A on an empty document doesn't raise."""
    empty = workspace / "empty.txt"
    empty.write_text("")
    app = make_app(workspace, light=True, open_file=empty)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        await pilot.press("ctrl+a")
        await pilot.pause()
        assert ta.extra_cursors == []
