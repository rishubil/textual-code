"""
Redo functionality tests.

T-01: undo → ctrl+shift+z redo → text restored
T-02: redo with nothing to redo does not error
"""

from pathlib import Path

from tests.conftest import make_app


async def test_redo_restores_text(workspace: Path, sample_py_file: Path):
    """T-01: Type text, undo with ctrl+z, redo with ctrl+shift+z restores text."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_focus()
        await pilot.wait_for_scheduled_animations()

        # Move to end and type some text
        await pilot.press("end")
        await pilot.press("x")
        await pilot.wait_for_scheduled_animations()

        text_after_type = editor.editor.text

        # Undo
        await pilot.press("ctrl+z")
        await pilot.wait_for_scheduled_animations()
        text_after_undo = editor.editor.text
        assert text_after_undo != text_after_type

        # Redo via ctrl+shift+z
        await pilot.press("ctrl+shift+z")
        await pilot.wait_for_scheduled_animations()
        assert editor.editor.text == text_after_type


async def test_redo_no_error_when_nothing_to_redo(
    workspace: Path, sample_py_file: Path
):
    """T-02: ctrl+shift+z with nothing to redo does not raise an error."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.action_focus()
        await pilot.wait_for_scheduled_animations()

        # Press ctrl+shift+z without anything to redo — should not raise
        original_text = editor.editor.text
        await pilot.press("ctrl+shift+z")
        await pilot.wait_for_scheduled_animations()
        # Text remains unchanged
        assert editor.editor.text == original_text
