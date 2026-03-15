"""
Global footer tests (G-01 ~ G-15).

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
    async with app.run_test(size=(240, 40)) as pilot:
        await pilot.pause()
        footer = app.query_one(CodeEditorFooter)
        assert str(sample_py_file) in str(footer.path_view.content)


# ── G-05: tab switch updates footer ───────────────────────────────────────────


async def test_footer_updates_on_tab_switch(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    """G-05: switching tab updates global footer to new active editor's path."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test(size=(240, 40)) as pilot:
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
    async with app.run_test(size=(240, 40)) as pilot:
        await pilot.pause()
        # Create a split and open the json file in the new split
        await app.main_view.action_split_right()
        await pilot.pause()
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


# ── G-11: buttons auto-size to content width ──────────────────────────────────


async def test_footer_buttons_auto_size_to_content(
    workspace: Path, sample_py_file: Path
):
    """G-11: all 4 status buttons use only the space their current label needs.

    Formula (empirically verified): region.width = label_len + 4
      (1 button-internal pad + 1 CSS pad on each side).
    Fails with fixed-column layout (line_ending col=8 even when label='LF'=6).
    """
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        footer = app.query_one(CodeEditorFooter)
        # sample_py_file: LF endings, UTF-8, 4 Spaces, python
        # Formula: region.width = label_len + 4 (pad + internal button pad each side)
        # Exception: last button (no margin-right) may receive 1 less (1fr rounding)
        assert footer.line_ending_button.region.width == 6  # "LF"=2+4
        assert footer.encoding_button.region.width == 9  # "UTF-8"=5+4
        assert footer.indent_button.region.width == 12  # "4 Spaces"=8+4
        assert footer.language_button.region.width >= 9  # "python"=6+3..4


# ── G-12: path column absorbs freed space when button label shrinks ───────────


async def test_footer_path_widens_when_button_label_shortens(
    workspace: Path, sample_py_file: Path
):
    """G-12: switching line_ending CRLF→LF frees 2 cells; path column absorbs them."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        footer = app.query_one(CodeEditorFooter)
        footer.line_ending = "crlf"
        await pilot.pause()
        await pilot.pause()
        path_crlf = footer.path_view.region.width

        footer.line_ending = "lf"
        await pilot.pause()
        await pilot.pause()
        path_lf = footer.path_view.region.width

        # CRLF=8 cells, LF=6 cells → path must be 2 wider when showing LF
        assert path_lf == path_crlf + 2


# ── G-13: path shrinks first on narrow screen ─────────────────────────────────


async def test_footer_path_shrinks_first_on_narrow_screen(
    workspace: Path, sample_py_file: Path
):
    """G-13: on a narrow screen buttons maintain content width; path absorbs surplus."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test(size=(70, 40)) as pilot:
        await pilot.pause()
        footer = app.query_one(CodeEditorFooter)
        assert footer.line_ending_button.region.width == 6  # not shrunk
        assert footer.encoding_button.region.width == 9
        assert footer.indent_button.region.width == 12
        assert footer.language_button.region.width >= 9  # "python"=6+3..4
        assert footer.path_view.region.width >= 1  # path still has some space


# ── G-14: path ellipsis on very long path ─────────────────────────────────────


async def test_footer_path_ellipsis_on_very_long_path(workspace: Path, tmp_path: Path):
    """G-14: when path is too long to display fully, '...' + end of path is shown."""
    long_file = tmp_path / ("a" * 200 + ".py")
    long_file.touch()
    app = make_app(workspace, open_file=long_file)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        footer = app.query_one(CodeEditorFooter)
        content = str(footer.path_view.content)
        assert content.startswith("...")
        assert content.endswith(".py")


# ── G-14b: ellipsis uses dim style ────────────────────────────────────────────


async def test_footer_path_ellipsis_has_dim_style(workspace: Path, tmp_path: Path):
    """G-14b: '...' prefix is a Rich Text object so it carries independent style."""
    from rich.text import Text

    long_file = tmp_path / ("a" * 200 + ".py")
    long_file.touch()
    app = make_app(workspace, open_file=long_file)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        footer = app.query_one(CodeEditorFooter)
        content = footer.path_view.content
        # Must be a Rich Text object (not plain str) to carry style information
        assert isinstance(content, Text)
        # Plain text still starts with "..." and ends with ".py"
        assert content.plain.startswith("...")
        assert content.plain.endswith(".py")


# ── G-15: cursor_btn width is capped ──────────────────────────────────────────


async def test_footer_cursor_btn_capped_width(workspace: Path, multiline_file: Path):
    """G-15: cursor_btn never exceeds max-width=28 even with many cursors."""
    app = make_app(workspace, open_file=multiline_file)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # Add many cursors to force long label
        for row in range(1, 5):
            editor.editor.add_cursor((row, 0))
        await pilot.pause()
        footer = app.query_one(CodeEditorFooter)
        assert footer.cursor_button.region.width <= 28
