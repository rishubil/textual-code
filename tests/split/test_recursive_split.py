"""
Tests for recursive splitting (Phase 4): N-way splits, vertical splits,
focus cycling between splits.
"""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent
from textual_code.widgets.split_container import SplitContainer
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
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(180, 30)) as pilot:
        await pilot.wait_for_scheduled_animations()

        # First split
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        assert len(all_leaves(app.main_view._split_root)) == 2

        # Open file2 in the second split
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.wait_for_scheduled_animations()

        # Second split: should create a 3rd leaf
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

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
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(180, 30)) as pilot:
        await pilot.wait_for_scheduled_animations()

        # Create 3-way split
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_code_editor(path=py_file3)
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 3

        # Focus middle leaf and close it
        middle_leaf = leaves[1]
        app.main_view._active_leaf_id = middle_leaf.leaf_id
        await app.main_view.action_close_editor_group()
        await pilot.wait_for_scheduled_animations()

        leaves_after = all_leaves(app.main_view._split_root)
        assert len(leaves_after) == 2


# ── Focus cycling ─────────────────────────────────────────────────────────────


async def test_focus_next_split(workspace, py_file):
    """action_focus_next_group moves to the next leaf."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)
        # Active should be leaf 1 (just created by split_right)
        assert app.main_view._active_leaf_id == leaves[1].leaf_id

        # Focus next should wrap to leaf 0
        app.main_view.action_focus_next_group()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._active_leaf_id == leaves[0].leaf_id


async def test_focus_prev_split(workspace, py_file):
    """action_focus_previous_group moves to the previous leaf."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)
        # Active should be leaf 1
        assert app.main_view._active_leaf_id == leaves[1].leaf_id

        # Focus prev should go to leaf 0
        app.main_view.action_focus_previous_group()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._active_leaf_id == leaves[0].leaf_id


async def test_focus_cycle_three_splits(workspace, py_file, py_file2, py_file3):
    """Focus cycles through 3 splits correctly."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(180, 30)) as pilot:
        await pilot.wait_for_scheduled_animations()

        # Create 3-way split
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 3

        # Should be on leaf 2 (last created)
        assert app.main_view._active_leaf_id == leaves[2].leaf_id

        # Next wraps to leaf 0
        app.main_view.action_focus_next_group()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._active_leaf_id == leaves[0].leaf_id

        # Next goes to leaf 1
        app.main_view.action_focus_next_group()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._active_leaf_id == leaves[1].leaf_id

        # Next goes to leaf 2
        app.main_view.action_focus_next_group()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._active_leaf_id == leaves[2].leaf_id


# ── Vertical split ────────────────────────────────────────────────────────────


async def test_split_down_creates_vertical_split(workspace, py_file):
    """action_split_down creates a vertical split."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_down()
        await pilot.wait_for_scheduled_animations()

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
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(180, 30)) as pilot:
        await pilot.wait_for_scheduled_animations()

        # Create 3-way horizontal split: each split_right copies the active file
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 3

        # The 3rd leaf should have exactly 1 pane (copy of active file)
        last_leaf = leaves[2]
        assert len(last_leaf.pane_ids) == 1
        pane_id = next(iter(last_leaf.pane_ids))
        app.main_view._active_leaf_id = last_leaf.leaf_id

        # Close via action_close_code_editor (the actual crash path)
        await app.main_view.action_close_code_editor(pane_id)
        await pilot.wait_for_scheduled_animations()

        # Should have 2 leaves now, no crash
        remaining = all_leaves(app.main_view._split_root)
        assert len(remaining) == 2


async def test_close_tab_nested_split_no_crash(workspace, py_file, py_file2):
    """Closing last tab in a nested vertical+horizontal split should not crash.

    Reproduces the exact scenario from the user's traceback: vertical split
    with a horizontal sub-split, closing a tab in the sub-split collapses it.
    """
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()

        # Split down (vertical) → leaf_0 (top), leaf_1 (bottom)
        await app.main_view.action_split_down()
        await pilot.wait_for_scheduled_animations()
        assert len(all_leaves(app.main_view._split_root)) == 2

        # In leaf_1, split right (horizontal) → leaf_0 (top), [leaf_1, leaf_2] (bottom)
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 3

        # Close the last leaf's pane via action_close_code_editor (crash path)
        last_leaf = leaves[2]
        app.main_view._active_leaf_id = last_leaf.leaf_id
        pane_id = next(iter(last_leaf.pane_ids))
        await app.main_view.action_close_code_editor(pane_id)
        await pilot.wait_for_scheduled_animations()

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
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)
        # Active is now leaf 1 (right)
        assert app.main_view._active_leaf_id == leaves[1].leaf_id

        # Click on left split's editor area
        left_dtc = app.main_view.query_one(
            f"#{leaves[0].leaf_id}", DraggableTabbedContent
        )
        await pilot.click(left_dtc)
        await pilot.wait_for_scheduled_animations()

        assert app.main_view._active_leaf_id == leaves[0].leaf_id


