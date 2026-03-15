"""
Cursor button tests (T-01 ~ T-08).

The cursor position in CodeEditorFooter should be a clickable Button (#cursor_btn)
that opens GotoLineModalScreen when pressed.

Groups:
  A: Widget structure
  B: Reactive update
  C: Click → modal open
  D: Full flow
"""

import pytest
from textual.widgets import Button

from tests.conftest import make_app
from textual_code.modals import GotoLineModalScreen
from textual_code.widgets.code_editor import CodeEditorFooter

# ── Group A: Widget structure ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_footer_has_cursor_btn_not_label(workspace, multiline_file):
    """T-01: footer has a #cursor_btn Button (not a Label)."""
    app = make_app(workspace, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        btn = app.query_one(CodeEditorFooter).query_one("#cursor_btn", Button)
        assert btn is not None


@pytest.mark.asyncio
async def test_cursor_btn_initial_label(workspace, multiline_file):
    """T-02: initial cursor_btn label is 'Ln 1, Col 1'."""
    app = make_app(workspace, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        btn = app.query_one(CodeEditorFooter).cursor_button
        assert "Ln 1, Col 1" in str(btn.label)


# ── Group B: Reactive update ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cursor_btn_updates_on_cursor_move(workspace, multiline_file):
    """T-03: moving cursor updates cursor_btn label to 'Ln X, Col Y'."""
    app = make_app(workspace, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.editor.cursor_location = (4, 2)
        await pilot.pause()
        btn = app.query_one(CodeEditorFooter).cursor_button
        assert "Ln 5, Col 3" in str(btn.label)


@pytest.mark.asyncio
async def test_cursor_btn_label_is_one_based(workspace, multiline_file):
    """T-04: cursor_btn label starts at 1-based (row 0 → 'Ln 1, Col 1')."""
    app = make_app(workspace, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.editor.cursor_location = (0, 0)
        await pilot.pause()
        btn = app.query_one(CodeEditorFooter).cursor_button
        assert "Ln 1, Col 1" in str(btn.label)


# ── Group C: Click → modal open ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cursor_btn_click_opens_goto_modal(workspace, multiline_file):
    """T-05: clicking #cursor_btn opens GotoLineModalScreen."""
    app = make_app(workspace, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cursor_btn")
        await pilot.pause()
        assert isinstance(app.screen, GotoLineModalScreen)


@pytest.mark.asyncio
async def test_cursor_btn_click_opens_modal_untitled(workspace):
    """T-06: cursor_btn click opens modal even when editor has no file."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.action_new_editor()
        await pilot.pause()
        await pilot.click("#cursor_btn")
        await pilot.pause()
        assert isinstance(app.screen, GotoLineModalScreen)


# ── Group D: Full flow ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cursor_btn_click_goto_moves_cursor(workspace, multiline_file):
    """T-07: click cursor_btn → enter '3' in modal → cursor moves to line 3."""
    app = make_app(workspace, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#cursor_btn")
        await pilot.pause()
        assert isinstance(app.screen, GotoLineModalScreen)
        input_widget = app.screen.query_one("#location")
        await pilot.click(input_widget)
        await pilot.press("3")
        await pilot.click("#goto")
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        row, _ = editor.editor.cursor_location
        assert row == 2  # 0-based → line 3


@pytest.mark.asyncio
async def test_cursor_btn_click_cancel_no_change(workspace, multiline_file):
    """T-08: click cursor_btn → cancel → cursor position unchanged."""
    app = make_app(workspace, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.editor.cursor_location = (2, 3)
        await pilot.pause()
        original_location = editor.editor.cursor_location

        await pilot.click("CodeEditorFooter #cursor_btn")
        await pilot.pause()
        assert isinstance(app.screen, GotoLineModalScreen)
        await pilot.click("#cancel")
        await pilot.pause()

        assert editor.editor.cursor_location == original_location


# ── Group E: col 10+ truncation regression ───────────────────────────────────


@pytest.mark.asyncio
async def test_cursor_btn_col_10_label_visible(workspace):
    """T-09: cursor_btn label must not be clipped when col >= 10."""
    # Create a file with a line that is at least 10 characters long
    long_line_file = workspace / "long_line.txt"
    long_line_file.write_text("0123456789abcdef\n")
    app = make_app(workspace, open_file=long_line_file)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        editor.editor.cursor_location = (0, 9)  # col 9 → "Ln 1, Col 10"
        await pilot.pause()
        btn = app.query_one(CodeEditorFooter).cursor_button
        assert str(btn.label) == "Ln 1, Col 10"
        # Button must be wide enough to show the full label without clipping.
        # "Ln 1, Col 10" = 12 chars; formula: region.width >= 12 + 4 = 16
        assert btn.region.width >= 16
