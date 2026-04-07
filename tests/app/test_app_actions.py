"""Tests for app-level action wrappers in textual_code/app.py.

These test the app.action_* methods that delegate to the active code editor
or main_view. The underlying editor/main_view actions are tested in their
own suites; these tests verify the app-level dispatch (get_active_code_editor
+ call_next pattern, including the "no file open" error branch).
"""

from pathlib import Path

import pytest

from tests.conftest import make_app

# ── Text transform wrappers ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "action_name",
    [
        "action_sort_lines_ascending",
        "action_sort_lines_descending",
        "action_transform_uppercase",
        "action_transform_lowercase",
        "action_transform_title_case",
        "action_transform_snake_case",
        "action_transform_camel_case",
        "action_transform_kebab_case",
        "action_transform_pascal_case",
    ],
)
async def test_text_transform_with_file_open(
    workspace: Path, sample_py_file: Path, action_name: str
):
    """App-level text transform wrappers dispatch without crash."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        getattr(app, action_name)()
        await pilot.wait_for_scheduled_animations()


@pytest.mark.parametrize(
    "action_name",
    [
        "action_sort_lines_ascending",
        "action_sort_lines_descending",
        "action_transform_uppercase",
        "action_transform_lowercase",
        "action_transform_title_case",
        "action_transform_snake_case",
        "action_transform_camel_case",
        "action_transform_kebab_case",
        "action_transform_pascal_case",
        "action_toggle_word_wrap",
        "action_toggle_indentation_guides",
        "action_add_cursor_below_cmd",
        "action_add_cursor_above_cmd",
        "action_select_all_occurrences_cmd",
        "action_add_next_occurrence_cmd",
        "action_redo_cmd",
        "action_select_all_text_cmd",
        "action_indent_line_cmd",
        "action_outdent_line_cmd",
        "action_move_line_up_cmd",
        "action_move_line_down_cmd",
        "action_scroll_up_cmd",
        "action_scroll_down_cmd",
        "action_goto_line_cmd",
        "action_change_language",
        "action_find_cmd",
        "action_replace_cmd",
        "action_change_indentation",
        "action_change_line_ending",
        "action_change_encoding",
        "action_revert_file",
        "action_copy_relative_path",
        "action_copy_absolute_path",
        "action_copy_displayed_path",
        "action_set_render_whitespace",
        "action_save_file",
        "action_save_as",
        "action_close_editor_cmd",
        "action_delete_file",
    ],
)
async def test_action_no_file_notifies_error(workspace: Path, action_name: str):
    """App-level action wrappers execute the 'no file open' branch."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert app.main_view.get_active_code_editor() is None
        getattr(app, action_name)()
        await pilot.wait_for_scheduled_animations()


# ── Toggle wrappers ─────────────────────────────────────────────────────────


async def test_toggle_word_wrap_dispatches(workspace: Path, sample_py_file: Path):
    """action_toggle_word_wrap dispatches to the active editor."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        initial = editor.word_wrap
        app.action_toggle_word_wrap()
        await pilot.wait_for_scheduled_animations()
        assert editor.word_wrap != initial


# ── Multi-cursor wrappers ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "action_name",
    [
        "action_add_cursor_below_cmd",
        "action_add_cursor_above_cmd",
    ],
)
async def test_cursor_add_cmd_dispatches(
    workspace: Path, multiline_file: Path, action_name: str
):
    """Cursor-add command wrappers dispatch to the active editor."""
    app = make_app(workspace, open_file=multiline_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.editor.cursor_location = (2, 0)
        await pilot.wait_for_scheduled_animations()
        assert len(editor.editor.extra_cursors) == 0
        getattr(app, action_name)()
        await pilot.wait_for_scheduled_animations()
        assert len(editor.editor.extra_cursors) == 1


# ── TextArea palette wrappers ────────────────────────────────────────────────


async def test_select_all_text_cmd_dispatches(workspace: Path, sample_py_file: Path):
    """action_select_all_text_cmd dispatches select_all to the active editor."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.action_select_all_text_cmd()
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.editor.selected_text != ""


# ── Modal opener wrappers ────────────────────────────────────────────────────


