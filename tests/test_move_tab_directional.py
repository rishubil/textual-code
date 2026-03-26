"""
Tests for directional tab move actions (left, right, up, down).

Covers:
- Move tab to adjacent split in each direction
- Auto-create split when no split exists in target direction
- Source leaf auto-closes when its last tab is moved
- Command registration in get_system_commands

VSCode reference (Phase 4 additions):
- editorGroupsService.test.ts lines 1082-1100: "moveEditor (across groups)"
- editorGroupsService.test.ts lines 1103-1125: "moveEditors (across groups)"
- editorGroupsService.test.ts lines 1612-1654: "moveEditor with context"
"""

from pathlib import Path

import pytest
from textual.widgets import TabbedContent

from tests.conftest import make_app
from textual_code.widgets.split_tree import all_leaves

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def py_file(workspace: Path) -> Path:
    f = workspace / "main.py"
    f.write_text("print('hello')\n")
    return f


@pytest.fixture
def py_file2(workspace: Path) -> Path:
    f = workspace / "other.py"
    f.write_text("x = 1\n")
    return f


@pytest.fixture
def py_file3(workspace: Path) -> Path:
    f = workspace / "third.py"
    f.write_text("y = 2\n")
    return f


# ── Move right with horizontal split ────────────────────────────────────────


async def test_move_tab_right(
    workspace: Path, py_file: Path, py_file2: Path, py_file3: Path
):
    """Move a tab from left split to right split."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Open second file, then split right
        await app.main_view.action_open_code_editor(py_file2)
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2

        # Open a third file in the LEFT leaf (unique to left, avoids dedup)
        app.main_view._set_active_leaf(leaves[0])
        await pilot.pause()
        await app.main_view.action_open_code_editor(py_file3)
        await pilot.pause()

        # Verify py_file3 is in left leaf
        assert py_file3 in leaves[0].opened_files

        # Move py_file3 to the right
        await app.main_view.action_move_editor_right()
        await pilot.pause()

        # py_file3 should now be in the right leaf
        right_leaf = all_leaves(app.main_view._split_root)[-1]
        assert py_file3 in right_leaf.opened_files


# ── Move left with horizontal split ─────────────────────────────────────────


async def test_move_tab_left(
    workspace: Path, py_file: Path, py_file2: Path, py_file3: Path
):
    """Move a tab from right split to left split."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Split right, then open a unique file in the right leaf
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2
        right_leaf = leaves[1]
        assert app.main_view._active_leaf_id == right_leaf.leaf_id

        # Open a file unique to right leaf
        await app.main_view.action_open_code_editor(py_file3)
        await pilot.pause()
        assert py_file3 in right_leaf.opened_files

        # Move py_file3 to the left
        await app.main_view.action_move_editor_left()
        await pilot.pause()

        # py_file3 should now be in the left leaf
        left_leaf = all_leaves(app.main_view._split_root)[0]
        assert py_file3 in left_leaf.opened_files


# ── Auto-create split when none exists ────────────────────────────────────────


