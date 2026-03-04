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

from tests.conftest import make_app

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
        await pilot.pause()

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