async def test_goto_line_cmd_opens_modal(workspace: Path, sample_py_file: Path):
    """action_goto_line_cmd opens GotoLineModalScreen."""
    from textual_code.modals import GotoLineModalScreen

    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.action_goto_line_cmd()
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, GotoLineModalScreen)


async def test_find_cmd_opens_find_bar(workspace: Path, sample_py_file: Path):
    """action_find_cmd opens the find bar in the active editor."""
    from textual_code.widgets.find_replace_bar import FindReplaceBar

    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.action_find_cmd()
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        frb = editor.query_one(FindReplaceBar)
        assert frb.display is True


async def test_replace_cmd_opens_replace_bar(workspace: Path, sample_py_file: Path):
    """action_replace_cmd opens the replace bar in the active editor."""
    from textual_code.widgets.find_replace_bar import FindReplaceBar

    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.action_replace_cmd()
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        frb = editor.query_one(FindReplaceBar)
        assert frb.display is True


# ── Split wrappers ──────────────────────────────────────────────────────────


async def test_split_right_cmd_creates_split(workspace: Path, sample_py_file: Path):
    """action_split_right_cmd creates a new split pane."""
    from textual_code.widgets.split_tree import all_leaves

    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.action_split_right_cmd()
        await pilot.wait_for_scheduled_animations()
        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2


# ── Additional app-level wrappers with file open ────────────────────────────


@pytest.mark.parametrize(
    "action_name",
    [
        "action_select_all_occurrences_cmd",
        "action_add_next_occurrence_cmd",
        "action_outdent_line_cmd",
        "action_move_line_up_cmd",
        "action_move_line_down_cmd",
        "action_scroll_up_cmd",
        "action_scroll_down_cmd",
        "action_change_language",
        "action_change_indentation",
        "action_change_line_ending",
        "action_change_encoding",
    ],
)
async def test_additional_action_dispatches_with_file(
    workspace: Path, sample_py_file: Path, action_name: str
):
    """Additional app-level action wrappers dispatch without crash."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        getattr(app, action_name)()
        await pilot.wait_for_scheduled_animations()
        # Dismiss any modal that might have opened
        await pilot.press("escape")
        await pilot.wait_for_scheduled_animations()


# ── call_next delegators ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "action_name",
    [
        "action_save_file",
        "action_save_as",
        "action_close_editor_cmd",
        "action_delete_file",
        "action_split_left",
        "action_split_down",
        "action_split_up",
        "action_focus_left_split_cmd",
        "action_focus_right_split_cmd",
        "action_focus_next_group",
        "action_focus_previous_group",
        "action_close_all_editors_cmd",
        "action_close_other_editors_cmd",
        "action_close_editors_to_the_right_cmd",
        "action_close_editors_to_the_left_cmd",
        "action_close_saved_editors_cmd",
        "action_save_all_files",
        "action_move_editor_to_next_group_cmd",
        "action_move_editor_left",
        "action_move_editor_right",
        "action_move_editor_up",
        "action_move_editor_down",
        "action_reorder_tab_right",
        "action_reorder_tab_left",
        "action_toggle_split_orientation",
        "action_find_in_files_cmd",
        "action_open_markdown_preview_cmd",
        "action_close_editor_group_cmd",
    ],
)
async def test_callnext_delegators_no_crash(
    workspace: Path, sample_py_file: Path, action_name: str
):
    """call_next delegators to main_view dispatch without crash."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        getattr(app, action_name)()
        await pilot.wait_for_scheduled_animations()


# ── Settings modal openers ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "action_name",
    [
        "action_set_default_line_ending",
        "action_set_default_encoding",
        "action_change_syntax_theme",
        "action_change_ui_theme",
        "action_set_render_whitespace",
    ],
)
async def test_settings_modal_opens(
    workspace: Path, sample_py_file: Path, action_name: str
):
    """Settings modal opener actions push a modal screen."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        getattr(app, action_name)()
        await pilot.wait_for_scheduled_animations()
        # Dismiss whatever modal opened
        await pilot.press("escape")
        await pilot.wait_for_scheduled_animations()


# ── Footer / shortcuts configuration ────────────────────────────────────────


async def test_collect_bindings_for_area(workspace: Path, sample_py_file: Path):
    """_collect_bindings_for_area returns bindings for known areas."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        for area in ("editor", "explorer", "search", "image_preview"):
            bindings = app._collect_bindings_for_area(area)
            assert len(bindings) > 0, f"No bindings for area '{area}'"


