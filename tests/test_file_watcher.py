"""
File External Change Detection + Auto/Manual Reload tests.

Group A — _file_mtime tracking
Group B — _reload_file() behavior
Group C — _poll_file_change() auto-reload
Group D — action_revert_file() manual reload with modal
Group E — action_save() with external change modal
"""

import time
from pathlib import Path

from tests.conftest import make_app
from textual_code.modals import (
    DiscardAndReloadModalScreen,
    OverwriteConfirmModalScreen,
)

# ── Group A: _file_mtime tracking ─────────────────────────────────────────────


async def test_file_mtime_set_on_open(workspace: Path, sample_py_file: Path):
    """T-01: _file_mtime is set when a file is opened."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor._file_mtime is not None
        assert editor._file_mtime == sample_py_file.stat().st_mtime


async def test_file_mtime_updated_after_save(workspace: Path, sample_py_file: Path):
    """T-02: _file_mtime is updated after saving."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Modify and save
        editor.text = "modified content\n"
        await pilot.press("ctrl+s")
        await pilot.pause()

        assert editor._file_mtime is not None
        assert editor._file_mtime == sample_py_file.stat().st_mtime


async def test_file_mtime_none_for_untitled(workspace: Path):
    """T-03: _file_mtime is None for untitled (no path) editors."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+n")
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor._file_mtime is None


# ── Group B: _reload_file() behavior ──────────────────────────────────────────


async def test_reload_file_updates_editor_text(workspace: Path, sample_py_file: Path):
    """T-04: _reload_file() loads the latest content from disk."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Write new content to disk externally
        sample_py_file.write_text("externally changed\n")

        editor._reload_file()
        await pilot.pause()

        assert editor.text == "externally changed\n"


async def test_reload_file_clears_unsaved_state(workspace: Path, sample_py_file: Path):
    """T-05: After _reload_file(), text == initial_text (no unsaved changes)."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Simulate unsaved changes
        sample_py_file.write_text("disk content\n")

        editor._reload_file()
        await pilot.pause()

        assert editor.text == editor.initial_text
        assert "*" not in editor.title


async def test_reload_file_updates_mtime(workspace: Path, sample_py_file: Path):
    """T-06: _reload_file() updates _file_mtime to the latest mtime."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Simulate external change by writing and updating mtime
        time.sleep(0.01)
        sample_py_file.write_text("new content\n")
        new_mtime = sample_py_file.stat().st_mtime

        editor._reload_file()
        await pilot.pause()

        assert editor._file_mtime == new_mtime


# ── Group C: _poll_file_change() auto-reload ──────────────────────────────────


async def test_auto_reload_when_no_unsaved_changes(
    workspace: Path, sample_py_file: Path
):
    """T-07: When file changes externally and no unsaved changes, auto-reload occurs."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.text == editor.initial_text  # no unsaved changes

        # Simulate external change
        sample_py_file.write_text("auto reloaded content\n")
        editor._file_mtime -= 1.0  # ty: ignore[unsupported-operator]

        editor._poll_file_change()
        await pilot.pause()

        assert editor.text == "auto reloaded content\n"


async def test_no_auto_reload_when_unsaved_changes_exist(
    workspace: Path, sample_py_file: Path
):
    """T-08: When file changes externally and unsaved changes exist, only notify."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Make unsaved change in editor
        editor.text = "unsaved editor change\n"
        await pilot.pause()
        assert editor.text != editor.initial_text

        # Simulate external file change
        sample_py_file.write_text("external disk change\n")
        editor._file_mtime -= 1.0  # ty: ignore[unsupported-operator]

        editor._poll_file_change()
        await pilot.pause()

        # Should NOT have reloaded — editor text still has the unsaved change
        assert editor.text == "unsaved editor change\n"


async def test_poll_does_nothing_without_mtime_change(
    workspace: Path, sample_py_file: Path
):
    """T-09: _poll_file_change() does nothing if mtime hasn't changed."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        original_text = editor.text
        # Do NOT change file or mtime
        editor._poll_file_change()
        await pilot.pause()

        assert editor.text == original_text


# ── Group D: action_revert_file() manual reload with modal ───────────────────


async def test_action_revert_file_no_unsaved_reloads_directly(
    workspace: Path, sample_py_file: Path
):
    """T-10: action_revert_file() with no unsaved changes reloads without modal."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.text == editor.initial_text

        sample_py_file.write_text("manually reloaded\n")

        editor.action_revert_file()
        await pilot.pause()

        # No modal should appear
        assert not isinstance(app.screen, DiscardAndReloadModalScreen)
        assert editor.text == "manually reloaded\n"


