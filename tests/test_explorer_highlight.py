"""Tests for explorer cursor highlighting when active tab changes."""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.widgets.explorer import Explorer


@pytest.fixture
def two_files(workspace: Path) -> tuple[Path, Path]:
    f1 = workspace / "alpha.py"
    f2 = workspace / "beta.py"
    f1.write_text("# alpha\n")
    f2.write_text("# beta\n")
    return f1, f2


async def test_open_file_highlights_in_explorer(workspace: Path, two_files):
    """Opening a file should highlight it in the explorer."""
    f1, f2 = two_files
    app = make_app(workspace, open_file=f1)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()  # extra pause for directory tree to load

        explorer = app.sidebar.query_one(Explorer)
        cursor_node = explorer.directory_tree.cursor_node
        assert cursor_node is not None
        assert cursor_node.data is not None
        assert cursor_node.data.path == f1


async def test_switch_tab_updates_explorer(workspace: Path, two_files):
    """Switching between tabs should update the explorer cursor."""
    f1, f2 = two_files
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()

        # Open both files
        await app.main_view.action_open_code_editor(f1)
        await pilot.pause()
        await app.main_view.action_open_code_editor(f2)
        await pilot.pause()
        await pilot.pause()

        # f2 should be highlighted (most recently opened)
        explorer = app.sidebar.query_one(Explorer)
        assert explorer.directory_tree.cursor_node is not None
        assert explorer.directory_tree.cursor_node.data.path == f2

        # Switch to f1 tab
        pane_id_f1 = app.main_view.pane_id_from_path(f1)
        app.main_view.tabbed_content.active = pane_id_f1
        await pilot.pause()
        await pilot.pause()

        # f1 should now be highlighted
        assert explorer.directory_tree.cursor_node is not None
        assert explorer.directory_tree.cursor_node.data.path == f1


async def test_select_file_outside_workspace_is_noop(workspace: Path, two_files):
    """select_file with path outside workspace is silently ignored."""
    f1, _ = two_files
    app = make_app(workspace, open_file=f1)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()

        explorer = app.sidebar.query_one(Explorer)
        original_node = explorer.directory_tree.cursor_node

        # Call select_file with a path outside workspace — should not raise
        outside_path = Path("/tmp/outside.py")
        explorer.select_file(outside_path)
        await pilot.pause()

        # Cursor should not have changed
        assert explorer.directory_tree.cursor_node is original_node
