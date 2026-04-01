"""
Tests for F6 / Shift+F6 widget focus cycling.

Uses Textual's built-in focus_next / focus_previous actions.
"""

from pathlib import Path

import pytest

from tests.conftest import make_app


@pytest.fixture
def py_file(workspace: Path) -> Path:
    f = workspace / "main.py"
    f.write_text("print('hello')\n")
    return f


async def test_f6_moves_focus(workspace: Path, py_file: Path):
    """F6 should move focus to a different widget."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        before = app.focused
        await pilot.press("f6")
        await pilot.wait_for_scheduled_animations()
        assert app.focused is not None
        assert app.focused is not before


async def test_shift_f6_moves_focus_backward(workspace: Path, py_file: Path):
    """Shift+F6 should move focus backward."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        before = app.focused
        await pilot.press("shift+f6")
        await pilot.wait_for_scheduled_animations()
        assert app.focused is not None
        assert app.focused is not before


async def test_f6_escapes_editor(workspace: Path, py_file: Path):
    """F6 should move focus away from the editor (core use case)."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Ensure focus starts on a TextArea (editor)
        from textual.widgets import TextArea

        editor = app.query_one(TextArea)
        editor.focus()
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.focused, TextArea)

        await pilot.press("f6")
        await pilot.wait_for_scheduled_animations()
        # Focus should have left the editor
        assert app.focused is not None
        assert not isinstance(app.focused, TextArea)


async def test_f6_wraps_around(workspace: Path, py_file: Path):
    """Pressing F6 enough times should cycle back to the original widget."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        start = app.focused

        # Press F6 many times to cycle through all focusable widgets
        for _ in range(20):
            await pilot.press("f6")
            await pilot.wait_for_scheduled_animations()
            if app.focused is start:
                break

        assert app.focused is start