# ── Down-then-right split width bug ──────────────────────────────────────────


async def test_split_down_then_right_has_nonzero_width(workspace, py_file):
    """Splitting down then right should give all leaves non-zero width/height.

    Reproduces a bug where the right split created after a down split has
    zero width, making it invisible.
    """
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()

        # Split down (vertical)
        await app.main_view.action_split_down()
        await pilot.wait_for_scheduled_animations()

        # Split right in the bottom pane (horizontal)
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 3

        # ALL leaves must have non-zero width and height
        for leaf in leaves:
            dtc = app.main_view.query_one(f"#{leaf.leaf_id}", DraggableTabbedContent)
            assert dtc.size.width > 0, f"{leaf.leaf_id} has zero width"
            assert dtc.size.height > 0, f"{leaf.leaf_id} has zero height"


# ── Bug 1: _active_leaf_id and DOM focus out of sync after split ─────────────


async def test_split_right_focuses_new_leaf(workspace, py_file):
    """After split_right, _active_leaf_id and DOM focus should be on the new leaf."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.wait_for_scheduled_animations()

        # Split right
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2
        new_leaf = leaves[1]

        # _active_leaf_id should point to the new leaf
        assert app.main_view._active_leaf_id == new_leaf.leaf_id

        # The new leaf's editor should have DOM focus
        editor = app.main_view._get_active_code_editor_in_leaf(new_leaf)
        assert editor is not None
        assert editor.editor.has_focus


async def test_split_right_then_split_down_splits_new_leaf(workspace, py_file):
    """split_right → split_down should split the RIGHT leaf (not the left)."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()

        # Split right → 2 leaves
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2
        right_leaf_id = leaves[1].leaf_id

        # Split down (should split the right leaf, not the left)
        await app.main_view.action_split_down()
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 3

        # The right leaf should have been split, so it's still present
        # and the new leaf is its sibling
        right_leaf_ids = {leaves[1].leaf_id, leaves[2].leaf_id}
        assert right_leaf_id in right_leaf_ids, (
            "Original right leaf should still exist after splitting it"
        )


# ── Bug 2: _auto_close_split_if_empty skipped the first (left) leaf ──────────


async def test_close_first_leaf_collapses_to_single(workspace, py_file):
    """2-way split: closing the first (left) leaf should collapse to 1 leaf."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.wait_for_scheduled_animations()

        # Split right
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2

        # Close all panes in the first (left) leaf
        first_leaf = leaves[0]
        for pane_id in list(first_leaf.pane_ids):
            await app.main_view.action_close_code_editor(
                pane_id, auto_close_split=False
            )
        await app.main_view._auto_close_split_if_empty()
        await pilot.wait_for_scheduled_animations()

        # Should collapse to 1 leaf
        remaining = all_leaves(app.main_view._split_root)
        assert len(remaining) == 1


async def test_close_middle_leaf_in_3way(workspace, py_file, py_file2, py_file3):
    """3-way split: closing middle leaf keeps 2 leaves."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(180, 30)) as pilot:
        await pilot.wait_for_scheduled_animations()

        # Create 3-way split
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_code_editor(path=py_file3)
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 3

        # Close middle leaf's pane
        middle_leaf = leaves[1]
        app.main_view._active_leaf_id = middle_leaf.leaf_id
        for pane_id in list(middle_leaf.pane_ids):
            await app.main_view.action_close_code_editor(
                pane_id, auto_close_split=False
            )
        await app.main_view._auto_close_split_if_empty()
        await pilot.wait_for_scheduled_animations()

        remaining = all_leaves(app.main_view._split_root)
        assert len(remaining) == 2