async def test_action_revert_file_with_unsaved_shows_modal(
    workspace: Path, sample_py_file: Path
):
    """T-11: action_revert_file() with unsaved changes shows DiscardAndReloadModal."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.text = "unsaved\n"
        await pilot.pause()

        editor.action_revert_file()
        await pilot.pause()

        assert isinstance(app.screen, DiscardAndReloadModalScreen)

        # Confirm reload
        await pilot.click("#reload")
        await pilot.pause()

        assert editor.text == "print('hello')\n"


async def test_action_revert_file_no_path_shows_error(workspace: Path):
    """T-12: action_revert_file() with no path shows error notification."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+n")
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.path is None

        editor.action_revert_file()
        await pilot.pause()

        # No modal should appear
        assert not isinstance(app.screen, DiscardAndReloadModalScreen)


# ── Group E: action_save() with external change modal ─────────────────────────


async def test_save_no_external_change_saves_directly(
    workspace: Path, sample_py_file: Path
):
    """T-13: action_save() with no external change saves without modal."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.text = "no external change\n"
        await pilot.press("ctrl+s")
        await pilot.pause()

        # No overwrite modal
        assert not isinstance(app.screen, OverwriteConfirmModalScreen)
        assert sample_py_file.read_text() == "no external change\n"


async def test_save_external_change_shows_overwrite_modal(
    workspace: Path, sample_py_file: Path
):
    """T-14: action_save() when external change exists shows OverwriteConfirmModal."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.text = "editor changes\n"
        await pilot.pause()

        # Simulate external file change by bumping the mtime tracker
        editor._file_mtime -= 1.0  # ty: ignore[unsupported-operator]

        editor.action_save()
        await pilot.pause()

        assert isinstance(app.screen, OverwriteConfirmModalScreen)


async def test_save_overwrite_confirmed_writes_file(
    workspace: Path, sample_py_file: Path
):
    """T-15: Confirming overwrite in the modal saves the editor content to disk."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.text = "overwrite confirmed\n"
        await pilot.pause()

        editor._file_mtime -= 1.0  # ty: ignore[unsupported-operator]

        editor.action_save()
        await pilot.pause()

        await pilot.click("#overwrite")
        await pilot.pause()

        assert sample_py_file.read_text() == "overwrite confirmed\n"


async def test_save_overwrite_cancelled_does_not_write(
    workspace: Path, sample_py_file: Path
):
    """T-16: Cancelling the overwrite modal does NOT write to disk."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        original_disk_content = sample_py_file.read_text()
        editor.text = "should not be written\n"
        await pilot.pause()

        editor._file_mtime -= 1.0  # ty: ignore[unsupported-operator]

        editor.action_save()
        await pilot.pause()

        await pilot.click("#cancel")
        await pilot.pause()

        assert sample_py_file.read_text() == original_disk_content


# ── Group F: cursor position preservation on reload ───────────────────────────


