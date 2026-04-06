"""Tests for explorer tree node state after file operations.

Verifies that tree widget nodes correctly reflect changes after move,
rename, create, and delete operations — complementing existing tests
that verify filesystem state and tab updates.

VSCode references:
- explorerModel.test.ts: "Move" — tree paths update after move
- explorerModel.test.ts: "Rename" — tree paths update recursively after rename
- explorerModel.test.ts: "Find with mixed case" — case-sensitive path matching
- explorerModel.test.ts: "Merge Local with Disk" — tree synchronizes with disk
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from textual.widgets import Input

from tests.conftest import (
    await_workers,
    find_tree_node_by_path,
    get_tree_child_labels,
    make_app,
)
from textual_code.app import TextualCode
from textual_code.modals import RenameModalScreen
from textual_code.widgets.explorer import Explorer

# ── Rename → Tree Node Verification ─────────────────────────────────────────


async def test_rename_file_reflected_in_tree(workspace: Path):
    """After renaming a file, old name disappears and new name appears in tree.

    Port of VSCode explorerModel.test.ts "Rename" — verifies tree node
    updates after rename operation.
    """
    f = workspace / "original.py"
    f.write_text("# original\n")

    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        tree = app.sidebar.explorer.directory_tree

        # Verify original file is in tree
        names_before = get_tree_child_labels(tree)
        assert "original.py" in names_before

        # Rename via explorer message flow
        explorer = app.sidebar.explorer
        explorer.post_message(Explorer.FileRenameRequested(explorer=explorer, path=f))
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert isinstance(app.screen, RenameModalScreen)
        inp = app.screen.query_one(Input)
        inp.value = "renamed.py"
        await pilot.wait_for_scheduled_animations()
        await pilot.click("#rename")

        # Wait for tree reload
        for _ in range(10):
            await pilot.wait_for_scheduled_animations()

        # Tree should show new name, not old name
        names_after = get_tree_child_labels(tree)
        assert "renamed.py" in names_after
        assert "original.py" not in names_after


async def test_rename_directory_children_accessible_by_new_path(workspace: Path):
    """After renaming a directory, children are accessible under new parent path.

    Port of VSCode explorerModel.test.ts "Rename" — verifies child paths
    update recursively when parent directory is renamed.
    """
    old_dir = workspace / "old_dir"
    old_dir.mkdir()
    (old_dir / "child.py").write_text("# child\n")

    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        tree = app.sidebar.explorer.directory_tree
        explorer = app.sidebar.explorer

        # Rename directory
        explorer.post_message(
            Explorer.FileRenameRequested(explorer=explorer, path=old_dir)
        )
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert isinstance(app.screen, RenameModalScreen)
        inp = app.screen.query_one(Input)
        inp.value = "new_dir"
        await pilot.wait_for_scheduled_animations()
        await pilot.click("#rename")

        for _ in range(10):
            await pilot.wait_for_scheduled_animations()

        # Tree should show new_dir, not old_dir
        names = get_tree_child_labels(tree)
        assert "new_dir" in names
        assert "old_dir" not in names

        # Expand new_dir — child should be accessible under new path
        new_dir = workspace / "new_dir"
        new_dir_node = find_tree_node_by_path(tree, new_dir)
        assert new_dir_node is not None
        new_dir_node.expand()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        new_child = new_dir / "child.py"
        child_node = find_tree_node_by_path(tree, new_child)
        assert child_node is not None


# ── Move → Tree Node Verification ───────────────────────────────────────────


async def test_move_file_reflected_in_tree(workspace: Path):
    """After moving a file, it disappears from source and appears in destination.

    Port of VSCode explorerModel.test.ts "Move" — verifies tree reflects
    new file location after move.
    """
    dest_dir = workspace / "dest"
    dest_dir.mkdir()
    f = workspace / "moveme.py"
    f.write_text("# moveme\n")

    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        tree = app.sidebar.explorer.directory_tree

        # moveme.py should be at root level
        root_names = get_tree_child_labels(tree)
        assert "moveme.py" in root_names

        # Move via direct MoveDestinationSelected message
        app.post_message(
            TextualCode.MoveDestinationSelected(source_path=f, destination_dir=dest_dir)
        )

        for _ in range(10):
            await pilot.wait_for_scheduled_animations()
        await await_workers(pilot)

        # moveme.py should no longer be at root level
        root_names_after = get_tree_child_labels(tree)
        assert "moveme.py" not in root_names_after

        # Expand dest dir — moveme.py should be there
        dest_node = find_tree_node_by_path(tree, dest_dir)
        assert dest_node is not None
        dest_node.expand()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        moved_file = dest_dir / "moveme.py"
        moved_node = find_tree_node_by_path(tree, moved_file)
        assert moved_node is not None


async def test_move_directory_subtree_reflected_in_tree(workspace: Path):
    """After moving a directory with children, subtree appears at new location.

    Port of VSCode explorerModel.test.ts "Move" subtree test — verifies
    child paths update when parent directory is moved.
    """
    src = workspace / "src_dir"
    src.mkdir()
    (src / "index.py").write_text("# index\n")

    dest = workspace / "dest_dir"
    dest.mkdir()
    # Add a sibling so dest_dir has multiple children and won't be compacted
    (dest / "existing.py").write_text("# existing\n")

    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        tree = app.sidebar.explorer.directory_tree

        # Move src_dir into dest_dir
        app.post_message(
            TextualCode.MoveDestinationSelected(source_path=src, destination_dir=dest)
        )
        await pilot.wait_for_scheduled_animations()
        await await_workers(pilot)

        for _ in range(10):
            await pilot.wait_for_scheduled_animations()

        # src_dir should be gone from root
        root_names = get_tree_child_labels(tree)
        assert "src_dir" not in root_names

        # Expand dest_dir → src_dir → verify index.py
        dest_node = find_tree_node_by_path(tree, dest)
        assert dest_node is not None
        dest_node.expand()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        moved_src = dest / "src_dir"
        moved_src_node = find_tree_node_by_path(tree, moved_src)
        assert moved_src_node is not None
        moved_src_node.expand()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        moved_index = moved_src / "index.py"
        index_node = find_tree_node_by_path(tree, moved_index)
        assert index_node is not None


# ── Find with Case Sensitivity ──────────────────────────────────────────────


@pytest.mark.skipif(sys.platform != "linux", reason="Linux-only case sensitivity")
async def test_select_file_case_sensitive(workspace: Path):
    """select_file() is case-sensitive on Linux — wrong case does not match.

    Port of VSCode explorerModel.test.ts "Find with mixed case" — on Linux,
    /path/to/Stat should NOT match /path/to/stat.
    """
    f = workspace / "CaseSensitive.py"
    f.write_text("# case\n")

    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        tree = explorer.directory_tree

        # Correct case: should find the file
        explorer.select_file(f)
        for _ in range(5):
            await pilot.wait_for_scheduled_animations()
        await await_workers(pilot)

        cursor = tree.cursor_node
        assert cursor is not None
        assert cursor.data is not None
        assert cursor.data.path == f

        # Wrong case: should NOT find the file
        wrong_case = workspace / "casesensitive.py"
        explorer.select_file(wrong_case)
        for _ in range(5):
            await pilot.wait_for_scheduled_animations()
        await await_workers(pilot)

        # Cursor should still be on the original file (unchanged)
        cursor_after = tree.cursor_node
        assert cursor_after is not None
        assert cursor_after.data is not None
        assert cursor_after.data.path == f


# ── External Changes → Tree Sync (Merge Local with Disk) ────────────────────


async def test_external_file_deletion_reflected_after_refresh(workspace: Path):
    """External file deletion is reflected in tree after poll/reload.

    Port of VSCode explorerModel.test.ts "Merge Local with Disk" —
    tree synchronizes with disk state when files are deleted externally.
    """
    f = workspace / "external.py"
    f.write_text("# will be deleted\n")

    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        tree = app.sidebar.explorer.directory_tree

        # File should be in tree
        names_before = get_tree_child_labels(tree)
        assert "external.py" in names_before

        # Initialize polling state
        tree._dir_mtimes = tree._collect_expanded_dir_mtimes()
        tree._git_ref_mtimes = tree._get_git_ref_mtimes()

        # Delete externally
        f.unlink()

        # Trigger poll and wait for reload
        tree._poll_workspace_change()
        for _ in range(5):
            await pilot.wait_for_scheduled_animations()

        # File should be gone from tree
        names_after = get_tree_child_labels(tree)
        assert "external.py" not in names_after


async def test_external_directory_deletion_reflected_after_refresh(workspace: Path):
    """External directory deletion is reflected in tree after poll/reload.

    Verifies tree removes directory node when the directory is deleted
    externally (outside the app).
    """
    d = workspace / "external_dir"
    d.mkdir()
    (d / "file.py").write_text("# inside\n")

    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        tree = app.sidebar.explorer.directory_tree

        names_before = get_tree_child_labels(tree)
        assert "external_dir" in names_before

        # Initialize polling state
        tree._dir_mtimes = tree._collect_expanded_dir_mtimes()
        tree._git_ref_mtimes = tree._get_git_ref_mtimes()

        # Delete externally
        shutil.rmtree(d)

        # Trigger poll and wait for reload
        tree._poll_workspace_change()
        for _ in range(5):
            await pilot.wait_for_scheduled_animations()

        names_after = get_tree_child_labels(tree)
        assert "external_dir" not in names_after


# ── Create → Tree Node Sort Position ────────────────────────────────────────


async def test_create_file_appears_in_correct_sort_position(workspace: Path):
    """New file created via app appears in correct sort position in tree.

    Verifies the sort key (not is_dir, name.lower()) works correctly
    when new files are added dynamically.
    """
    (workspace / "alpha.py").write_text("# a\n")
    (workspace / "gamma.py").write_text("# g\n")

    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        tree = app.sidebar.explorer.directory_tree

        names_before = get_tree_child_labels(tree)
        assert names_before == ["alpha.py", "gamma.py"]

        # Create beta.py via app message
        beta = workspace / "beta.py"
        app.post_message(TextualCode.CreateFileOrDirRequested(path=beta, is_dir=False))

        for _ in range(10):
            await pilot.wait_for_scheduled_animations()

        # beta.py should appear between alpha.py and gamma.py
        names_after = get_tree_child_labels(tree)
        assert names_after == ["alpha.py", "beta.py", "gamma.py"]


async def test_create_directory_appears_before_files(workspace: Path):
    """New directory created via app appears before files in tree.

    Directories always sort before files regardless of name.
    """
    (workspace / "aaa.py").write_text("# a\n")

    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.sidebar is not None
        tree = app.sidebar.explorer.directory_tree

        names_before = get_tree_child_labels(tree)
        assert names_before == ["aaa.py"]

        # Create zzz_dir (name comes after aaa.py alphabetically,
        # but should still appear first because it's a directory)
        zzz_dir = workspace / "zzz_dir"
        app.post_message(
            TextualCode.CreateFileOrDirRequested(path=zzz_dir, is_dir=True)
        )

        for _ in range(10):
            await pilot.wait_for_scheduled_animations()

        names_after = get_tree_child_labels(tree)
        assert names_after == ["zzz_dir", "aaa.py"]