async def test_close_empty_first_leaf_picks_nearest_active(workspace, py_file):
    """When the active first leaf is closed, active moves to the nearest leaf."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.wait_for_scheduled_animations()

        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)
        first_leaf = leaves[0]

        # Focus the first leaf and close its panes
        app.main_view._active_leaf_id = first_leaf.leaf_id
        for pane_id in list(first_leaf.pane_ids):
            await app.main_view.action_close_code_editor(
                pane_id, auto_close_split=False
            )
        await app.main_view._auto_close_split_if_empty()
        await pilot.wait_for_scheduled_animations()

        remaining = all_leaves(app.main_view._split_root)
        assert len(remaining) == 1
        assert app.main_view._active_leaf_id == remaining[0].leaf_id


# ── Bug: split left/right mounts in wrong container (issue #135) ─────────────


async def test_split_left_in_complex_grid_mounts_in_correct_container(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Split left from D in a complex grid should create a new column,
    not mount into a nested sibling container.

    Layout before split:
    |-----------+---|
    | A | B |   |   |
    |-------+   | D |
    |   C   |   |   |
    |-----------+---|

    Expected after split left from D:
    |-----------+---+---|
    | A | B |   |   |   |
    |-------+   | E | D |
    |   C   |   |   |   |
    |-----------+---+---|

    Bug: E was mounted inside B's SplitContainer instead of D's parent container.
    """
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(180, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        mv = app.main_view

        # Build layout: split right → [left, D]
        await mv.action_split_right()
        await pilot.wait_for_scheduled_animations()
        d_leaf = all_leaves(mv._split_root)[1]  # D is on the right

        # Focus left, split down → left becomes [top, C]
        mv._set_active_leaf(all_leaves(mv._split_root)[0])
        await mv.action_split_down()
        await pilot.wait_for_scheduled_animations()

        # Focus top-left, split right → top becomes [A, B]
        top_left = all_leaves(mv._split_root)[0]
        mv._set_active_leaf(top_left)
        await mv.action_split_right()
        await pilot.wait_for_scheduled_animations()

        # Now layout: root(H) → [vert([horiz([A,B]), C]), D]
        leaves_before = all_leaves(mv._split_root)
        assert len(leaves_before) == 4  # A, B, C, D

        # Focus D and split left
        mv._set_active_leaf(d_leaf)
        await mv.action_split_left()
        await pilot.wait_for_scheduled_animations()

        leaves_after = all_leaves(mv._split_root)
        assert len(leaves_after) == 5

        # The new leaf (E) should be mounted in the ROOT SplitContainer,
        # not inside the nested A|B container.
        new_leaf = leaves_after[3]  # E should be between left_vert and D
        new_dtc = mv.query_one(f"#{new_leaf.leaf_id}", DraggableTabbedContent)
        d_dtc = mv.query_one(f"#{d_leaf.leaf_id}", DraggableTabbedContent)

        # Both E and D should share the same parent SplitContainer (the root one)
        assert isinstance(new_dtc.parent, SplitContainer)
        assert new_dtc.parent is d_dtc.parent

        # All leaves must have non-zero dimensions
        for leaf in leaves_after:
            dtc = mv.query_one(f"#{leaf.leaf_id}", DraggableTabbedContent)
            assert dtc.size.width > 0, f"{leaf.leaf_id} has zero width"
            assert dtc.size.height > 0, f"{leaf.leaf_id} has zero height"


async def test_split_up_with_branch_sibling_vertical(workspace: Path, py_file: Path):
    """Split up from C where sibling is a horizontal BranchNode (depth=1).

    Tests the same bug with a vertical parent and depth=1 BranchNode sibling.

    Layout before split:
    |-------|
    | A | B |
    |-------|
    |   C   |
    |-------|

    Expected after split up from C:
    |-------|
    | A | B |
    |-------|
    |   E   |
    |-------|
    |   C   |
    |-------|

    E should be in the ROOT SplitContainer (vertical), not inside A|B's container.
    """
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        mv = app.main_view

        # Build layout: split down → [top, C]
        await mv.action_split_down()
        await pilot.wait_for_scheduled_animations()

        # Focus top, split right → top becomes [A, B]
        top = all_leaves(mv._split_root)[0]
        mv._set_active_leaf(top)
        await mv.action_split_right()
        await pilot.wait_for_scheduled_animations()

        # Now layout: root(V) → [horiz([A, B]), C]
        leaves_before = all_leaves(mv._split_root)
        assert len(leaves_before) == 3  # A, B, C
        c_leaf = leaves_before[2]

        # Focus C and split up → new leaf E between horiz([A,B]) and C
        # sibling = children[0] = horiz([A,B]) → BranchNode depth 1
        mv._set_active_leaf(c_leaf)
        await mv.action_split_up()
        await pilot.wait_for_scheduled_animations()

        leaves_after = all_leaves(mv._split_root)
        assert len(leaves_after) == 4  # A, B, E, C

        new_leaf = leaves_after[2]  # E between A|B group and C
        new_dtc = mv.query_one(f"#{new_leaf.leaf_id}", DraggableTabbedContent)
        c_dtc = mv.query_one(f"#{c_leaf.leaf_id}", DraggableTabbedContent)

        # Both E and C should share the same parent SplitContainer (root vertical)
        assert isinstance(new_dtc.parent, SplitContainer)
        assert new_dtc.parent is c_dtc.parent

        # All leaves must have non-zero dimensions
        for leaf in leaves_after:
            dtc = mv.query_one(f"#{leaf.leaf_id}", DraggableTabbedContent)
            assert dtc.size.width > 0, f"{leaf.leaf_id} has zero width"
            assert dtc.size.height > 0, f"{leaf.leaf_id} has zero height"
