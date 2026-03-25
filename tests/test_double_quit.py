"""Double Ctrl+Q force quit tests.

Textual's base App binds Ctrl+Q to action_quit.  When there are unsaved
changes, action_quit shows a confirmation modal instead of exiting.
Pressing Ctrl+Q twice within 1 second should bypass that modal and
force-quit immediately.
"""

from pathlib import Path

from tests.conftest import make_app
from textual_code.modals import UnsavedChangeQuitModalScreen


async def test_double_ctrl_q_force_quits_with_unsaved(
    workspace: Path, sample_py_file: Path
):
    """Double Ctrl+Q exits even when there are unsaved changes."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "unsaved change\n"
        await pilot.pause()

        await pilot.press("ctrl+q")
        await pilot.press("ctrl+q")
        await pilot.pause()

    # If force-quit worked, the app exited cleanly despite unsaved changes.
    # (Without force-quit, action_quit would show UnsavedChangeQuitModalScreen
    # and the app would NOT exit — run_test would hang or the screen would
    # still be the modal.)


async def test_single_ctrl_q_with_unsaved_shows_modal(
    workspace: Path, sample_py_file: Path
):
    """Single Ctrl+Q with unsaved changes should show the modal, not force-quit."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "unsaved\n"
        await pilot.pause()

        await pilot.press("ctrl+q")
        await pilot.pause()

        # The modal should be displayed, not force-quit
        assert isinstance(app.screen, UnsavedChangeQuitModalScreen)


async def test_ctrl_q_records_timestamp(workspace: Path):
    """Ctrl+Q should update the _last_ctrl_q_time timestamp."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app._last_ctrl_q_time == 0.0
        await pilot.press("ctrl+q")
        await pilot.pause()
    # Ctrl+Q sets the timestamp before triggering action_quit
    assert app._last_ctrl_q_time > 0