async def test_reload_preserves_cursor_position(workspace: Path, multiline_file: Path):
    """F-01: _reload_file() restores cursor position when file content unchanged."""
    app = make_app(workspace, open_file=multiline_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Set cursor to row 4, col 3
        editor.editor.cursor_location = (4, 3)
        await pilot.pause()

        # Reload with same content
        editor._reload_file()
        await pilot.pause()

        assert editor.editor.cursor_location == (4, 3)


async def test_reload_clamps_cursor_row_when_file_shrinks(
    workspace: Path, multiline_file: Path
):
    """F-02: _reload_file() clamps cursor row when file shrinks."""
    app = make_app(workspace, open_file=multiline_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Set cursor to row 8 (9th line of 10-line file)
        editor.editor.cursor_location = (8, 0)
        await pilot.pause()

        # Replace file with only 3 lines
        multiline_file.write_text("line1\nline2\nline3\n")
        editor._reload_file()
        await pilot.pause()

        row, _col = editor.editor.cursor_location
        # "line1\nline2\nline3\n" → document has 4 lines (including trailing empty line)
        # row 8 gets clamped to max valid row = 3
        assert row == 3


async def test_reload_clamps_cursor_col_when_line_shrinks(
    workspace: Path, sample_py_file: Path
):
    """F-03: _reload_file() clamps cursor col when line becomes shorter."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # sample_py_file: "print('hello')\n" — line length 14 chars
        editor.editor.cursor_location = (0, 12)
        await pilot.pause()

        # Replace with shorter content
        sample_py_file.write_text("hi\n")
        editor._reload_file()
        await pilot.pause()

        _row, col = editor.editor.cursor_location
        assert col == 2  # clamped to len("hi")


async def test_auto_reload_preserves_cursor_position(
    workspace: Path, multiline_file: Path
):
    """F-04: _poll_file_change() auto-reload also preserves cursor position."""
    app = make_app(workspace, open_file=multiline_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Set cursor to (3, 2)
        editor.editor.cursor_location = (3, 2)
        await pilot.pause()

        # Simulate external file change (same content, just bump mtime)
        multiline_file.write_text(multiline_file.read_text())
        editor._file_mtime -= 1.0  # ty: ignore[unsupported-operator]

        editor._poll_file_change()
        await pilot.pause()

        assert editor.editor.cursor_location == (3, 2)


# ── Group G: external-change toast lifecycle ──────────────────────────────────


async def test_toast_shown_once_on_first_poll(workspace: Path, sample_py_file: Path):
    """G-01: External change + unsaved → first poll sets notification reference."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Make unsaved change and simulate external file change
        editor.text = "unsaved\n"
        await pilot.pause()
        sample_py_file.write_text("external\n")
        editor._file_mtime -= 1.0  # ty: ignore[unsupported-operator]

        assert editor._external_change_notification is None
        editor._poll_file_change()
        await pilot.pause()

        assert editor._external_change_notification is not None


async def test_toast_not_repeated_on_subsequent_polls(
    workspace: Path, sample_py_file: Path
):
    """G-02: External change + unsaved → poll 3 times → same notification reference."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.text = "unsaved\n"
        await pilot.pause()
        sample_py_file.write_text("external\n")
        editor._file_mtime -= 1.0  # ty: ignore[unsupported-operator]

        editor._poll_file_change()
        await pilot.pause()
        first_notification = editor._external_change_notification
        assert first_notification is not None

        # Poll two more times — same notification object, no new one created
        editor._poll_file_change()
        await pilot.pause()
        editor._poll_file_change()
        await pilot.pause()

        assert editor._external_change_notification is first_notification


async def test_notification_cleared_after_reload(workspace: Path, sample_py_file: Path):
    """G-03: After reload, notification is None and removed from app._notifications."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.text = "unsaved\n"
        await pilot.pause()
        sample_py_file.write_text("external\n")
        editor._file_mtime -= 1.0  # ty: ignore[unsupported-operator]

        editor._poll_file_change()
        await pilot.pause()
        notification = editor._external_change_notification
        assert notification is not None

        # Reload dismisses the notification
        editor._reload_file()
        await pilot.pause()
        assert editor._external_change_notification is None
        assert notification not in app._notifications

        # Another external change can trigger a new notification
        sample_py_file.write_text("external2\n")
        editor._file_mtime -= 1.0
        editor.text = "unsaved2\n"
        await pilot.pause()
        editor._poll_file_change()
        await pilot.pause()
        assert editor._external_change_notification is not None


async def test_notification_cleared_after_save(workspace: Path, sample_py_file: Path):
    """G-04: After save, notification is None and removed from app._notifications."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        editor.text = "unsaved\n"
        await pilot.pause()
        sample_py_file.write_text("external\n")
        editor._file_mtime -= 1.0  # ty: ignore[unsupported-operator]

        editor._poll_file_change()
        await pilot.pause()
        notification = editor._external_change_notification
        assert notification is not None

        # Save dismisses the notification
        editor._write_to_disk()
        await pilot.pause()
        assert editor._external_change_notification is None
        assert notification not in app._notifications


async def test_new_notification_after_reload_then_change(
    workspace: Path, sample_py_file: Path
):
    """G-05: After reload clears notification, new external change shows new one."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # First cycle: external change + unsaved → notification shown
        editor.text = "unsaved\n"
        await pilot.pause()
        sample_py_file.write_text("external\n")
        editor._file_mtime -= 1.0  # ty: ignore[unsupported-operator]
        editor._poll_file_change()
        await pilot.pause()
        first_notification = editor._external_change_notification
        assert first_notification is not None

        # Reload clears it
        editor._reload_file()
        await pilot.pause()
        assert editor._external_change_notification is None

        # Second cycle: new external change → new notification (different object)
        sample_py_file.write_text("external2\n")
        editor._file_mtime -= 1.0
        editor.text = "unsaved2\n"
        await pilot.pause()
        editor._poll_file_change()
        await pilot.pause()
        second_notification = editor._external_change_notification
        assert second_notification is not None
        assert second_notification is not first_notification


async def test_new_notification_after_save_then_change(
    workspace: Path, sample_py_file: Path
):
    """G-06: After save clears notification, new external change shows new one."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # First cycle: external change + unsaved → notification shown
        editor.text = "unsaved\n"
        await pilot.pause()
        sample_py_file.write_text("external\n")
        editor._file_mtime -= 1.0  # ty: ignore[unsupported-operator]
        editor._poll_file_change()
        await pilot.pause()
        first_notification = editor._external_change_notification
        assert first_notification is not None

        # Save clears it
        editor._write_to_disk()
        await pilot.pause()
        assert editor._external_change_notification is None

        # Second cycle: new external change → new notification (different object)
        sample_py_file.write_text("external2\n")
        editor._file_mtime -= 1.0
        editor.text = "unsaved2\n"
        await pilot.pause()
        editor._poll_file_change()
        await pilot.pause()
        second_notification = editor._external_change_notification
        assert second_notification is not None
        assert second_notification is not first_notification
