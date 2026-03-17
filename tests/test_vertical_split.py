"""
Tests for the vertical split view (toggle split orientation) feature.

Uses the tree-based split model with SplitContainer.
"""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.widgets.split_container import SplitContainer


@pytest.fixture
def py_file(workspace: Path) -> Path:
    f = workspace / "main.py"
    f.write_text("print('hello')\n")
    return f


# ── Unit tests ───────────────────────────────────────────────────────────────


async def test_toggle_split_vertical_command_exists(workspace: Path):
    """'Toggle split orientation' command is yielded by get_system_commands."""
    from unittest.mock import MagicMock

    app = make_app(workspace, open_file=None, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen_mock = MagicMock()
        commands = list(app.get_system_commands(screen_mock))
        titles = [c.title for c in commands]
        assert "Toggle split orientation" in titles


async def test_toggle_split_vertical_adds_css_class(workspace: Path, py_file: Path):
    """action_toggle_split_vertical toggles 'split-vertical' class on SplitContainer."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        # First create a split so we have a SplitContainer
        await app.main_view.action_split_right()
        await pilot.pause()

        containers = list(app.main_view.query(SplitContainer))
        assert containers, "Expected a SplitContainer after split"
        container = containers[0]

        app.main_view.action_toggle_split_vertical()
        await pilot.pause()

        assert "split-vertical" in container.classes


async def test_toggle_split_vertical_twice_removes_class(
    workspace: Path, py_file: Path
):
    """Calling action_toggle_split_vertical twice reverts to horizontal layout."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        containers = list(app.main_view.query(SplitContainer))
        container = containers[0]

        app.main_view.action_toggle_split_vertical()
        await pilot.pause()
        assert "split-vertical" in container.classes

        app.main_view.action_toggle_split_vertical()
        await pilot.pause()
        assert "split-vertical" not in container.classes


async def test_horizontal_split_still_works_after_vertical_toggle(
    workspace: Path, py_file: Path
):
    """Horizontal split (Ctrl+\\) still works after toggling vertical orientation."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Open horizontal split first
        await app.main_view.action_split_right()
        await pilot.pause()

        # Toggle to vertical orientation
        app.main_view.action_toggle_split_vertical()
        await pilot.pause()

        # Split should still be visible
        assert app.main_view._split_visible is True


# ── Snapshot test ─────────────────────────────────────────────────────────────


@pytest.mark.serial
def test_vertical_split_snapshot(snap_compare, snapshot_workspace: Path):
    """Snapshot: vertical split orientation is displayed correctly."""
    py_file = snapshot_workspace / "hello.py"
    py_file.write_text("print('hello')\n")

    app = make_app(snapshot_workspace, open_file=py_file)

    async def setup(pilot):
        await pilot.pause()
        # Enable split and toggle to vertical
        await app.main_view.action_split_right()
        await pilot.pause()
        app.main_view.action_toggle_split_vertical()
        await pilot.pause()

    assert snap_compare(app, run_before=setup, terminal_size=(120, 40))
