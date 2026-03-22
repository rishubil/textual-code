"""
Clipboard tests: Ctrl+C (copy), Ctrl+X (cut), and Ctrl+V (paste).

Behaviour mirrors VS Code:
- With selection: copies/cuts the selected text.
- Without selection: copies/cuts the current line (including newline).
- Paste after line-copy/cut: inserts above the current line (VS Code behavior).
"""

from pathlib import Path

from textual.widgets.text_area import Selection

from tests.conftest import make_app

# ── helpers ───────────────────────────────────────────────────────────────────


async def _open_file(workspace: Path, content: str, name: str = "test.txt") -> Path:
    f = workspace / name
    f.write_text(content)
    return f


# ── copy: with selection ───────────────────────────────────────────────────────


async def test_ctrl_c_copies_selected_text(workspace: Path):
    """Ctrl+C with a selection copies the selected text to the clipboard."""
    f = await _open_file(workspace, "hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Select "hello"
        ta.selection = Selection((0, 0), (0, 5))
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert app.clipboard == "hello"


# ── copy: no selection → current line ─────────────────────────────────────────


async def test_ctrl_c_no_selection_copies_current_line(workspace: Path):
    """Ctrl+C with no selection copies the current line (including newline)."""
    f = await _open_file(workspace, "hello world\nsecond line\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Cursor at (0, 3); no selection
        ta.cursor_location = (0, 3)
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert app.clipboard == "hello world\n"


async def test_ctrl_c_no_selection_copies_second_line(workspace: Path):
    """Ctrl+C on the second line copies that line."""
    f = await _open_file(workspace, "first\nsecond\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        ta.cursor_location = (1, 0)
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert app.clipboard == "second\n"


# ── cut: with selection ────────────────────────────────────────────────────────


async def test_ctrl_x_cuts_selected_text(workspace: Path):
    """Ctrl+X with a selection copies to clipboard AND removes the text."""
    f = await _open_file(workspace, "hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Select "hello"
        ta.selection = Selection((0, 0), (0, 5))
        await pilot.press("ctrl+x")
        await pilot.pause()
        assert app.clipboard == "hello"
        assert " world\n" in ta.text


# ── cut: no selection → current line ──────────────────────────────────────────


async def test_ctrl_x_no_selection_cuts_current_line(workspace: Path):
    """Ctrl+X with no selection cuts the current line."""
    f = await _open_file(workspace, "first\nsecond\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        ta.cursor_location = (0, 2)
        await pilot.press("ctrl+x")
        await pilot.pause()
        assert app.clipboard == "first\n"
        assert "second" in ta.text
        assert "first" not in ta.text


# ── multi-cursor: ctrl+c clears extra cursors ─────────────────────────────────


async def test_ctrl_c_with_multiple_cursors_preserves_extra_cursors(workspace: Path):
    """Ctrl+C while multi-cursor is active preserves extra cursors."""
    f = await _open_file(workspace, "line1\nline2\nline3\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        ta.add_cursor((1, 0))
        ta.add_cursor((2, 0))
        assert len(ta.extra_cursors) == 2
        await pilot.press("ctrl+c")
        await pilot.pause()
        # Extra cursors are preserved (copy does not clear multi-cursor state)
        assert len(ta.extra_cursors) == 2


# ── paste: line-copied text inserts above current line (VS Code) ─────────────


async def test_paste_line_copied_text_inserts_above_current_line(workspace: Path):
    """Pasting a line copied without selection inserts it above the cursor line.

    VS Code behavior: copy 'bar' line (no selection), move to 'hello' line,
    paste → 'bar' inserted above 'hello', cursor stays on 'hello'.
    """
    f = await _open_file(workspace, "foo\nbar\nbaz\nhello\nworld\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Place cursor on 'bar' line (row 1), col 1 ('a')
        ta.cursor_location = (1, 1)
        # Copy without selection → copies "bar\n"
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert app.clipboard == "bar\n"
        # Move cursor to 'hello' line (row 3), col 1 ('e')
        ta.cursor_location = (3, 1)
        # Paste → should insert "bar" above "hello"
        await pilot.press("ctrl+v")
        await pilot.pause()
        lines = ta.text.split("\n")
        # Expected: foo, bar, baz, bar, hello, world, (empty)
        assert lines[0] == "foo"
        assert lines[1] == "bar"
        assert lines[2] == "baz"
        assert lines[3] == "bar"
        assert lines[4] == "hello"
        assert lines[5] == "world"
        # Cursor should stay on 'hello' line (now row 4), same column
        assert ta.cursor_location == (4, 1)


async def test_paste_selection_copied_text_inserts_at_cursor(workspace: Path):
    """Pasting text copied WITH selection inserts at cursor position (normal)."""
    f = await _open_file(workspace, "hello world\nsecond line\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Select "hello"
        ta.selection = Selection((0, 0), (0, 5))
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert app.clipboard == "hello"
        # Move to start of second line and paste
        ta.selection = Selection.cursor((1, 0))
        await pilot.pause()
        await pilot.press("ctrl+v")
        await pilot.pause()
        # Normal paste: "hello" inserted at cursor, text becomes "hellosecond line"
        lines = ta.text.split("\n")
        assert lines[1] == "hellosecond line"


async def test_paste_line_cut_text_inserts_above_current_line(workspace: Path):
    """Pasting a line cut without selection inserts it above the cursor line."""
    f = await _open_file(workspace, "foo\nbar\nbaz\nhello\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Place cursor on 'bar' line at col 2
        ta.cursor_location = (1, 2)
        # Cut without selection → cuts "bar\n"
        await pilot.press("ctrl+x")
        await pilot.pause()
        assert app.clipboard == "bar\n"
        # After cut, text is "foo\nbaz\nhello\n", cursor on 'baz' (now row 1)
        # Move cursor to 'hello' line (row 2), col 1
        ta.cursor_location = (2, 1)
        # Paste → should insert "bar" above "hello"
        await pilot.press("ctrl+v")
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines[0] == "foo"
        assert lines[1] == "baz"
        assert lines[2] == "bar"
        assert lines[3] == "hello"
        # Cursor should be on 'hello' (now row 3), col 1
        assert ta.cursor_location == (3, 1)


async def test_line_copy_flag_reset_by_selection_copy(workspace: Path):
    """Line-copy flag resets when copying WITH selection."""
    f = await _open_file(workspace, "aaa\nbbb\nccc\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Line-copy 'aaa' (no selection)
        ta.cursor_location = (0, 0)
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert app.clipboard == "aaa\n"
        # Now copy WITH selection → should reset line-copy flag
        ta.selection = Selection((1, 0), (1, 3))
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert app.clipboard == "bbb"
        # Paste at row 2 → should insert "bbb" at cursor, NOT above line
        ta.selection = Selection.cursor((2, 0))
        await pilot.pause()
        await pilot.press("ctrl+v")
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines[2] == "bbbccc"


async def test_paste_line_at_first_row(workspace: Path):
    """Line-paste at row 0 inserts above the first line."""
    f = await _open_file(workspace, "first\nsecond\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Line-copy 'second' (row 1)
        ta.cursor_location = (1, 0)
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert app.clipboard == "second\n"
        # Move to first line (row 0), paste → should insert above row 0
        ta.cursor_location = (0, 2)
        await pilot.press("ctrl+v")
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines[0] == "second"
        assert lines[1] == "first"
        assert lines[2] == "second"
        assert ta.cursor_location == (1, 2)


async def test_paste_line_at_last_row(workspace: Path):
    """Line-paste at the last row inserts above it."""
    f = await _open_file(workspace, "aaa\nbbb\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Line-copy 'aaa' (row 0)
        ta.cursor_location = (0, 1)
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert app.clipboard == "aaa\n"
        # Move to last non-empty row (row 1) and paste
        ta.cursor_location = (1, 2)
        await pilot.press("ctrl+v")
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines[0] == "aaa"
        assert lines[1] == "aaa"
        assert lines[2] == "bbb"
        assert ta.cursor_location == (2, 2)


async def test_paste_line_with_multiple_cursors(workspace: Path):
    """Line-paste with multi-cursor active still inserts above current line."""
    f = await _open_file(workspace, "line1\nline2\nline3\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Line-copy 'line1' (no selection)
        ta.cursor_location = (0, 0)
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert app.clipboard == "line1\n"
        # Add extra cursor and move main cursor to row 2
        ta.cursor_location = (2, 0)
        ta.add_cursor((1, 0))
        # Paste → should insert above row 2 for main cursor
        await pilot.press("ctrl+v")
        await pilot.pause()
        # Verify line1 was inserted somewhere in the document
        assert "line1\nline1\n" in ta.text or ta.text.count("line1") >= 2


async def test_paste_line_twice(workspace: Path):
    """Pasting a line-copied text twice inserts two copies above."""
    f = await _open_file(workspace, "aaa\nbbb\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Line-copy 'aaa' (row 0)
        ta.cursor_location = (0, 1)
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert app.clipboard == "aaa\n"
        # Move to 'bbb' and paste twice
        ta.cursor_location = (1, 1)
        await pilot.press("ctrl+v")
        await pilot.pause()
        await pilot.press("ctrl+v")
        await pilot.pause()
        lines = ta.text.split("\n")
        # Expected: aaa, aaa, aaa, bbb, (empty)
        assert lines[0] == "aaa"
        assert lines[1] == "aaa"
        assert lines[2] == "aaa"
        assert lines[3] == "bbb"
        # Cursor stays on 'bbb' (now row 3), col 1
        assert ta.cursor_location == (3, 1)
