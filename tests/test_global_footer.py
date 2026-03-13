"""
Global footer tests (G-01 ~ G-10).

After the global footer refactor, there is exactly one CodeEditorFooter in the
whole app, owned by MainView. It reflects the currently active editor's state.
"""

from pathlib import Path

from tests.conftest import make_app
from textual_code.modals import GotoLineModalScreen
from textual_code.widgets.code_editor import CodeEditorFooter

# ── G-01: exactly one footer in the app ───────────────────────────────────────


async def test_single_footer_in_app(workspace: Path, sample_py_file: Path):
    """G-01: app.query(CodeEditorFooter) returns exactly one widget."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        footers = app.query(CodeEditorFooter)
        assert len(footers) == 1


# ── G-02: footer parent is MainView ───────────────────────────────────────────


async def test_footer_parent_is_main_view(workspace: Path, sample_py_file: Path):
    """G-02: the global footer's parent is MainView."""
    from textual_code.widgets.main_view import MainView

    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        footer = app.query_one(CodeEditorFooter)
        assert isinstance(footer.parent, MainView)


# ── G-03: opening multiple tabs keeps one footer ──────────────────────────────


async def test_one_footer_with_two_open_files(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    """G-03: two open tabs still yield only one CodeEditorFooter."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(sample_json_file)
        await pilot.pause()
        assert len(app.query(CodeEditorFooter)) == 1


# ── G-04: footer shows active editor's path ───────────────────────────────────


async def test_footer_shows_active_editor_path(workspace: Path, sample_py_file: Path):
    """G-04: global footer path label contains the active file's path."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        footer = app.query_one(CodeEditorFooter)
        assert str(sample_py_file) in str(footer.path_view.content)


# ── G-05: tab switch updates footer ───────────────────────────────────────────


async def test_footer_updates_on_tab_switch(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    """G-05: switching tab updates global footer to new active editor's path."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(sample_json_file)
        await pilot.pause()

        # Switch back to the py tab
        py_pane_id = app.main_view.pane_id_from_path(sample_py_file)
        assert py_pane_id is not None
        app.main_view.left_tabbed_content.active = py_pane_id
        await pilot.pause()

        footer = app.query_one(CodeEditorFooter)
        assert str(sample_py_file) in str(footer.path_view.content)


# ── G-06: cursor move updates footer ──────────────────────────────────────────


async def test_footer_updates_on_cursor_move(workspace: Path, multiline_file: Path):
    """G-06: moving cursor updates the footer's cursor button."""
    app = make_app(workspace, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.editor.cursor_location = (3, 5)
        await pilot.pause()
        footer = app.query_one(CodeEditorFooter)
        assert "Ln 4, Col 6" in str(footer.cursor_button.label)


# ── G-07: cursor_btn click opens GotoLineModal ────────────────────────────────


async def test_footer_cursor_btn_click_opens_goto_modal(
    workspace: Path, sample_py_file: Path
):
    """G-07: clicking the global footer's #cursor_btn opens GotoLineModalScreen."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("CodeEditorFooter #cursor_btn")
        await pilot.pause()
        assert isinstance(app.screen, GotoLineModalScreen)


# ── G-08: split switch updates footer ─────────────────────────────────────────


async def test_footer_updates_on_split_switch(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    """G-08: switching focus to the right split shows right editor's path."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Open right split with the json file
        app.main_view._active_split = "right"
        app.main_view._split_visible = True
        app.main_view.right_tabbed_content.display = True
        await app.main_view.action_open_code_editor(sample_json_file)
        await pilot.pause()

        footer = app.query_one(CodeEditorFooter)
        assert str(sample_json_file) in str(footer.path_view.content)


# ── G-09: multi-cursor count shown in footer ──────────────────────────────────


async def test_footer_shows_cursor_count(workspace: Path, multiline_file: Path):
    """G-09: add_cursor() causes the footer to show '[2]'."""
    app = make_app(workspace, open_file=multiline_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.editor.add_cursor((1, 0))
        await pilot.pause()
        footer = app.query_one(CodeEditorFooter)
        assert "[2]" in str(footer.cursor_button.label)


# ── G-10: closing last editor resets footer ───────────────────────────────────


async def test_footer_resets_when_last_editor_closed(
    workspace: Path, sample_py_file: Path
):
    """G-10: after the last editor is closed the footer shows empty path and 'plain'."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+w")
        await pilot.pause()
        footer = app.query_one(CodeEditorFooter)
        assert str(footer.path_view.content) == ""
        assert "plain" in str(footer.language_button.label)
