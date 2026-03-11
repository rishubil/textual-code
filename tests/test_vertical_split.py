"""
Tests for the vertical split view (toggle split orientation) feature.

Red-Green TDD: written before implementation so all tests initially fail,
then pass once the feature is implemented.
"""

from pathlib import Path

import pytest

from tests.conftest import make_app


@pytest.fixture
def py_file(workspace: Path) -> Path:
    f = workspace / "main.py"
    f.write_text("print('hello')\n")
    return f


# ── Unit tests ───────────────────────────────────────────────────────────────


async def test_toggle_split_vertical_command_exists(workspace: Path):
    """'Toggle split orientation' command is yielded by get_system_commands."""
    from unittest.mock import MagicMock

    app = make_app(workspace, open_file=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen_mock = MagicMock()
        commands = list(app.get_system_commands(screen_mock))
        titles = [c.title for c in commands]
        assert "Toggle split orientation" in titles


async def test_toggle_split_vertical_adds_css_class(workspace: Path, py_file: Path):
    """action_toggle_split_vertical adds 'split-vertical' class to #split_container."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        container = app.main_view.query_one("#split_container")
        assert "split-vertical" not in container.classes

        app.main_view.action_toggle_split_vertical()
        await pilot.pause()

        assert "split-vertical" in container.classes


async def test_toggle_split_vertical_twice_removes_class(
    workspace: Path, py_file: Path
):
    """Calling action_toggle_split_vertical twice reverts to horizontal layout."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        container = app.main_view.query_one("#split_container")

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
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Toggle to vertical orientation
        app.main_view.action_toggle_split_vertical()
        await pilot.pause()

        # Open horizontal split
        await app.main_view.action_split_right()
        await pilot.pause()

        # Split should be visible
        assert app.main_view._split_visible is True
        assert app.main_view.right_tabbed_content.display is True


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