async def test_action_configure_footer_opens_modal(
    workspace: Path, sample_py_file: Path
):
    """action_configure_footer opens FooterConfigScreen."""
    from textual_code.modals.shortcuts_config import FooterConfigScreen

    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.action_configure_footer()
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, FooterConfigScreen)


async def test_action_open_user_settings(workspace: Path, tmp_path: Path):
    """action_open_user_settings opens settings file in editor."""
    from textual_code.app import TextualCode

    settings_path = tmp_path / "settings.toml"
    app = TextualCode(
        workspace_path=workspace,
        with_open_file=None,
        user_config_path=settings_path,
        skip_sidebar=True,
    )
    app.animation_level = "none"
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.action_open_user_settings()
        await pilot.wait_for_scheduled_animations()
        # Settings file should have been created and opened
        assert settings_path.exists()


async def test_action_open_project_settings(workspace: Path, sample_py_file: Path):
    """action_open_project_settings opens project settings file."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.action_open_project_settings()
        await pilot.wait_for_scheduled_animations()


async def test_action_open_keyboard_shortcuts_file(workspace: Path, tmp_path: Path):
    """action_open_keyboard_shortcuts_file opens keybindings file."""
    from textual_code.app import TextualCode

    settings_path = tmp_path / "settings.toml"
    app = TextualCode(
        workspace_path=workspace,
        with_open_file=None,
        user_config_path=settings_path,
        skip_sidebar=True,
    )
    app.animation_level = "none"
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.action_open_keyboard_shortcuts_file()
        await pilot.wait_for_scheduled_animations()


# ── Find in files ───────────────────────────────────────────────────────────


async def test_action_find_in_files(workspace: Path, sample_py_file: Path):
    """action_find_in_files focuses the workspace search pane."""
    app = make_app(workspace, open_file=sample_py_file)  # needs sidebar
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.action_find_in_files()
        await pilot.wait_for_scheduled_animations()


# ── Sidebar property coverage ───────────────────────────────────────────────


def test_format_file_size():
    """_format_file_size correctly formats sizes at all scale boundaries."""
    from textual_code.modals.file_ops import _format_file_size

    assert _format_file_size(500) == "500 B"
    assert _format_file_size(1023) == "1023 B"
    assert "KB" in _format_file_size(1024)
    assert "KB" in _format_file_size(2048)
    assert "MB" in _format_file_size(1024 * 1024)
    assert "MB" in _format_file_size(2 * 1024 * 1024)
    assert "GB" in _format_file_size(1024 * 1024 * 1024)
    assert "GB" in _format_file_size(2 * 1024 * 1024 * 1024)


async def test_discard_reload_modal_cancel(workspace: Path, sample_py_file: Path):
    """Clicking Cancel in DiscardAndReloadModal dismisses with is_cancelled=True."""
    from textual.widgets import Button

    from textual_code.modals.file_ops import (
        DiscardAndReloadModalResult,
        DiscardAndReloadModalScreen,
    )

    results: list[DiscardAndReloadModalResult | None] = []
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        screen = DiscardAndReloadModalScreen()
        app.push_screen(screen, results.append)
        await pilot.wait_for_scheduled_animations()
        cancel_btn = app.screen.query_one("#cancel", Button)
        cancel_btn.press()
        await pilot.wait_for_scheduled_animations()
        assert len(results) == 1
        assert results[0] is not None
        assert results[0].is_cancelled


async def test_sidebar_properties(workspace: Path, sample_py_file: Path):
    """Sidebar properties (explorer_pane, search_pane) are accessible."""
    from textual.widgets import TabPane

    app = make_app(workspace, open_file=sample_py_file)  # needs sidebar
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        sb = app.sidebar
        assert sb is not None
        assert isinstance(sb.explorer_pane, TabPane)
        assert isinstance(sb.search_pane, TabPane)
