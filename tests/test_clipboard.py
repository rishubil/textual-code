"""
Clipboard tests: Ctrl+C (copy) and Ctrl+X (cut).

Behaviour mirrors VS Code:
- With selection: copies/cuts the selected text.
- Without selection: copies/cuts the current line (including newline).
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
    app = make_app(workspace, open_file=f)
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
    app = make_app(workspace, open_file=f)
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
    app = make_app(workspace, open_file=f)
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
    app = make_app(workspace, open_file=f)
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
    app = make_app(workspace, open_file=f)
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


async def test_ctrl_c_with_multiple_cursors_clears_extra_cursors(workspace: Path):
    """Ctrl+C while multi-cursor is active clears extra cursors."""
    f = await _open_file(workspace, "line1\nline2\nline3\n")
    app = make_app(workspace, open_file=f)
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
        # Extra cursors are cleared (multi-cursor copy is not supported)
        assert ta.extra_cursors == []
