"""
Snapshot tests.

Uses the snap_compare fixture from pytest-textual-snapshot to capture
the visual state of the app and detect regressions.

Snapshot tests use a fixed workspace path (/tmp/tc_snapshot_ws/<test_name>)
so the file path shown in the footer is stable across test runs.

Generate initial snapshots:
    uv run pytest tests/test_snapshots.py --snapshot-update

Compare on subsequent runs:
    uv run pytest tests/test_snapshots.py
"""

from pathlib import Path

import pytest
from textual.widgets import Input

from tests.conftest import init_git_repo, make_app, make_png, requires_git
from textual_code.modals import RebindKeyScreen
from textual_code.widgets.image_preview import ImagePreviewPane
from textual_code.widgets.split_tree import all_leaves
from textual_code.widgets.workspace_search import WorkspaceSearchPane

pytestmark = pytest.mark.serial

TERMINAL_SIZE = (120, 40)


def _focus_editor(app):
    """Return a run_before function that waits for the editor to settle and focus."""

    async def run_before(pilot):
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        if editor is not None:
            editor.action_focus()
        await pilot.pause()

    return run_before


# ── Basic app state ───────────────────────────────────────────────────────────


def test_snapshot_empty_app(snap_compare, snapshot_workspace: Path):
    """Empty app with no open files."""
    app = make_app(snapshot_workspace)
    assert snap_compare(app, terminal_size=TERMINAL_SIZE)


def test_snapshot_app_with_file(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """App with a Python file open in a tab."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)
    assert snap_compare(app, run_before=_focus_editor(app), terminal_size=TERMINAL_SIZE)


def test_snapshot_multiple_tabs(
    snap_compare,
    snapshot_workspace: Path,
    snapshot_py_file: Path,
    snapshot_json_file: Path,
):
    """App with multiple file tabs open."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def open_second_file(pilot):
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=snapshot_json_file)
        editor = app.main_view.get_active_code_editor()
        if editor is not None:
            editor.action_focus()
        await pilot.pause()

    assert snap_compare(app, run_before=open_second_file, terminal_size=TERMINAL_SIZE)


# ── New editor tab ────────────────────────────────────────────────────────────


def test_snapshot_new_editor_tab(snap_compare, snapshot_workspace: Path):
    """App after pressing Ctrl+N to open a new empty editor tab."""
    app = make_app(snapshot_workspace)

    async def open_new_editor(pilot):
        await pilot.press("ctrl+n")
        editor = app.main_view.get_active_code_editor()
        if editor is not None:
            editor.action_focus()
        await pilot.pause()

    assert snap_compare(app, run_before=open_new_editor, terminal_size=TERMINAL_SIZE)


