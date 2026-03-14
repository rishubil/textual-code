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

from tests.conftest import make_app

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

        editor = app.main_view.get_active_code_editor()
        if editor is not None:
            editor.action_focus()
        await pilot.pause()

    assert snap_compare(app, run_before=reorder_tabs, terminal_size=TERMINAL_SIZE)


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
