"""
Clipboard tests: Ctrl+C (copy), Ctrl+X (cut), and Ctrl+V (paste).

Behaviour mirrors VS Code:
- With selection: copies/cuts the selected text.
- Without selection: copies/cuts the current line (including newline).
- Paste after line-copy/cut: inserts above the current line (VS Code behavior).
- Paste via terminal Paste event (bracketed paste) should behave the same.
"""

from pathlib import Path

from textual import events
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
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Select "hello"
        ta.selection = Selection((0, 0), (0, 5))
        await pilot.press("ctrl+c")
        await pilot.wait_for_scheduled_animations()
        assert app.clipboard == "hello"


# ── copy: no selection → current line ─────────────────────────────────────────


async def test_ctrl_c_no_selection_copies_current_line(workspace: Path):
    """Ctrl+C with no selection copies the current line (including newline)."""
    f = await _open_file(workspace, "hello world\nsecond line\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Cursor at (0, 3); no selection
        ta.cursor_location = (0, 3)
        await pilot.press("ctrl+c")
        await pilot.wait_for_scheduled_animations()
        assert app.clipboard == "hello world\n"


async def test_ctrl_c_no_selection_copies_second_line(workspace: Path):
    """Ctrl+C on the second line copies that line."""
    f = await _open_file(workspace, "first\nsecond\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        ta.cursor_location = (1, 0)
        await pilot.press("ctrl+c")
        await pilot.wait_for_scheduled_animations()
        assert app.clipboard == "second\n"


# ── cut: with selection ────────────────────────────────────────────────────────


async def test_ctrl_x_cuts_selected_text(workspace: Path):
    """Ctrl+X with a selection copies to clipboard AND removes the text."""
    f = await _open_file(workspace, "hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Select "hello"
        ta.selection = Selection((0, 0), (0, 5))
        await pilot.press("ctrl+x")
        await pilot.wait_for_scheduled_animations()
        assert app.clipboard == "hello"
        assert " world\n" in ta.text


# ── cut: no selection → current line ──────────────────────────────────────────


async def test_ctrl_x_no_selection_cuts_current_line(workspace: Path):
    """Ctrl+X with no selection cuts the current line."""
    f = await _open_file(workspace, "first\nsecond\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        ta.cursor_location = (0, 2)
        await pilot.press("ctrl+x")
        await pilot.wait_for_scheduled_animations()
        assert app.clipboard == "first\n"
        assert "second" in ta.text
        assert "first" not in ta.text


# ── multi-cursor: ctrl+c clears extra cursors ─────────────────────────────────


async def test_ctrl_c_with_multiple_cursors_preserves_extra_cursors(workspace: Path):
    """Ctrl+C while multi-cursor is active preserves extra cursors."""
    f = await _open_file(workspace, "line1\nline2\nline3\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        ta.add_cursor((1, 0))
        ta.add_cursor((2, 0))
        assert len(ta.extra_cursors) == 2
        await pilot.press("ctrl+c")
        await pilot.wait_for_scheduled_animations()
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
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Place cursor on 'bar' line (row 1), col 1 ('a')
        ta.cursor_location = (1, 1)
        # Copy without selection → copies "bar\n"
        await pilot.press("ctrl+c")
        await pilot.wait_for_scheduled_animations()
        assert app.clipboard == "bar\n"
        # Move cursor to 'hello' line (row 3), col 1 ('e')
        ta.cursor_location = (3, 1)
        # Paste → should insert "bar" above "hello"
        await pilot.press("ctrl+v")
        await pilot.wait_for_scheduled_animations()
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
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Select "hello"
        ta.selection = Selection((0, 0), (0, 5))
        await pilot.press("ctrl+c")
        await pilot.wait_for_scheduled_animations()
        assert app.clipboard == "hello"
        # Move to start of second line and paste
        ta.selection = Selection.cursor((1, 0))
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+v")
        await pilot.wait_for_scheduled_animations()
        # Normal paste: "hello" inserted at cursor, text becomes "hellosecond line"
        lines = ta.text.split("\n")
        assert lines[1] == "hellosecond line"


async def test_paste_line_cut_text_inserts_above_current_line(workspace: Path):
    """Pasting a line cut without selection inserts it above the cursor line."""
    f = await _open_file(workspace, "foo\nbar\nbaz\nhello\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Place cursor on 'bar' line at col 2
        ta.cursor_location = (1, 2)
        # Cut without selection → cuts "bar\n"
        await pilot.press("ctrl+x")
        await pilot.wait_for_scheduled_animations()
        assert app.clipboard == "bar\n"
        # After cut, text is "foo\nbaz\nhello\n", cursor on 'baz' (now row 1)
        # Move cursor to 'hello' line (row 2), col 1
        ta.cursor_location = (2, 1)
        # Paste → should insert "bar" above "hello"
        await pilot.press("ctrl+v")
        await pilot.wait_for_scheduled_animations()
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
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Line-copy 'aaa' (no selection)
        ta.cursor_location = (0, 0)
        await pilot.press("ctrl+c")
        await pilot.wait_for_scheduled_animations()
        assert app.clipboard == "aaa\n"
        # Now copy WITH selection → should reset line-copy flag
        ta.selection = Selection((1, 0), (1, 3))
        await pilot.press("ctrl+c")
        await pilot.wait_for_scheduled_animations()
        assert app.clipboard == "bbb"
        # Paste at row 2 → should insert "bbb" at cursor, NOT above line
        ta.selection = Selection.cursor((2, 0))
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+v")
        await pilot.wait_for_scheduled_animations()
        lines = ta.text.split("\n")
        assert lines[2] == "bbbccc"


async def test_paste_line_at_first_row(workspace: Path):
    """Line-paste at row 0 inserts above the first line."""
    f = await _open_file(workspace, "first\nsecond\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Line-copy 'second' (row 1)
        ta.cursor_location = (1, 0)
        await pilot.press("ctrl+c")
        await pilot.wait_for_scheduled_animations()
        assert app.clipboard == "second\n"
        # Move to first line (row 0), paste → should insert above row 0
        ta.cursor_location = (0, 2)
        await pilot.press("ctrl+v")
        await pilot.wait_for_scheduled_animations()
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
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Line-copy 'aaa' (row 0)
        ta.cursor_location = (0, 1)
        await pilot.press("ctrl+c")
        await pilot.wait_for_scheduled_animations()
        assert app.clipboard == "aaa\n"
        # Move to last non-empty row (row 1) and paste
        ta.cursor_location = (1, 2)
        await pilot.press("ctrl+v")
        await pilot.wait_for_scheduled_animations()
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
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Line-copy 'line1' (no selection)
        ta.cursor_location = (0, 0)
        await pilot.press("ctrl+c")
        await pilot.wait_for_scheduled_animations()
        assert app.clipboard == "line1\n"
        # Add extra cursor and move main cursor to row 2
        ta.cursor_location = (2, 0)
        ta.add_cursor((1, 0))
        # Paste → should insert above row 2 for main cursor
        await pilot.press("ctrl+v")
        await pilot.wait_for_scheduled_animations()
        # Verify line1 was inserted somewhere in the document
        assert "line1\nline1\n" in ta.text or ta.text.count("line1") >= 2


async def test_paste_line_twice(workspace: Path):
    """Pasting a line-copied text twice inserts two copies above."""
    f = await _open_file(workspace, "aaa\nbbb\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Line-copy 'aaa' (row 0)
        ta.cursor_location = (0, 1)
        await pilot.press("ctrl+c")
        await pilot.wait_for_scheduled_animations()
        assert app.clipboard == "aaa\n"
        # Move to 'bbb' and paste twice
        ta.cursor_location = (1, 1)
        await pilot.press("ctrl+v")
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+v")
        await pilot.wait_for_scheduled_animations()
        lines = ta.text.split("\n")
        # Expected: aaa, aaa, aaa, bbb, (empty)
        assert lines[0] == "aaa"
        assert lines[1] == "aaa"
        assert lines[2] == "aaa"
        assert lines[3] == "bbb"
        # Cursor stays on 'bbb' (now row 3), col 1
        assert ta.cursor_location == (3, 1)


# ── Paste event (bracketed paste / Windows terminal) ─────────────────────────
# On Windows Terminal, Ctrl+V sends a Paste event instead of triggering the
# action_paste key binding.  These tests verify that the Paste event path
# behaves identically to action_paste.


async def test_paste_event_preserves_trailing_whitespace(workspace: Path):
    """Paste event should preserve trailing whitespace from local clipboard."""
    f = await _open_file(workspace, "hello\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Copy text with trailing spaces to local clipboard
        text_with_spaces = "   foo   "
        app.copy_to_clipboard(text_with_spaces)
        # Move cursor and simulate Paste event (as Windows terminal would send)
        ta.selection = Selection.cursor((0, 0))
        await pilot.wait_for_scheduled_animations()
        await ta._on_paste(events.Paste(text_with_spaces))
        await pilot.wait_for_scheduled_animations()
        # Trailing spaces must be preserved
        assert "   foo   " in ta.text


async def test_paste_event_line_copy_inserts_above(workspace: Path):
    """Paste event after line-copy should insert above the current line."""
    f = await _open_file(workspace, "foo\nbar\nbaz\nhello\nworld\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Line-copy 'bar' (no selection)
        ta.cursor_location = (1, 1)
        await pilot.press("ctrl+c")
        await pilot.wait_for_scheduled_animations()
        assert app.clipboard == "bar\n"
        # Move cursor to 'hello' line
        ta.cursor_location = (3, 1)
        # Simulate Paste event (as Windows terminal would send)
        await ta._on_paste(events.Paste("bar\n"))
        await pilot.wait_for_scheduled_animations()
        lines = ta.text.split("\n")
        # Expected: foo, bar, baz, bar, hello, world, (empty)
        assert lines[3] == "bar"
        assert lines[4] == "hello"
        # Cursor should stay on 'hello' (now row 4), same column
        assert ta.cursor_location == (4, 1)


async def test_paste_event_normalizes_crlf(workspace: Path):
    """Paste event with CRLF text should normalize to LF."""
    f = await _open_file(workspace, "hello\nworld\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        ta.selection = Selection.cursor((0, 0))
        await pilot.wait_for_scheduled_animations()
        # Simulate Paste event with CRLF (as Windows clipboard would provide)
        await ta._on_paste(events.Paste("line1\r\nline2"))
        await pilot.wait_for_scheduled_animations()
        # Should not contain \r in the document
        assert "\r" not in ta.text
        assert "line1\nline2" in ta.text


async def test_paste_event_with_stripped_trailing_spaces(workspace: Path):
    """Paste event with trailing-space-stripped text should prefer local clipboard."""
    f = await _open_file(workspace, "hello\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Copy text with trailing spaces to local clipboard
        app.copy_to_clipboard("foo   ")
        ta.selection = Selection.cursor((0, 0))
        await pilot.wait_for_scheduled_animations()
        # Simulate Paste event with stripped text (as Windows Terminal would send)
        # The local clipboard should be preferred to preserve trailing spaces
        await ta._on_paste(events.Paste("foo"))
        await pilot.wait_for_scheduled_animations()
        # Local clipboard "foo   " should be used (trailing spaces preserved)
        assert "foo   " in ta.text


async def test_paste_event_line_copy_with_stripped_whitespace(workspace: Path):
    """Line-paste via Paste event works even when terminal strips trailing spaces."""
    f = await _open_file(workspace, "foo\nbar  \nbaz\nhello\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Line-copy 'bar  ' (no selection, row 1) → clipboard = "bar  \n"
        ta.cursor_location = (1, 1)
        await pilot.press("ctrl+c")
        await pilot.wait_for_scheduled_animations()
        assert app.clipboard == "bar  \n"
        # Move cursor to 'hello' line (row 3)
        ta.cursor_location = (3, 1)
        # Simulate Paste event with stripped text
        # (Windows Terminal strips trailing spaces)
        await ta._on_paste(events.Paste("bar\n"))
        await pilot.wait_for_scheduled_animations()
        lines = ta.text.split("\n")
        # Expected: foo, bar  , baz, bar  , hello, (empty)
        # Line-paste should insert "bar  " ABOVE "hello"
        assert lines[3] == "bar  "
        assert lines[4] == "hello"
        # Cursor should stay on 'hello' (now row 4), same column
        assert ta.cursor_location == (4, 1)


async def test_paste_event_line_copy_with_stripped_trailing_newline(workspace: Path):
    """Line-paste via Paste event works when terminal strips trailing newline."""
    f = await _open_file(workspace, "foo\nbar\nbaz\nhello\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Line-copy 'bar' (no selection, row 1) → clipboard = "bar\n"
        ta.cursor_location = (1, 1)
        await pilot.press("ctrl+c")
        await pilot.wait_for_scheduled_animations()
        assert app.clipboard == "bar\n"
        # Move cursor to 'hello' line (row 3)
        ta.cursor_location = (3, 1)
        # Simulate Paste event with stripped trailing newline
        # (Windows Terminal may strip trailing newline from clipboard text)
        await ta._on_paste(events.Paste("bar"))
        await pilot.wait_for_scheduled_animations()
        lines = ta.text.split("\n")
        # Line-paste should insert "bar" ABOVE "hello"
        assert lines[3] == "bar"
        assert lines[4] == "hello"
        # Cursor should stay on 'hello' (now row 4), same column
        assert ta.cursor_location == (4, 1)


async def test_paste_event_truly_different_text_uses_event(workspace: Path):
    """Paste event with genuinely different text should use event text."""
    f = await _open_file(workspace, "hello\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Local clipboard has something
        app.copy_to_clipboard("foo   ")
        ta.selection = Selection.cursor((0, 0))
        await pilot.wait_for_scheduled_animations()
        # Simulate Paste event with completely different text
        await ta._on_paste(events.Paste("completely different"))
        await pilot.wait_for_scheduled_animations()
        # Event text should be used, not local clipboard
        assert "completely different" in ta.text
        assert "foo   " not in ta.text


async def test_paste_event_external_text_used_as_is(workspace: Path):
    """Paste event from external source should use event text, not local clipboard."""
    f = await _open_file(workspace, "hello\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Local clipboard has something different
        app.copy_to_clipboard("local text")
        ta.selection = Selection.cursor((0, 0))
        await pilot.wait_for_scheduled_animations()
        # Simulate Paste event from external source
        await ta._on_paste(events.Paste("external text"))
        await pilot.wait_for_scheduled_animations()
        # External text should be used, not local clipboard
        assert "external text" in ta.text
        assert "local text" not in ta.text
        # Line-copy flag should be reset
        from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

        assert MultiCursorTextArea._line_copy_text is None


async def test_paste_event_via_post_message(workspace: Path):
    """Paste event via message queue should work correctly."""
    f = await _open_file(workspace, "foo\nbar\nbaz\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        ta = editor.editor
        # Line-copy 'foo' (no selection)
        ta.cursor_location = (0, 0)
        await pilot.press("ctrl+c")
        await pilot.wait_for_scheduled_animations()
        assert app.clipboard == "foo\n"
        # Move to 'baz' line and paste via post_message (simulates real event path)
        ta.cursor_location = (2, 0)
        ta.post_message(events.Paste("foo\n"))
        await pilot.wait_for_scheduled_animations()
        lines = ta.text.split("\n")
        # Expected: foo, bar, foo, baz, (empty)
        assert lines[2] == "foo"
        assert lines[3] == "baz"