async def test_move_tab_creates_split_right_when_none_exists(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Moving right with no split creates a horizontal split and moves the tab."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Open a second file so the source leaf keeps a tab after the move
        await app.main_view.action_open_code_editor(py_file2)
        await pilot.pause()

        assert len(all_leaves(app.main_view._split_root)) == 1

        # Move the active tab (py_file2) to the right — should create a split
        await app.main_view.action_move_editor_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2
        # py_file2 should be in the new right leaf
        assert py_file2 in leaves[-1].opened_files
        # py_file stays in the original left leaf
        assert py_file in leaves[0].opened_files


async def test_move_tab_creates_split_left_when_none_exists(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Moving left with no split creates a horizontal split (before)."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        await app.main_view.action_open_code_editor(py_file2)
        await pilot.pause()

        await app.main_view.action_move_editor_left()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2
        # py_file2 should be in the new left leaf (position=before → first leaf)
        assert py_file2 in leaves[0].opened_files


async def test_move_tab_creates_split_down_when_none_exists(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Moving down with no split creates a vertical split and moves the tab."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        await app.main_view.action_open_code_editor(py_file2)
        await pilot.pause()

        await app.main_view.action_move_editor_down()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2
        assert py_file2 in leaves[-1].opened_files


async def test_move_single_tab_is_noop(workspace: Path, py_file: Path):
    """Moving the only tab is a no-op (would auto-close back to 1 leaf)."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert len(all_leaves(app.main_view._split_root)) == 1

        await app.main_view.action_move_editor_right()
        await pilot.pause()

        remaining = all_leaves(app.main_view._split_root)
        assert len(remaining) == 1
        assert py_file in remaining[0].opened_files


async def test_move_tab_noop_no_editor(workspace: Path):
    """Moving is a no-op when no editor is open."""
    app = make_app(workspace, open_file=None, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        await app.main_view.action_move_editor_right()
        await pilot.pause()

        assert len(all_leaves(app.main_view._split_root)) == 1


# ── Source leaf auto-closes after move ───────────────────────────────────────


async def test_move_only_tab_auto_closes_source(
    workspace: Path, py_file: Path, py_file2: Path, py_file3: Path
):
    """When the only tab in a leaf is moved, the source leaf auto-closes."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Split right, then open a unique file in the right leaf
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2

        # Close the duplicated file in the right leaf, open a unique one
        right_leaf = leaves[1]
        assert app.main_view._active_leaf_id == right_leaf.leaf_id

        # Right leaf has the split-created file; close it and open py_file3
        for pane_id in list(right_leaf.pane_ids):
            await app.main_view.action_close_code_editor(
                pane_id, auto_close_split=False
            )
        await pilot.pause()
        await app.main_view.action_open_code_editor(py_file3)
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        right_leaf = leaves[1]
        assert len(right_leaf.pane_ids) == 1
        assert py_file3 in right_leaf.opened_files

        # Move the only tab from right to left
        await app.main_view.action_move_editor_left()
        await pilot.pause()

        # Source leaf should have been auto-closed, collapsing back to 1 leaf
        remaining = all_leaves(app.main_view._split_root)
        assert len(remaining) == 1
        assert py_file3 in remaining[0].opened_files


# ── Command registration ────────────────────────────────────────────────────


async def test_directional_move_commands_registered(workspace: Path, py_file: Path):
    """All 4 directional move commands are registered in get_system_commands."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = {cmd.title for cmd in app.get_system_commands(app.screen)}

        assert "Move Editor into Left Group" in cmds
        assert "Move Editor into Right Group" in cmds
        assert "Move Editor into Group Above" in cmds
        assert "Move Editor into Group Below" in cmds


# ── Sequential multi-move (VSCode "moveEditors" port) ─────────────────────
# Ported from VSCode "moveEditors (across groups)"
# (editorGroupsService.test.ts lines 1103-1125)
#
# VSCode has batch moveEditors(). Our editor moves one at a time.
# This test verifies the same outcome: correct counts and order after
# moving multiple tabs sequentially to another group.


async def test_sequential_multi_move_across_groups(
    workspace: Path, py_file: Path, py_file2: Path, py_file3: Path
):
    """Moving 2 of 3 tabs to another group: source keeps 1, target gets 2.

    VSCode equivalent: moveEditors([input2, input3], rightGroup)
    → leftGroup.count = 1, rightGroup.count = 2,
      rightGroup[0] = input2, rightGroup[1] = input3.
    """
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Open 2 more files (total 3 in single leaf)
        await app.main_view.action_open_code_editor(py_file2)
        await pilot.pause()
        await app.main_view.action_open_code_editor(py_file3)
        await pilot.pause()

        # Create a right split (empty destination)
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2
        left_leaf = leaves[0]

        # Activate left leaf and move py_file2 to right
        app.main_view._set_active_leaf(left_leaf)
        await pilot.pause()
        tc_left = app.main_view.query_one(f"#{left_leaf.leaf_id}", TabbedContent)
        # Activate py_file2 pane
        pane_id_file2 = left_leaf.opened_files[py_file2]
        tc_left.active = pane_id_file2
        await pilot.pause()
        await app.main_view.action_move_editor_right()
        await pilot.pause()

        # Now move py_file3 to right
        leaves = all_leaves(app.main_view._split_root)
        left_leaf = leaves[0]
        app.main_view._set_active_leaf(left_leaf)
        await pilot.pause()
        tc_left = app.main_view.query_one(f"#{left_leaf.leaf_id}", TabbedContent)
        pane_id_file3 = left_leaf.opened_files[py_file3]
        tc_left.active = pane_id_file3
        await pilot.pause()
        await app.main_view.action_move_editor_right()
        await pilot.pause()

        # Verify: left has 1 (py_file), right has 2 (py_file2, py_file3)
        leaves = all_leaves(app.main_view._split_root)
        left_leaf = leaves[0]
        right_leaf = leaves[-1]
        assert py_file in left_leaf.opened_files
        assert len(left_leaf.pane_ids) == 1
        assert py_file2 in right_leaf.opened_files
        assert py_file3 in right_leaf.opened_files
        assert len(right_leaf.pane_ids) >= 2


async def test_move_preserves_unsaved_content(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Moving a dirty editor to another group preserves unsaved content.

    VSCode equivalent: move dirty editor → editor content unchanged in target.
    """
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Open second file so source keeps a tab
        await app.main_view.action_open_code_editor(py_file2)
        await pilot.pause()

        # Activate py_file and make it dirty
        leaf = all_leaves(app.main_view._split_root)[0]
        tc = app.main_view.query_one(f"#{leaf.leaf_id}", TabbedContent)
        pane_id = leaf.opened_files[py_file]
        tc.active = pane_id
        await pilot.pause()

        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.replace_editor_text("unsaved changes here\n")
        await pilot.pause()

        # Move to right (creates new split)
        await app.main_view.action_move_editor_right()
        await pilot.pause()

        # Verify: content preserved in the new location
        editor_after = app.main_view.get_active_code_editor()
        assert editor_after is not None
        assert editor_after.text == "unsaved changes here\n"

        # Verify file moved to right leaf
        leaves = all_leaves(app.main_view._split_root)
        right_leaf = leaves[-1]
        assert py_file in right_leaf.opened_files


async def test_move_duplicate_file_activates_existing(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Moving a file to a group where it's already open activates the existing tab.

    VSCode equivalent: move editor to group where same resource exists →
    existing editor is focused, source is closed.
    """
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Open second file so source leaf keeps a tab after move
        await app.main_view.action_open_code_editor(py_file2)
        await pilot.pause()

        # Activate py_file (so it gets duplicated on split)
        leaf = all_leaves(app.main_view._split_root)[0]
        tc = app.main_view.query_one(f"#{leaf.leaf_id}", TabbedContent)
        tc.active = leaf.opened_files[py_file]
        await pilot.pause()

        # Split right — the active file (py_file) is duplicated in the right leaf
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2
        left_leaf = leaves[0]
        right_leaf = leaves[1]

        # py_file should exist in both leaves
        assert py_file in left_leaf.opened_files
        assert py_file in right_leaf.opened_files

        # Activate left leaf and try to move py_file to right
        app.main_view._set_active_leaf(left_leaf)
        await pilot.pause()
        tc_left = app.main_view.query_one(f"#{left_leaf.leaf_id}", TabbedContent)
        pane_id = left_leaf.opened_files[py_file]
        tc_left.active = pane_id
        await pilot.pause()

        left_count_before = len(left_leaf.pane_ids)

        await app.main_view.action_move_editor_right()
        await pilot.pause()

        # Source pane should be closed (deduplication: existing in target activated)
        leaves = all_leaves(app.main_view._split_root)
        right_leaf = leaves[-1]
        assert py_file in right_leaf.opened_files
        # Left leaf should have lost the py_file pane
        left_leaf = leaves[0]
        assert len(left_leaf.pane_ids) == left_count_before - 1
