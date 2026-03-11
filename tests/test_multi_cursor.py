"""
Multi-cursor feature tests.

Unit-level tests exercise MultiCursorTextArea directly (API + editing logic).
Integration-level tests run the full app via pilot (CodeEditor + key bindings).
"""

from pathlib import Path

import pytest

from tests.conftest import make_app
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
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.editor.extra_cursors == []


async def test_add_cursor_adds_to_list(workspace: Path, two_line_file: Path):
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        ta.add_cursor((1, 0))
        assert (1, 0) in ta.extra_cursors


async def test_add_cursor_same_as_primary_is_noop(workspace: Path, two_line_file: Path):
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        primary = ta.cursor_location
        ta.add_cursor(primary)
        assert ta.extra_cursors == []


async def test_add_cursor_duplicate_is_noop(workspace: Path, two_line_file: Path):
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        ta.add_cursor((1, 0))
        ta.add_cursor((1, 0))  # duplicate
        assert ta.extra_cursors.count((1, 0)) == 1


async def test_clear_cursors_removes_all(workspace: Path, two_line_file: Path):
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        primary_row, primary_col = ta.cursor_location

        await pilot.press("ctrl+alt+down")
        await pilot.pause()

        assert (primary_row + 1, primary_col) in ta.extra_cursors


async def test_ctrl_alt_up_adds_cursor_above(workspace: Path, three_line_file: Path):
    app = make_app(workspace, open_file=three_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor

        await pilot.press("ctrl+alt+up")
        await pilot.pause()

        assert ta.extra_cursors == []


# ── Integration: escape clears extra cursors ──────────────────────────────────


async def test_escape_clears_extra_cursors(workspace: Path, two_line_file: Path):
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = app.main_view.get_active_code_editor().editor
        ta.add_cursor((1, 0))

        await pilot.press("right")
        await pilot.pause()

        assert ta.extra_cursors == []


# ── Integration: multi-cursor typing ─────────────────────────────────────────


async def test_typing_inserts_at_two_cursors(workspace: Path, two_line_file: Path):
    """Type 'X' with cursors on both lines inserts on both lines."""
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        ta = editor.editor

        # Single cursor: no bracket suffix
        cursor_btn = editor.footer.cursor_button
        assert "[" not in str(cursor_btn.label)

        ta.add_cursor((1, 0))
        await pilot.pause()

        # Multi-cursor: "[2]" suffix appears
        assert "[2]" in str(cursor_btn.label)


async def test_footer_hides_cursor_count_after_escape(
    workspace: Path, two_line_file: Path
):
    app = make_app(workspace, open_file=two_line_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        ta = editor.editor

        ta.add_cursor((1, 0))
        await pilot.pause()
        assert "[2]" in str(editor.footer.cursor_button.label)

        await pilot.press("escape")
        await pilot.pause()

        assert "[" not in str(editor.footer.cursor_button.label)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def five_line_file(workspace: Path) -> Path:
    f = workspace / "five.txt"
    f.write_text("line0\nline1\nline2\nline3\nline4\n")
    return f


# ── Integration: Enter (line splits) ─────────────────────────────────────────


async def test_enter_splits_two_different_rows(workspace: Path, two_line_file: Path):
    """Enter with cursors on different rows splits both lines."""
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=five_line_file)
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
    app = make_app(workspace, open_file=five_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=five_line_file)
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
    app = make_app(workspace, open_file=five_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=five_line_file)
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
    app = make_app(workspace, open_file=five_line_file)
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
    app = make_app(workspace, open_file=five_line_file)
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
    app = make_app(workspace, open_file=five_line_file)
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
    app = make_app(workspace, open_file=five_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=five_line_file)
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
    app = make_app(workspace, open_file=five_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
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
    app = make_app(workspace, open_file=two_line_file)
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
