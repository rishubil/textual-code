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

from tests.conftest import make_app
from textual_code.modals import RebindKeyScreen
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
        app.action_quit()
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
        editor._file_mtime -= 1.0
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
        order = tc.get_ordered_pane_ids()
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
        await pilot.pause(0.5)

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

        # Simulate drag state: -dragging on source tab, edge overlay on source pane
        content_tabs = left_dtc.get_child_by_type(ContentTabs)
        tabs = list(content_tabs.query(ContentTab))
        tabs[0].add_class("-dragging")
        left_dtc.show_edge_overlay()
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
        app.sidebar.styles.width = 12
        await pilot.pause()

    assert snap_compare(app, run_before=run_before, terminal_size=TERMINAL_SIZE)