def test_snapshot_unsaved_marker(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """Tab title shows unsaved marker (*) after text is modified."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def modify_text(pilot):
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_focus()
        # Setting editor.text directly is intentional here: we are testing the
        # unsaved-marker (*) in the tab title, not the editor's visual content.
        # Direct assignment is stable because it does not move the TextArea cursor.
        editor.text = "modified content\n"
        # Reactive chain: watch_text → update_title → watch_title →
        # TitleChanged message → on_code_editor_title_changed → tab label update.
        # Each reactive watcher is deferred via call_later, so the chain spans
        # several event-loop cycles.  A real-time pause lets everything settle.
        await pilot.pause(0.2)

    assert snap_compare(app, run_before=modify_text, terminal_size=TERMINAL_SIZE)


# ── Modal snapshots ────────────────────────────────────────────────────────────


def test_snapshot_save_as_modal(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """Save As modal dialog open."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def open_save_as(pilot):
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_focus()
        await pilot.pause()
        editor.action_save_as()
        await pilot.pause()

    assert snap_compare(app, run_before=open_save_as, terminal_size=TERMINAL_SIZE)


def test_snapshot_unsaved_change_modal(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """Unsaved changes modal shown when closing a modified file."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def modify_and_close(pilot):
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "modified content\n"
        await pilot.pause()
        editor.action_close()
        await pilot.pause()

    assert snap_compare(app, run_before=modify_and_close, terminal_size=TERMINAL_SIZE)


def test_snapshot_unsaved_quit_modal(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """Unsaved changes modal shown when quitting with modified file."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def modify_and_quit(pilot):
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "modified content\n"
        await pilot.pause()
        await app.action_quit()
        await pilot.pause()

    assert snap_compare(app, run_before=modify_and_quit, terminal_size=TERMINAL_SIZE)


def test_snapshot_delete_modal(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """Delete file confirmation modal open."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def open_delete(pilot):
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_focus()
        await pilot.pause()
        editor.action_delete()
        await pilot.pause()

    assert snap_compare(app, run_before=open_delete, terminal_size=TERMINAL_SIZE)


# ── Split view ────────────────────────────────────────────────────────────────


def test_snapshot_split_view_open(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """App with the right split panel open showing the same file."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def open_split(pilot):
        await pilot.pause()
        await app.main_view.action_split_right()
        editor = app.main_view._get_active_code_editor_in_split("right")
        if editor is not None:
            editor.action_focus()
        await pilot.pause()

    assert snap_compare(app, run_before=open_split, terminal_size=TERMINAL_SIZE)


def test_snapshot_split_left_view_open(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """App with the left split panel open showing the same file."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def open_split(pilot):
        await pilot.pause()
        await app.main_view.action_split_left()
        await pilot.pause()

    assert snap_compare(app, run_before=open_split, terminal_size=TERMINAL_SIZE)


# ── Markdown preview ──────────────────────────────────────────────────────────


def test_snapshot_markdown_preview_open(snap_compare, snapshot_workspace: Path):
    """App with a markdown preview tab open showing a .md file."""
    md_file = snapshot_workspace / "notes.md"
    md_file.write_text("# Hello\n\nThis is a **Markdown** preview.\n")
    app = make_app(snapshot_workspace, open_file=md_file)

    async def open_preview(pilot):
        await pilot.pause()
        await app.main_view.action_open_markdown_preview_tab()
        await pilot.pause()

    assert snap_compare(app, run_before=open_preview, terminal_size=TERMINAL_SIZE)


def test_snapshot_readme_preview(snap_compare, snapshot_workspace: Path):
    """README showcase: editor left, markdown preview right, git status off."""
    # Workspace files for sidebar variety
    (snapshot_workspace / "src").mkdir()
    (snapshot_workspace / "src" / "app.py").write_text("class App:\n    pass\n")
    (snapshot_workspace / "tests").mkdir()
    (snapshot_workspace / "tests" / "test_app.py").write_text("def test_app(): pass\n")
    (snapshot_workspace / "docs").mkdir()
    (snapshot_workspace / "docs" / "guide.md").write_text("# Guide\n")
    (snapshot_workspace / "pyproject.toml").write_text(
        '[project]\nname = "my-project"\nversion = "0.1.0"\n'
    )
    (snapshot_workspace / ".gitignore").write_text("__pycache__/\n*.pyc\n")
    readme = snapshot_workspace / "README.md"
    project_readme = Path(__file__).resolve().parent.parent / "README.md"
    readme.write_text(project_readme.read_text())

    # Disable git status highlighting
    config = snapshot_workspace / "settings.toml"
    config.write_text("[editor]\nshow_git_status = false\n")

    app = make_app(snapshot_workspace, open_file=readme, user_config_path=config)

    async def setup_preview_split(pilot):
        await pilot.pause()
        # Open markdown preview (tab in left/only leaf)
        await app.main_view.action_open_markdown_preview_tab()
        await pilot.pause()
        # Move preview to a new right split
        preview_pane_id = app.main_view._preview_pane_ids[readme]
        new_leaf = await app.main_view._create_empty_split("horizontal", "after")
        await app.main_view._move_pane_to_leaf(preview_pane_id, new_leaf)
        await pilot.pause()
        # Focus back to left editor
        left_leaf = all_leaves(app.main_view._split_root)[0]
        app.main_view._set_active_leaf(left_leaf)
        await pilot.pause()

    assert snap_compare(
        app, run_before=setup_preview_split, terminal_size=TERMINAL_SIZE
    )


def test_snapshot_overwrite_confirm_modal(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """OverwriteConfirmModalScreen shown when saving over an externally changed file."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def trigger_overwrite_modal(pilot):
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_focus()
        editor.text = "editor changes\n"
        await pilot.pause()
        # Simulate external change by shifting mtime tracker
        editor._file_mtime -= 1.0  # ty: ignore[unsupported-operator]
        editor.action_save()
        await pilot.pause()

    assert snap_compare(
        app, run_before=trigger_overwrite_modal, terminal_size=TERMINAL_SIZE
    )


def test_snapshot_discard_and_reload_modal(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """DiscardAndReloadModalScreen shown when reloading with unsaved changes."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def trigger_reload_modal(pilot):
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_focus()
        editor.text = "unsaved changes\n"
        await pilot.pause()
        editor.action_reload_file()
        await pilot.pause()

    assert snap_compare(
        app, run_before=trigger_reload_modal, terminal_size=TERMINAL_SIZE
    )


def test_snapshot_show_shortcuts_screen(snap_compare, snapshot_workspace: Path):
    """ShowShortcutsScreen (F1) is centered on screen."""
    app = make_app(snapshot_workspace)

    async def open_shortcuts(pilot):
        await pilot.pause()
        app.action_show_shortcuts()
        await pilot.pause()

    assert snap_compare(app, run_before=open_shortcuts, terminal_size=TERMINAL_SIZE)


def test_snapshot_shortcut_settings_screen(snap_compare, snapshot_workspace: Path):
    """ShortcutSettingsScreen modal with palette toggle."""
    from textual_code.modals import ShortcutSettingsScreen

    app = make_app(snapshot_workspace)

    async def open_settings(pilot):
        await pilot.pause()
        app.push_screen(
            ShortcutSettingsScreen(
                action_name="save",
                description="Save",
                current_key="Ctrl+S",
                palette_visible=True,
            )
        )
        await pilot.pause()

    assert snap_compare(app, run_before=open_settings, terminal_size=TERMINAL_SIZE)


def test_snapshot_footer_config_screen(snap_compare, snapshot_workspace: Path):
    """FooterConfigScreen modal with reorderable list and area selector."""
    from textual_code.config import FooterOrders
    from textual_code.modals import FooterConfigScreen

    app = make_app(snapshot_workspace)

    async def open_footer_config(pilot):
        await pilot.pause()
        editor_actions = [
            ("save", "Save", "Ctrl+S", True),
            ("find", "Find", "Ctrl+F", True),
            ("replace", "Replace", "Ctrl+H", True),
            ("goto_line", "Goto line", "Ctrl+G", True),
            ("close", "Close tab", "Ctrl+W", True),
            ("new_editor", "New file", "Ctrl+N", True),
            ("toggle_sidebar", "Toggle sidebar", "Ctrl+B", True),
        ]
        explorer_actions = [
            ("create_file", "Create file", "Ctrl+N", True),
            ("create_directory", "Create directory", "Ctrl+D", True),
            ("new_editor", "New file", "Ctrl+N", True),
            ("toggle_sidebar", "Toggle sidebar", "Ctrl+B", True),
        ]
        all_area_actions = {
            "editor": editor_actions,
            "explorer": explorer_actions,
        }
        orders = FooterOrders(areas={"editor": ["save", "find", "replace"]})
        app.push_screen(
            FooterConfigScreen(all_area_actions, orders, initial_area="editor")
        )
        await pilot.pause()

    assert snap_compare(app, run_before=open_footer_config, terminal_size=TERMINAL_SIZE)


def test_snapshot_tab_reorder_active_indicator(
    snap_compare,
    snapshot_workspace: Path,
    snapshot_py_file: Path,
    snapshot_json_file: Path,
):
    """After tab drag-reorder, the active indicator sits on the correct tab."""
    from textual.widgets._tabbed_content import ContentTab, ContentTabs

    from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent

    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def reorder_tabs(pilot):
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=snapshot_json_file)
        await pilot.pause()

        from textual_code.widgets.split_tree import all_leaves

        leaves = all_leaves(app.main_view._split_root)
        dtc = app.main_view.query_one(f"#{leaves[0].leaf_id}", DraggableTabbedContent)
        content_tabs = dtc.get_child_by_type(ContentTabs)
        tabs = list(content_tabs.query(ContentTab))
        # Move second tab (json) before first tab (py)
        b_id = ContentTab.sans_prefix(tabs[1].id)
        a_id = ContentTab.sans_prefix(tabs[0].id)
        dtc.reorder_tab(b_id, a_id, before=True)
        assert dtc.active == b_id  # active tab must remain data.json after reorder
        await pilot.pause()
        await pilot.pause()

        editor = app.main_view.get_active_code_editor()
        if editor is not None:
            editor.action_focus()
        await pilot.pause()

    assert snap_compare(app, run_before=reorder_tabs, terminal_size=TERMINAL_SIZE)


def test_snapshot_tab_reorder_right_indicator(
    snap_compare,
    snapshot_workspace: Path,
    snapshot_py_file: Path,
    snapshot_json_file: Path,
):
    """After action_reorder_tab_right, the active indicator sits on the moved tab."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def reorder_right(pilot):
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=snapshot_json_file)
        await pilot.pause()

        tc = app.main_view.tabbed_content
        order = tc.get_ordered_pane_ids()  # ty: ignore[unresolved-attribute]
        # Activate first tab (hello.py)
        tc.active = order[0]
        await pilot.pause()

        # Move it right (swap with data.json)
        app.main_view.action_reorder_tab_right()
        await pilot.pause()
        await pilot.pause()

        editor = app.main_view.get_active_code_editor()
        if editor is not None:
            editor.action_focus()
        await pilot.pause()

    assert snap_compare(app, run_before=reorder_right, terminal_size=TERMINAL_SIZE)


# ── Custom language highlighting ───────────────────────────────────────────────


def test_snapshot_dockerfile_highlighting(snap_compare, snapshot_workspace: Path):
    """Dockerfile opened in editor shows syntax highlighting."""
    dockerfile = snapshot_workspace / "Dockerfile"
    dockerfile.write_text(
        "FROM ubuntu:22.04\nRUN apt-get update && apt-get install -y python3\n"
        'ENV APP_HOME=/app\nWORKDIR $APP_HOME\nCOPY . .\nCMD ["python3", "app.py"]\n'
    )
    app = make_app(snapshot_workspace, open_file=dockerfile)
    assert snap_compare(app, run_before=_focus_editor(app), terminal_size=TERMINAL_SIZE)


# ── Footer modal no-save-level ─────────────────────────────────────────────────


def test_snapshot_footer_indent_modal_no_save_level(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """ChangeIndentModalScreen from footer (no save_level row)."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def open_modal(pilot):
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_change_indent()
        await pilot.pause()

    assert snap_compare(app, run_before=open_modal, terminal_size=TERMINAL_SIZE)


def test_snapshot_footer_line_ending_modal_no_save_level(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """ChangeLineEndingModalScreen from footer (no save_level row)."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def open_modal(pilot):
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_change_line_ending()
        await pilot.pause()

    assert snap_compare(app, run_before=open_modal, terminal_size=TERMINAL_SIZE)


def test_snapshot_footer_encoding_modal_no_save_level(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """ChangeEncodingModalScreen from footer (no save_level row)."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def open_modal(pilot):
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_change_encoding()
        await pilot.pause()

    assert snap_compare(app, run_before=open_modal, terminal_size=TERMINAL_SIZE)


# ── Helpers for modal tests ────────────────────────────────────────────────────


def _open_editor_modal(app, action_fn):
    """Return run_before that focuses the editor then calls action_fn."""

    async def run_before(pilot):
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None, f"No active editor in {app}"
        editor.action_focus()
        await pilot.pause()
        action_fn(editor)
        await pilot.pause()

    return run_before


def _open_app_modal(app, action_fn):
    """Return run_before that calls an app-level action_fn."""

    async def run_before(pilot):
        await pilot.pause()
        action_fn(app)
        await pilot.pause()

    return run_before


# ── Additional modal snapshots ─────────────────────────────────────────────────


def test_snapshot_goto_line_modal(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """GotoLineModalScreen open via editor action_goto_line()."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)
    assert snap_compare(
        app,
        run_before=_open_editor_modal(app, lambda e: e.action_goto_line()),
        terminal_size=TERMINAL_SIZE,
    )


def test_snapshot_change_language_modal(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """ChangeLanguageModalScreen open via editor action_change_language()."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)
    assert snap_compare(
        app,
        run_before=_open_editor_modal(app, lambda e: e.action_change_language()),
        terminal_size=TERMINAL_SIZE,
    )


def test_snapshot_change_syntax_theme_modal(snap_compare, snapshot_workspace: Path):
    """ChangeSyntaxThemeModalScreen (with save_level row) via app action."""
    app = make_app(snapshot_workspace)
    assert snap_compare(
        app,
        run_before=_open_app_modal(app, lambda a: a.action_set_syntax_theme()),
        terminal_size=TERMINAL_SIZE,
    )


def test_snapshot_change_word_wrap_modal(snap_compare, snapshot_workspace: Path):
    """ChangeWordWrapModalScreen (with save_level row) via app action."""
    app = make_app(snapshot_workspace)
    assert snap_compare(
        app,
        run_before=_open_app_modal(app, lambda a: a.action_set_default_word_wrap()),
        terminal_size=TERMINAL_SIZE,
    )


def test_snapshot_change_ui_theme_modal(snap_compare, snapshot_workspace: Path):
    """ChangeUIThemeModalScreen (with save_level row) via app action."""
    app = make_app(snapshot_workspace)
    assert snap_compare(
        app,
        run_before=_open_app_modal(app, lambda a: a.action_set_ui_theme()),
        terminal_size=TERMINAL_SIZE,
    )


def test_snapshot_sidebar_resize_modal(snap_compare, snapshot_workspace: Path):
    """SidebarResizeModalScreen open via app action_resize_sidebar_cmd()."""
    app = make_app(snapshot_workspace)
    assert snap_compare(
        app,
        run_before=_open_app_modal(app, lambda a: a.action_resize_sidebar_cmd()),
        terminal_size=TERMINAL_SIZE,
    )


def test_snapshot_split_resize_modal(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """SplitResizeModalScreen open after split_right then action_resize_split_cmd()."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def run_before(pilot):
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        app.action_resize_split_cmd()
        await pilot.pause()

    assert snap_compare(app, run_before=run_before, terminal_size=TERMINAL_SIZE)


def test_snapshot_rebind_key_screen(snap_compare, snapshot_workspace: Path):
    """RebindKeyScreen shown for the 'quit' action."""
    app = make_app(snapshot_workspace)

    async def run_before(pilot):
        await pilot.pause()
        app.push_screen(RebindKeyScreen("quit", "Quit", "q"))
        await pilot.pause()

    assert snap_compare(app, run_before=run_before, terminal_size=TERMINAL_SIZE)


def test_snapshot_indent_modal_with_save_level(snap_compare, snapshot_workspace: Path):
    """ChangeIndentModalScreen with save_level row (user/project setting visible)."""
    app = make_app(snapshot_workspace)
    assert snap_compare(
        app,
        run_before=_open_app_modal(app, lambda a: a.action_set_default_indentation()),
        terminal_size=TERMINAL_SIZE,
    )


def test_snapshot_line_ending_modal_with_save_level(
    snap_compare, snapshot_workspace: Path
):
    """ChangeLineEndingModalScreen with save_level row (user/project visible)."""
    app = make_app(snapshot_workspace)
    assert snap_compare(
        app,
        run_before=_open_app_modal(app, lambda a: a.action_set_default_line_ending()),
        terminal_size=TERMINAL_SIZE,
    )


def test_snapshot_encoding_modal_with_save_level(
    snap_compare, snapshot_workspace: Path
):
    """ChangeEncodingModalScreen with save_level row (user/project setting visible)."""
    app = make_app(snapshot_workspace)
    assert snap_compare(
        app,
        run_before=_open_app_modal(app, lambda a: a.action_set_default_encoding()),
        terminal_size=TERMINAL_SIZE,
    )


# ── Additional UI panel snapshots ─────────────────────────────────────────────


def test_snapshot_find_bar_open(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """FindReplaceBar shown in find mode via editor action_find()."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)
    assert snap_compare(
        app,
        run_before=_open_editor_modal(app, lambda e: e.action_find()),
        terminal_size=TERMINAL_SIZE,
    )


def test_snapshot_replace_bar_open(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """FindReplaceBar shown in replace mode via editor action_replace()."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)
    assert snap_compare(
        app,
        run_before=_open_editor_modal(app, lambda e: e.action_replace()),
        terminal_size=TERMINAL_SIZE,
    )


def test_snapshot_sidebar_search_tab(snap_compare, snapshot_workspace: Path):
    """WorkspaceSearchPane shown in empty state after switching to Search tab."""
    app = make_app(snapshot_workspace)

    async def run_before(pilot):
        await pilot.pause()
        app.main_view.action_find_in_workspace()
        await pilot.pause()

    assert snap_compare(app, run_before=run_before, terminal_size=TERMINAL_SIZE)


def test_snapshot_workspace_search_results(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """WorkspaceSearchPane showing results after searching for 'print'."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def run_before(pilot):
        await pilot.pause()
        app.main_view.action_find_in_workspace()
        await pilot.pause()
        pane = app.query_one(WorkspaceSearchPane)
        pane.query_one("#ws-query", Input).value = "print"
        pane._run_search()
        # Give threaded search worker time to finish and post results
        for _ in range(5):
            await pilot.pause()

    assert snap_compare(app, run_before=run_before, terminal_size=TERMINAL_SIZE)


def test_snapshot_multi_cursor(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """MultiCursorTextArea showing multiple cursors after Ctrl+Alt+Down twice."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def run_before(pilot):
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_focus()
        await pilot.pause()
        await pilot.press("ctrl+alt+down")
        await pilot.pause()
        await pilot.press("ctrl+alt+down")
        await pilot.pause()

    assert snap_compare(app, run_before=run_before, terminal_size=TERMINAL_SIZE)


def test_snapshot_tab_dragging_highlight(
    snap_compare,
    snapshot_workspace: Path,
    snapshot_py_file: Path,
    snapshot_json_file: Path,
):
    """Dragged tab shows distinct highlight (accent background, inverted text, bold)."""
    from textual.widgets._tabbed_content import ContentTab, ContentTabs

    from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent
    from textual_code.widgets.split_tree import all_leaves

    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def add_dragging_class(pilot):
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=snapshot_json_file)
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        dtc = app.main_view.query_one(f"#{leaves[0].leaf_id}", DraggableTabbedContent)
        content_tabs = dtc.get_child_by_type(ContentTabs)
        tabs = list(content_tabs.query(ContentTab))
        # Manually add -dragging class to the first tab
        tabs[0].add_class("-dragging")
        await pilot.pause()

    assert snap_compare(app, run_before=add_dragging_class, terminal_size=TERMINAL_SIZE)


def test_snapshot_drop_target_highlight(
    snap_compare,
    snapshot_workspace: Path,
    snapshot_py_file: Path,
    snapshot_json_file: Path,
):
    """Target split pane shows accent border when another tab is dragged over it."""
    from textual.widgets._tabbed_content import ContentTab, ContentTabs

    from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent
    from textual_code.widgets.split_tree import all_leaves

    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def setup_drop_target(pilot):
        from textual_code.widgets.draggable_tabs_content import DropTargetScreen

        await pilot.pause()
        await app.main_view.action_open_code_editor(path=snapshot_json_file)
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        # Open a different file in the right split so it has visible content
        leaves = all_leaves(app.main_view._split_root)
        right_leaf = leaves[-1]
        app.main_view._active_leaf_id = right_leaf.leaf_id
        await app.main_view.action_open_code_editor(path=snapshot_py_file)
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        left_dtc = app.main_view.query_one(
            f"#{leaves[0].leaf_id}", DraggableTabbedContent
        )
        right_dtc = app.main_view.query_one(
            f"#{leaves[1].leaf_id}", DraggableTabbedContent
        )

        # Ensure deterministic active tab in both panes and let
        # the underline indicator settle before taking the snapshot
        right_pane_ids = right_dtc.get_ordered_pane_ids()
        if right_pane_ids:
            right_dtc.active = right_pane_ids[0]
        left_pane_ids = left_dtc.get_ordered_pane_ids()
        if left_pane_ids:
            left_dtc.active = left_pane_ids[0]
        for _ in range(5):
            await pilot.pause()

        # Push overlay screen and set references on all DTCs
        dtcs = list(app.main_view.query(DraggableTabbedContent))
        overlay = DropTargetScreen([dtc.id for dtc in dtcs])
        for dtc in dtcs:
            dtc._overlay_screen = overlay
        app.push_screen(overlay)
        await pilot.pause()

        # Simulate drag state: -dragging on source tab, overlay on target pane
        content_tabs = left_dtc.get_child_by_type(ContentTabs)
        tabs = list(content_tabs.query(ContentTab))
        tabs[0].add_class("-dragging")
        right_dtc.show_drop_overlay()
        await pilot.pause()

    assert snap_compare(app, run_before=setup_drop_target, terminal_size=TERMINAL_SIZE)


def test_snapshot_drop_target_edge_highlight(
    snap_compare,
    snapshot_workspace: Path,
    snapshot_py_file: Path,
    snapshot_json_file: Path,
):
    """Edge zone shows semi-transparent accent overlay on the right side."""
    from textual.widgets._tabbed_content import ContentTab, ContentTabs

    from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent
    from textual_code.widgets.split_tree import all_leaves

    app = make_app(snapshot_workspace, open_file=snapshot_py_file)

    async def setup_edge_overlay(pilot):
        from textual_code.widgets.draggable_tabs_content import DropTargetScreen

        await pilot.pause()
        await app.main_view.action_open_code_editor(path=snapshot_json_file)
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        # Open a different file in the right split so it has visible content
        leaves = all_leaves(app.main_view._split_root)
        right_leaf = leaves[-1]
        app.main_view._active_leaf_id = right_leaf.leaf_id
        await app.main_view.action_open_code_editor(path=snapshot_py_file)
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        left_dtc = app.main_view.query_one(
            f"#{leaves[0].leaf_id}", DraggableTabbedContent
        )

        # Ensure deterministic active tab and let underline settle
        left_pane_ids = left_dtc.get_ordered_pane_ids()
        if left_pane_ids:
            left_dtc.active = left_pane_ids[0]
        for _ in range(5):
            await pilot.pause()

        # Push overlay screen and set references on all DTCs
        dtcs = list(app.main_view.query(DraggableTabbedContent))
        overlay = DropTargetScreen([dtc.id for dtc in dtcs])
        for dtc in dtcs:
            dtc._overlay_screen = overlay
        app.push_screen(overlay)
        for _ in range(5):
            await pilot.pause()

        # Simulate drag state: -dragging on source tab, edge overlay on source pane
        content_tabs = left_dtc.get_child_by_type(ContentTabs)
        tabs = list(content_tabs.query(ContentTab))
        tabs[0].add_class("-dragging")
        left_dtc.show_edge_overlay("right")
        for _ in range(5):
            await pilot.pause()

    assert snap_compare(app, run_before=setup_edge_overlay, terminal_size=TERMINAL_SIZE)


def test_snapshot_footer_path_truncation(snap_compare, snapshot_workspace: Path):
    """Footer path shows dim ellipsis when path is truncated."""
    long_file = snapshot_workspace / ("a" * 150 + ".py")
    long_file.touch()
    app = make_app(snapshot_workspace, open_file=long_file)
    assert snap_compare(app, terminal_size=TERMINAL_SIZE)


def test_snapshot_narrow_sidebar_icon_only(snap_compare, snapshot_workspace: Path):
    """Sidebar tabs and search buttons show icon-only labels when narrow."""
    app = make_app(snapshot_workspace)

    async def run_before(pilot):
        await pilot.pause()
        app.main_view.action_find_in_workspace()
        await pilot.pause()
        assert app.sidebar is not None
        app.sidebar.styles.width = 12
        await pilot.pause()

    assert snap_compare(app, run_before=run_before, terminal_size=TERMINAL_SIZE)


# ── Hidden files toggle ──────────────────────────────────────────────────────


def test_snapshot_explorer_hidden_files_visible(snap_compare, snapshot_workspace: Path):
    """Explorer showing hidden files (default behavior)."""
    (snapshot_workspace / "hello.py").write_text("print('hello')\n")
    (snapshot_workspace / ".hidden_file").write_text("secret\n")
    (snapshot_workspace / ".hidden_dir").mkdir()
    config = snapshot_workspace / "settings.toml"
    app = make_app(snapshot_workspace, user_config_path=config)

    assert snap_compare(app, terminal_size=TERMINAL_SIZE)


# ── Dim hidden files ─────────────────────────────────────────────────────────


def test_snapshot_explorer_dim_hidden_files(snap_compare, snapshot_workspace: Path):
    """Explorer dims dotfiles and dotfolders when dim_hidden_files is enabled."""
    (snapshot_workspace / "hello.py").write_text("print('hello')\n")
    (snapshot_workspace / ".hidden_file").write_text("secret\n")
    (snapshot_workspace / ".hidden_dir").mkdir()
    config = snapshot_workspace / "settings.toml"
    config.write_text("[editor]\ndim_hidden_files = true\n")
    app = make_app(snapshot_workspace, user_config_path=config)

    assert snap_compare(app, terminal_size=TERMINAL_SIZE)


@requires_git
def test_snapshot_explorer_git_status(snap_compare, snapshot_workspace: Path):
    """Explorer shows git status colors for modified and untracked files."""
    init_git_repo(snapshot_workspace)
    # Create modifications: modify one, add untracked
    (snapshot_workspace / "committed.py").write_text("# modified\n")
    (snapshot_workspace / "untracked.py").write_text("# untracked\n")
    config = snapshot_workspace / "settings.toml"
    app = make_app(snapshot_workspace, user_config_path=config)

    assert snap_compare(app, terminal_size=TERMINAL_SIZE)


def test_snapshot_sidebar_custom_width(snap_compare, snapshot_workspace: Path):
    """Sidebar rendered at configured width of 50 cells."""
    (snapshot_workspace / "hello.py").write_text("print('hello')\n")
    config = snapshot_workspace / "settings.toml"
    config.write_text("[editor]\nsidebar_width = 50\n")
    app = make_app(snapshot_workspace, user_config_path=config)

    assert snap_compare(app, terminal_size=TERMINAL_SIZE)


# ── Explorer create file pre-fill ─────────────────────────────────────────────


def test_snapshot_explorer_create_file_prefilled(
    snap_compare, snapshot_workspace: Path
):
    """CommandPalette shows pre-filled path when creating file from explorer."""
    subdir = snapshot_workspace / "src"
    subdir.mkdir()
    (subdir / "main.py").write_text("# main\n")
    app = make_app(snapshot_workspace)

    async def run_before(pilot):
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        tree = explorer.directory_tree
        # Select the "src" directory node
        for node in tree.root.children:
            if node.data and node.data.path == subdir:
                tree.move_cursor(node)
                break
        await pilot.pause()
        tree.focus()
        await pilot.pause()
        await pilot.press("ctrl+n")
        await pilot.pause()

    assert snap_compare(app, run_before=run_before, terminal_size=TERMINAL_SIZE)


def test_snapshot_rename_modal(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """RenameModalScreen open via app._handle_rename_path()."""
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)
    assert snap_compare(
        app,
        run_before=_open_app_modal(
            app, lambda a: a._handle_rename_path(snapshot_py_file)
        ),
        terminal_size=TERMINAL_SIZE,
    )


def test_snapshot_move_modal(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """Move directory picker CommandPalette via app._handle_move_path()."""
    # Create subdirectories for visual richness in the snapshot
    (snapshot_workspace / "src").mkdir(exist_ok=True)
    (snapshot_workspace / "lib").mkdir(exist_ok=True)
    (snapshot_workspace / "tests").mkdir(exist_ok=True)
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)
    assert snap_compare(
        app,
        run_before=_open_app_modal(
            app, lambda a: a._handle_move_path(snapshot_py_file)
        ),
        terminal_size=TERMINAL_SIZE,
    )


def test_snapshot_file_search_modal(
    snap_compare, snapshot_workspace: Path, snapshot_py_file: Path
):
    """File search PathSearchModal via action_open_file_with_command_palette()."""
    # Create files for visual richness
    (snapshot_workspace / "main.py").write_text("# main\n")
    (snapshot_workspace / "utils.py").write_text("# utils\n")
    (snapshot_workspace / "src").mkdir(exist_ok=True)
    (snapshot_workspace / "src" / "app.py").write_text("# app\n")
    app = make_app(snapshot_workspace, open_file=snapshot_py_file)
    assert snap_compare(
        app,
        run_before=_open_app_modal(
            app, lambda a: a.action_open_file_with_command_palette()
        ),
        terminal_size=TERMINAL_SIZE,
    )


# ── Image preview ─────────────────────────────────────────────────────────────


def test_snapshot_image_preview(snap_compare, snapshot_workspace: Path):
    """Image preview pane showing a small PNG image."""
    img = make_png(snapshot_workspace / "test.png")
    app = make_app(snapshot_workspace, open_file=img)

    async def run_before(pilot):
        # Give image worker time to load and render
        for _ in range(5):
            await pilot.pause()
        preview = app.query(ImagePreviewPane)
        if preview:
            preview.first().focus()
        await pilot.pause()

    assert snap_compare(app, run_before=run_before, terminal_size=TERMINAL_SIZE)


# ── Git diff gutter indicators ───────────────────────────────────────────────


@requires_git
def test_snapshot_git_diff_gutter(snap_compare, snapshot_workspace: Path):
    """Editor gutter shows green/yellow/red indicators for git changes."""
    init_git_repo(snapshot_workspace)
    committed = snapshot_workspace / "committed.py"
    # Create a multi-line committed file with modifications
    committed.write_text("# modified line\nprint('hello')\nnew_line = True\n")
    app = make_app(snapshot_workspace, open_file=committed)

    async def run_before(pilot):
        # Wait for mount + background git diff worker
        for _ in range(5):
            await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        if editor is not None:
            editor.action_focus()
        await pilot.pause()

    assert snap_compare(app, run_before=run_before, terminal_size=TERMINAL_SIZE)


def test_snapshot_indentation_guides(snap_compare, snapshot_workspace: Path):
    """Editor shows vertical indentation guides in leading whitespace."""
    f = snapshot_workspace / "indented.py"
    f.write_text(
        "def hello():\n"
        "    if True:\n"
        "        print('hello')\n"
        "        if False:\n"
        "            pass\n"
        "    return\n"
    )
    app = make_app(snapshot_workspace, open_file=f)
    assert snap_compare(app, run_before=_focus_editor(app), terminal_size=TERMINAL_SIZE)


def test_snapshot_render_whitespace(snap_compare, snapshot_workspace: Path):
    """Editor shows whitespace markers (middle dots for spaces, arrows for tabs)."""
    f = snapshot_workspace / "whitespace.py"
    f.write_text(
        "def example():\n"
        "    x = 1\n"
        "    if x > 0:\n"
        "        print('hello')  \n"
        "\treturn x\n"
    )
    app = make_app(snapshot_workspace, open_file=f)

    async def enable_whitespace(pilot):
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        if editor is not None:
            editor.render_whitespace = "all"
            editor.action_focus()
        await pilot.pause()

    assert snap_compare(app, run_before=enable_whitespace, terminal_size=TERMINAL_SIZE)
