"""
Tests for recursive splitting (Phase 4): N-way splits, vertical splits,
focus cycling between splits.
"""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent
from textual_code.widgets.split_tree import BranchNode, all_leaves


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


# ── Three-way horizontal split ───────────────────────────────────────────────


async def test_three_way_horizontal_split(workspace, py_file, py_file2, py_file3):
    """Splitting twice horizontally creates 3 leaves."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(180, 30)) as pilot:
        await pilot.pause()

        # First split
        await app.main_view.action_split_right()
        await pilot.pause()
        assert len(all_leaves(app.main_view._split_root)) == 2

        # Open file2 in the second split
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.pause()

        # Second split: should create a 3rd leaf
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 3

        # Root should be a BranchNode with 3 children
        root = app.main_view._split_root
        assert isinstance(root, BranchNode)
        assert len(root.children) == 3


async def test_close_middle_split_collapses_correctly(
    workspace, py_file, py_file2, py_file3
):
    """Closing the middle split in a 3-way split preserves the outer two."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(180, 30)) as pilot:
        await pilot.pause()

        # Create 3-way split
        await app.main_view.action_split_right()
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=py_file3)
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 3

        # Focus middle leaf and close it
        middle_leaf = leaves[1]
        app.main_view._active_leaf_id = middle_leaf.leaf_id
        await app.main_view.action_close_split()
        await pilot.pause()

        leaves_after = all_leaves(app.main_view._split_root)
        assert len(leaves_after) == 2


# ── Focus cycling ─────────────────────────────────────────────────────────────


async def test_focus_next_split(workspace, py_file):
    """action_focus_next_split moves to the next leaf."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        # Active should be leaf 1 (just created by split_right)
        assert app.main_view._active_leaf_id == leaves[1].leaf_id

        # Focus next should wrap to leaf 0
        app.main_view.action_focus_next_split()
        await pilot.pause()
        assert app.main_view._active_leaf_id == leaves[0].leaf_id


async def test_focus_prev_split(workspace, py_file):
    """action_focus_prev_split moves to the previous leaf."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        # Active should be leaf 1
        assert app.main_view._active_leaf_id == leaves[1].leaf_id

        # Focus prev should go to leaf 0
        app.main_view.action_focus_prev_split()
        await pilot.pause()
        assert app.main_view._active_leaf_id == leaves[0].leaf_id


async def test_focus_cycle_three_splits(workspace, py_file, py_file2, py_file3):
    """Focus cycles through 3 splits correctly."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(180, 30)) as pilot:
        await pilot.pause()

        # Create 3-way split
        await app.main_view.action_split_right()
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 3

        # Should be on leaf 2 (last created)
        assert app.main_view._active_leaf_id == leaves[2].leaf_id

        # Next wraps to leaf 0
        app.main_view.action_focus_next_split()
        await pilot.pause()
        assert app.main_view._active_leaf_id == leaves[0].leaf_id

        # Next goes to leaf 1
        app.main_view.action_focus_next_split()
        await pilot.pause()
        assert app.main_view._active_leaf_id == leaves[1].leaf_id

        # Next goes to leaf 2
        app.main_view.action_focus_next_split()
        await pilot.pause()
        assert app.main_view._active_leaf_id == leaves[2].leaf_id


# ── Vertical split ────────────────────────────────────────────────────────────


async def test_split_down_creates_vertical_split(workspace, py_file):
    """action_split_down creates a vertical split."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_down()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2

        root = app.main_view._split_root
        assert isinstance(root, BranchNode)
        assert root.direction == "vertical"


# ── Focus sets active leaf correctly ──────────────────────────────────────────


async def test_close_tab_in_3way_split_no_crash(workspace, py_file, py_file2, py_file3):
    """Closing last tab in a 3-way split should auto-collapse without crashing.

    Reproduces a bug where _auto_close_split_if_empty crashed with NoMatches
    when querying the active leaf's widget after collapsing an empty leaf.
    Uses action_close_code_editor (the actual crash path via CodeEditor.Closed).
    """
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(180, 30)) as pilot:
        await pilot.pause()

        # Create 3-way horizontal split: each split_right copies the active file
        await app.main_view.action_split_right()
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 3

        # The 3rd leaf should have exactly 1 pane (copy of active file)
        last_leaf = leaves[2]
        assert len(last_leaf.pane_ids) == 1
        pane_id = next(iter(last_leaf.pane_ids))
        app.main_view._active_leaf_id = last_leaf.leaf_id

        # Close via action_close_code_editor (the actual crash path)
        await app.main_view.action_close_code_editor(pane_id)
        await pilot.pause()

        # Should have 2 leaves now, no crash
        remaining = all_leaves(app.main_view._split_root)
        assert len(remaining) == 2


async def test_close_tab_nested_split_no_crash(workspace, py_file, py_file2):
    """Closing last tab in a nested vertical+horizontal split should not crash.

    Reproduces the exact scenario from the user's traceback: vertical split
    with a horizontal sub-split, closing a tab in the sub-split collapses it.
    """
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()

        # Split down (vertical) → leaf_0 (top), leaf_1 (bottom)
        await app.main_view.action_split_down()
        await pilot.pause()
        assert len(all_leaves(app.main_view._split_root)) == 2

        # In leaf_1, split right (horizontal) → leaf_0 (top), [leaf_1, leaf_2] (bottom)
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 3

        # Close the last leaf's pane via action_close_code_editor (crash path)
        last_leaf = leaves[2]
        app.main_view._active_leaf_id = last_leaf.leaf_id
        pane_id = next(iter(last_leaf.pane_ids))
        await app.main_view.action_close_code_editor(pane_id)
        await pilot.pause()

        # Should have 2 leaves now, and remaining widgets are queryable
        remaining = all_leaves(app.main_view._split_root)
        assert len(remaining) == 2

        # ALL remaining leaf widgets must be queryable (the crash was NoMatches)
        for leaf in remaining:
            dtc = app.main_view.query_one(f"#{leaf.leaf_id}", DraggableTabbedContent)
            assert dtc is not None
            assert dtc.size.width > 0  # verify layout is valid


async def test_clicking_split_changes_active_leaf(workspace, py_file, py_file2):
    """Clicking in a split panel changes the active leaf."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        # Active is now leaf 1 (right)
        assert app.main_view._active_leaf_id == leaves[1].leaf_id

        # Click on left split's editor area
        left_dtc = app.main_view.query_one(
            f"#{leaves[0].leaf_id}", DraggableTabbedContent
        )
        await pilot.click(left_dtc)
        await pilot.pause()

        assert app.main_view._active_leaf_id == leaves[0].leaf_id


# ── Down-then-right split width bug ──────────────────────────────────────────


async def test_split_down_then_right_has_nonzero_width(workspace, py_file):
    """Splitting down then right should give all leaves non-zero width/height.

    Reproduces a bug where the right split created after a down split has
    zero width, making it invisible.
    """
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()

        # Split down (vertical)
        await app.main_view.action_split_down()
        await pilot.pause()

        # Split right in the bottom pane (horizontal)
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 3

        # ALL leaves must have non-zero width and height
        for leaf in leaves:
            dtc = app.main_view.query_one(f"#{leaf.leaf_id}", DraggableTabbedContent)
            assert dtc.size.width > 0, f"{leaf.leaf_id} has zero width"
            assert dtc.size.height > 0, f"{leaf.leaf_id} has zero height"
