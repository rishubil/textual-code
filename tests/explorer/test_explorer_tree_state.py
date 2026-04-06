"""Tests for explorer tree state management.

Covers:
- Sort order verification (directories first, then files, alphabetical)
- Expand/collapse state preservation across tree reload
- Find/select file in tree (select_file direct calls)
- Cursor position after file operations

VSCode references:
- objectTreeModel.test.ts: "collapse state is preserved with strict identity"
- objectTreeModel.test.ts: "sorter"
- indexTreeModel.test.ts: "collapse" / "expand" state preservation
- asyncDataTree.test.ts: "Collapse state should be preserved across refresh calls"
"""

from pathlib import Path

import pytest

from tests.conftest import (
    await_workers,
    find_tree_node_by_path,
    get_tree_child_labels,
    make_app,
)
from textual_code.widgets.explorer import Explorer, FilteredDirectoryTree


def _get_expanded_paths(tree: FilteredDirectoryTree) -> set[Path]:
    """Collect paths of all expanded directory nodes."""
    result: set[Path] = set()

    def walk(node):
        for child in node.children:
            if child.data is not None and child.is_expanded and child.allow_expand:
                result.add(child.data.path)
                walk(child)

    walk(tree.root)
    return result


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def state_tree(workspace: Path) -> dict[str, Path]:
    """Create a directory tree suitable for state management tests.

    Structure (sorted order):
      dir_alpha/
        inner.py
      dir_beta/
        sub_beta/
          deep.py
        beta_file.py
      aaa.py
      mmm.py
      zzz.py
    """
    dirs = {
        "dir_alpha": workspace / "dir_alpha",
        "dir_beta": workspace / "dir_beta",
        "sub_beta": workspace / "dir_beta" / "sub_beta",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    files = {
        "inner": dirs["dir_alpha"] / "inner.py",
        "deep": dirs["sub_beta"] / "deep.py",
        "beta_file": dirs["dir_beta"] / "beta_file.py",
        "aaa": workspace / "aaa.py",
        "mmm": workspace / "mmm.py",
        "zzz": workspace / "zzz.py",
    }
    for f in files.values():
        f.write_text(f"# {f.stem}\n")

    return {**dirs, **files}


# ── Sort Order ───────────────────────────────────────────────────────────────


async def test_sort_order_dirs_first_then_files_alphabetical(
    workspace: Path, state_tree: dict[str, Path]
):
    """Tree root children: directories first (alphabetical), then files (alphabetical).

    Port of VSCode objectTreeModel.test.ts "sorter" concept — verifies our
    sort key: (not is_dir, name.lower()).
    """
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        tree = app.sidebar.explorer.directory_tree
        labels = get_tree_child_labels(tree)

        # Directories first (alphabetical), then files (alphabetical)
        assert labels == ["dir_alpha", "dir_beta", "aaa.py", "mmm.py", "zzz.py"]


async def test_sort_order_case_insensitive(workspace: Path):
    """Sort order is case-insensitive: 'Alpha.py' and 'beta.py' sort alphabetically.

    Verifies the .lower() in the sort key handles mixed-case file names.
    """
    (workspace / "Zebra.py").write_text("# Zebra\n")
    (workspace / "alpha.py").write_text("# alpha\n")
    (workspace / "Beta.py").write_text("# Beta\n")
    (workspace / "GAMMA.py").write_text("# GAMMA\n")

    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        tree = app.sidebar.explorer.directory_tree
        labels = get_tree_child_labels(tree)

        # All are files, sorted case-insensitively
        assert labels == ["alpha.py", "Beta.py", "GAMMA.py", "Zebra.py"]


async def test_sort_order_children_within_directory(
    workspace: Path, state_tree: dict[str, Path]
):
    """Children within an expanded directory follow the same sort order.

    Expands dir_beta and verifies: sub_beta/ (dir) comes before beta_file.py (file).
    """
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        tree = app.sidebar.explorer.directory_tree

        # Find and expand dir_beta
        dir_beta_node = find_tree_node_by_path(tree, state_tree["dir_beta"])
        assert dir_beta_node is not None
        dir_beta_node.expand()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        # Children: sub_beta/ first (directory), then beta_file.py (file)
        child_labels = [str(c.label) for c in dir_beta_node.children]
        assert child_labels == ["sub_beta", "beta_file.py"]


# ── Expand/Collapse Preservation ─────────────────────────────────────────────


async def test_expand_state_preserved_after_reload(
    workspace: Path, state_tree: dict[str, Path]
):
    """Expanded directories remain expanded after tree reload().

    Port of VSCode asyncDataTree.test.ts "Collapse state should be preserved
    across refresh calls" — adapted for our reload() mechanism.
    """
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        tree = app.sidebar.explorer.directory_tree

        # Expand dir_alpha
        alpha_node = find_tree_node_by_path(tree, state_tree["dir_alpha"])
        assert alpha_node is not None
        alpha_node.expand()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        # Verify expanded before reload
        expanded_before = _get_expanded_paths(tree)
        assert state_tree["dir_alpha"] in expanded_before

        # Trigger reload
        tree.reload()
        for _ in range(10):
            await pilot.wait_for_scheduled_animations()

        # dir_alpha should still be expanded
        alpha_node_after = find_tree_node_by_path(tree, state_tree["dir_alpha"])
        assert alpha_node_after is not None
        assert alpha_node_after.is_expanded


async def test_nested_expand_preserved_after_reload(
    workspace: Path, state_tree: dict[str, Path]
):
    """Nested expanded directories survive reload.

    Expand dir_beta → sub_beta, reload, both should remain expanded.
    Port of VSCode indexTreeModel.test.ts "collapse should recursively adjust"
    concept — but testing preservation rather than collapse.
    """
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        tree = app.sidebar.explorer.directory_tree

        # Expand dir_beta
        beta_node = find_tree_node_by_path(tree, state_tree["dir_beta"])
        assert beta_node is not None
        beta_node.expand()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        # Expand sub_beta
        sub_beta_node = find_tree_node_by_path(tree, state_tree["sub_beta"])
        assert sub_beta_node is not None
        sub_beta_node.expand()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        # Verify both expanded
        expanded_before = _get_expanded_paths(tree)
        assert state_tree["dir_beta"] in expanded_before
        assert state_tree["sub_beta"] in expanded_before

        # Reload
        tree.reload()
        for _ in range(10):
            await pilot.wait_for_scheduled_animations()

        # Both should still be expanded
        beta_after = find_tree_node_by_path(tree, state_tree["dir_beta"])
        assert beta_after is not None
        assert beta_after.is_expanded

        sub_beta_after = find_tree_node_by_path(tree, state_tree["sub_beta"])
        assert sub_beta_after is not None
        assert sub_beta_after.is_expanded


async def test_collapse_state_not_changed_after_reload(
    workspace: Path, state_tree: dict[str, Path]
):
    """Collapsed directories remain collapsed after reload.

    Complement to expansion preservation — verifies reload doesn't accidentally
    expand collapsed dirs.
    """
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        tree = app.sidebar.explorer.directory_tree

        # Verify dirs are initially collapsed (default state)
        alpha_node = find_tree_node_by_path(tree, state_tree["dir_alpha"])
        assert alpha_node is not None
        assert not alpha_node.is_expanded

        # Reload
        tree.reload()
        for _ in range(10):
            await pilot.wait_for_scheduled_animations()

        # Should still be collapsed
        alpha_after = find_tree_node_by_path(tree, state_tree["dir_alpha"])
        assert alpha_after is not None
        assert not alpha_after.is_expanded


async def test_expand_state_preserved_after_file_create(
    workspace: Path, state_tree: dict[str, Path]
):
    """Expanded directory stays expanded after a new file is created in workspace.

    Simulates the flow: user expands dir_alpha, then creates a new file at the
    workspace root. The polling/reload cycle should preserve the expanded state.
    """
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        tree = app.sidebar.explorer.directory_tree

        # Expand dir_alpha
        alpha_node = find_tree_node_by_path(tree, state_tree["dir_alpha"])
        assert alpha_node is not None
        alpha_node.expand()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        # Create a new file (triggers workspace change on next poll)
        new_file = workspace / "new_file.py"
        new_file.write_text("# new\n")

        # Trigger reload to simulate auto-refresh detecting the change
        tree.reload()
        for _ in range(10):
            await pilot.wait_for_scheduled_animations()

        # dir_alpha should still be expanded
        alpha_after = find_tree_node_by_path(tree, state_tree["dir_alpha"])
        assert alpha_after is not None
        assert alpha_after.is_expanded

        # And the new file should appear in the tree
        labels = get_tree_child_labels(tree)
        assert "new_file.py" in labels


# ── Find/Select ──────────────────────────────────────────────────────────────


async def test_select_file_updates_cursor(workspace: Path, state_tree: dict[str, Path]):
    """select_file() moves the cursor to the target file.

    Direct test of the select_file mechanism without going through tab switching.
    """
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        explorer = app.sidebar.query_one(Explorer)

        # Select a top-level file
        explorer.select_file(state_tree["mmm"])
        await pilot.wait_for_scheduled_animations()
        await await_workers(pilot)

        cursor = explorer.directory_tree.cursor_node
        assert cursor is not None
        assert cursor.data is not None
        assert cursor.data.path == state_tree["mmm"]


async def test_select_file_expands_collapsed_parent(
    workspace: Path, state_tree: dict[str, Path]
):
    """select_file() on a nested path auto-expands collapsed parent directories.

    Port of VSCode objectTreeModel.test.ts "expandTo" concept — verifies
    our select_file auto-expansion mechanism.
    """
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        explorer = app.sidebar.query_one(Explorer)
        tree = explorer.directory_tree

        # dir_alpha is collapsed initially
        alpha_node = find_tree_node_by_path(tree, state_tree["dir_alpha"])
        assert alpha_node is not None
        assert not alpha_node.is_expanded

        # Select inner.py inside dir_alpha — should trigger auto-expansion
        # (triggers _load_directory worker for dir_alpha via run_cancellable)
        explorer.select_file(state_tree["inner"])
        for _ in range(10):
            await pilot.wait_for_scheduled_animations()
        await await_workers(pilot)
        for _ in range(10):
            await pilot.wait_for_scheduled_animations()
        await await_workers(pilot)

        # dir_alpha should now be expanded
        alpha_node = find_tree_node_by_path(tree, state_tree["dir_alpha"])
        assert alpha_node is not None
        assert alpha_node.is_expanded

        # Cursor should be on inner.py
        cursor = tree.cursor_node
        assert cursor is not None
        assert cursor.data is not None
        assert cursor.data.path == state_tree["inner"]


async def test_select_file_expands_deeply_nested_path(
    workspace: Path, state_tree: dict[str, Path]
):
    """select_file() expands multiple levels to reach a deeply nested file.

    Tests dir_beta → sub_beta → deep.py expansion chain.
    """
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        explorer = app.sidebar.query_one(Explorer)
        tree = explorer.directory_tree

        # Select deep.py (two levels deep — each level triggers a
        # _load_directory worker via run_cancellable).
        # Level 1: expand dir_beta, Level 2: expand sub_beta, then cursor.
        explorer.select_file(state_tree["deep"])
        for _ in range(10):
            await pilot.wait_for_scheduled_animations()
        await await_workers(pilot)
        for _ in range(10):
            await pilot.wait_for_scheduled_animations()
        await await_workers(pilot)
        for _ in range(10):
            await pilot.wait_for_scheduled_animations()
        await await_workers(pilot)

        # Both dir_beta and sub_beta should be expanded
        beta_node = find_tree_node_by_path(tree, state_tree["dir_beta"])
        assert beta_node is not None
        assert beta_node.is_expanded

        sub_beta_node = find_tree_node_by_path(tree, state_tree["sub_beta"])
        assert sub_beta_node is not None
        assert sub_beta_node.is_expanded

        # Cursor should be on deep.py
        cursor = tree.cursor_node
        assert cursor is not None
        assert cursor.data is not None
        assert cursor.data.path == state_tree["deep"]


# ── Cursor Position After Operations ─────────────────────────────────────────


async def test_cursor_after_selected_file_deleted(workspace: Path):
    """After deleting the file under cursor, cursor should not reference deleted path.

    Port of VSCode concept: tree state stability after model mutations.
    """
    f1 = workspace / "alpha.py"
    f2 = workspace / "beta.py"
    f1.write_text("# alpha\n")
    f2.write_text("# beta\n")

    app = make_app(workspace, open_file=f1)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        explorer = app.sidebar.query_one(Explorer)

        # Verify cursor is on f1
        cursor = explorer.directory_tree.cursor_node
        assert cursor is not None
        assert cursor.data is not None
        assert cursor.data.path == f1

        # Delete f1 via the explorer message flow
        explorer.post_message(Explorer.FileDeleteRequested(explorer=explorer, path=f1))
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        # Confirm deletion in modal
        from textual_code.modals import DeleteFileModalScreen

        assert isinstance(app.screen, DeleteFileModalScreen)
        await pilot.click("#delete")
        await pilot.wait_for_scheduled_animations()
        await await_workers(pilot)

        # Wait for tree reload
        for _ in range(10):
            await pilot.wait_for_scheduled_animations()

        # File should be gone from disk
        assert not f1.exists()

        # Cursor should not reference the deleted file
        cursor_after = explorer.directory_tree.cursor_node
        if cursor_after is not None and cursor_after.data is not None:
            assert cursor_after.data.path != f1
