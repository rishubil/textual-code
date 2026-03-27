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

        assert app.sidebar is not None
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
        assert app.sidebar is not None
        explorer = app.sidebar.query_one(Explorer)
        assert explorer.directory_tree.cursor_node is not None
        assert explorer.directory_tree.cursor_node.data is not None
        assert explorer.directory_tree.cursor_node.data.path == f2

        # Switch to f1 tab
        pane_id_f1 = app.main_view.pane_id_from_path(f1)
        assert pane_id_f1 is not None
        tc = app.main_view.tabbed_content
        tc.active = pane_id_f1
        await pilot.pause()
        await pilot.pause()

        # f1 should now be highlighted
        assert explorer.directory_tree.cursor_node is not None
        assert explorer.directory_tree.cursor_node.data is not None
        assert explorer.directory_tree.cursor_node.data.path == f1


async def test_switch_tab_updates_explorer_nested_file(workspace: Path):
    """Switching to a tab with a file in a collapsed folder should highlight it."""
    subdir = workspace / "subdir"
    subdir.mkdir()
    f_top = workspace / "top.py"
    f_nested = subdir / "nested.py"
    f_top.write_text("# top\n")
    f_nested.write_text("# nested\n")

    app = make_app(workspace, open_file=f_top)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()

        # Open nested file — subdir is collapsed in the explorer
        await app.main_view.action_open_code_editor(f_nested)
        # Wait for expand + reload chain (each folder level requires one refresh cycle)
        for _ in range(5):
            await pilot.pause()

        assert app.sidebar is not None
        explorer = app.sidebar.query_one(Explorer)
        assert explorer.directory_tree.cursor_node is not None
        assert explorer.directory_tree.cursor_node.data is not None
        assert explorer.directory_tree.cursor_node.data.path == f_nested


async def test_switch_tab_updates_explorer_doubly_nested_file(workspace: Path):
    """Switching to a tab whose file is two levels deep should highlight it."""
    subdir = workspace / "a" / "b"
    subdir.mkdir(parents=True)
    f_top = workspace / "top.py"
    f_nested = subdir / "deep.py"
    f_top.write_text("# top\n")
    f_nested.write_text("# deep\n")

    app = make_app(workspace, open_file=f_top)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()

        assert app.sidebar is not None
        explorer = app.sidebar.query_one(Explorer)
        await app.main_view.action_open_code_editor(f_nested)
        # Poll until cursor reaches the target file.
        for _ in range(100):
            await pilot.pause()
            node = explorer.directory_tree.cursor_node
            if (
                node is not None
                and node.data is not None
                and node.data.path == f_nested
            ):
                break

        assert explorer.directory_tree.cursor_node is not None
        assert explorer.directory_tree.cursor_node.data is not None
        assert explorer.directory_tree.cursor_node.data.path == f_nested


async def test_select_file_deep_path_no_compact(workspace: Path):
    """select_file must reveal files at any depth without external re-triggers.

    Regression test for #141: _MAX_SELECT_RETRIES=10 is too low for deeply
    nested paths.  Each directory has a sibling file so compact_folders cannot
    collapse the chain.
    """
    # Create a path 12 levels deep where each dir has a sibling file
    deep_dir = workspace
    for i in range(12):
        subdir = deep_dir / f"d{i}"
        subdir.mkdir(parents=True, exist_ok=True)
        (deep_dir / f"sibling{i}.py").write_text(f"# sibling {i}\n")
        deep_dir = subdir

    f_top = workspace / "top.py"
    f_deep = deep_dir / "deep_file.py"
    f_top.write_text("# top\n")
    f_deep.write_text("# deep\n")

    app = make_app(workspace, open_file=f_top)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()

        assert app.sidebar is not None
        explorer = app.sidebar.query_one(Explorer)
        await app.main_view.action_open_code_editor(f_deep)

        # Wait for the explorer to expand all ancestors — NO re-trigger workaround.
        # Each directory level needs several frames for async loading.
        for _ in range(200):
            await pilot.pause()

        node = explorer.directory_tree.cursor_node
        assert node is not None and node.data is not None
        # Before the fix this fails: cursor stuck mid-way, _pending_path=None
        assert node.data.path == f_deep


async def test_switch_tab_updates_explorer_after_collapse(workspace: Path):
    """Switching to a tab whose folder was expanded then collapsed should work."""
    subdir = workspace / "subdir"
    subdir.mkdir()
    f_top = workspace / "top.py"
    f_nested = subdir / "nested.py"
    f_top.write_text("# top\n")
    f_nested.write_text("# nested\n")

    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()

        # Open both files so subdir gets expanded
        await app.main_view.action_open_code_editor(f_top)
        await pilot.pause()
        await app.main_view.action_open_code_editor(f_nested)
        for _ in range(5):
            await pilot.pause()

        assert app.sidebar is not None
        explorer = app.sidebar.query_one(Explorer)

        # Collapse subdir manually
        subdir_node = next(
            n
            for n in explorer.directory_tree.root.children
            if n.data is not None and n.data.path == subdir
        )
        subdir_node.collapse()
        await pilot.pause()

        # Switch to f_top, then back to f_nested (subdir is collapsed)
        pane_id_top = app.main_view.pane_id_from_path(f_top)
        assert pane_id_top is not None
        tc = app.main_view.tabbed_content
        tc.active = pane_id_top
        await pilot.pause()

        pane_id_nested = app.main_view.pane_id_from_path(f_nested)
        assert pane_id_nested is not None
        tc = app.main_view.tabbed_content
        tc.active = pane_id_nested
        for _ in range(5):
            await pilot.pause()

        assert explorer.directory_tree.cursor_node is not None
        assert explorer.directory_tree.cursor_node.data is not None
        assert explorer.directory_tree.cursor_node.data.path == f_nested


async def test_select_file_nonexistent_nested_path_is_noop(workspace: Path):
    """select_file with a path whose parent dir is missing from the tree is a no-op."""
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()

        assert app.sidebar is not None
        explorer = app.sidebar.query_one(Explorer)
        original_node = explorer.directory_tree.cursor_node

        # Path is inside workspace but the subdirectory does not exist on disk
        ghost_path = workspace / "ghost_dir" / "ghost.py"
        explorer.select_file(ghost_path)
        await pilot.pause()

        # Cursor should not have changed
        assert explorer.directory_tree.cursor_node is original_node


async def test_select_file_outside_workspace_is_noop(workspace: Path, two_files):
    """select_file with path outside workspace is silently ignored."""
    f1, _ = two_files
    app = make_app(workspace, open_file=f1)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.pause()

        assert app.sidebar is not None
        explorer = app.sidebar.query_one(Explorer)
        original_node = explorer.directory_tree.cursor_node

        # Call select_file with a path outside workspace — should not raise
        outside_path = Path("/tmp/outside.py")
        explorer.select_file(outside_path)
        await pilot.pause()

        # Cursor should not have changed
        assert explorer.directory_tree.cursor_node is original_node
