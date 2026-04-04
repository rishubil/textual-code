"""
Tests for the split view feature (tree-based).

Covers:
- Initial state (single leaf)
- Split right
- Focus navigation
- Close split
- Split independence
- Bindings
- Move tab to other split
- Edge drag creates split
- DescendantFocus updates active leaf
- Focus correctness after tab moves
"""

from pathlib import Path

import pytest
from textual.message import Message

from tests.conftest import assert_focus_on_leaf, make_app, wait_for_condition
from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent
from textual_code.widgets.split_tree import BranchNode, all_leaves

# ── Fixtures ────────────────────────────────────────────────────────────────────


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


# ── Group A — Initial State ─────────────────────────────────────────────────────


async def test_initial_state_single_leaf(workspace: Path, py_file: Path):
    """Initially there is exactly one leaf."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 1


async def test_split_not_visible_initially(workspace: Path, py_file: Path):
    """_split_visible is False on startup."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._split_visible is False


async def test_active_split_initially_left(workspace: Path, py_file: Path):
    """_active_split is 'left' on startup."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._active_split == "left"


async def test_initial_file_tracked_in_left_split(workspace: Path, py_file: Path):
    """File opened on startup is in the left split's tracking."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert py_file in app.main_view._opened_files["left"]


async def test_right_pane_ids_initially_empty(workspace: Path, py_file: Path):
    """Right split has no open panes on startup."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._pane_ids["right"] == set()


# ── Group B — Split Right ────────────────────────────────────────────────────────


async def test_split_right_creates_second_leaf(workspace: Path, py_file: Path):
    """action_split_right creates a second leaf."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2


async def test_split_right_sets_split_visible(workspace: Path, py_file: Path):
    """action_split_right sets _split_visible to True."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._split_visible is True


async def test_split_right_opens_same_file(workspace: Path, py_file: Path):
    """action_split_right opens the current file in the right panel."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        assert py_file in app.main_view._opened_files["right"]


async def test_split_right_sets_active_split_to_right(workspace: Path, py_file: Path):
    """action_split_right switches focus to the right split."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._active_split == "right"


async def test_split_right_with_no_file(workspace: Path):
    """action_split_right with no open file opens an empty editor in right."""
    app = make_app(workspace, open_file=None, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._split_visible is True
        assert len(app.main_view._pane_ids["right"]) == 1


async def test_split_right_twice_creates_three_way_split(
    workspace: Path, py_file: Path
):
    """A second action_split_right creates a third split (recursive splitting)."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(180, 30)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        leaf_count_after_first = len(all_leaves(app.main_view._split_root))
        assert leaf_count_after_first == 2

        # Switch back to left and split right again
        app.main_view._active_split = "left"
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        # Now we should have 3 leaves
        assert app.main_view._split_visible is True
        assert len(all_leaves(app.main_view._split_root)) == 3


# ── Group C — Focus Navigation ───────────────────────────────────────────────────


async def test_focus_left_split_updates_active_split(workspace: Path, py_file: Path):
    """action_focus_left_split sets _active_split to 'left'."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._active_split == "right"
        app.main_view.action_focus_left_split()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._active_split == "left"


async def test_focus_right_split_when_open(workspace: Path, py_file: Path):
    """action_focus_right_split switches to right when split is visible."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        app.main_view.action_focus_left_split()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._active_split == "left"
        app.main_view.action_focus_right_split()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._active_split == "right"


async def test_focus_right_split_noop_when_closed(workspace: Path, py_file: Path):
    """action_focus_right_split is a no-op when no split is open."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._active_split == "left"
        app.main_view.action_focus_right_split()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._active_split == "left"


# ── Group D — Close Split ────────────────────────────────────────────────────────


async def test_close_split_returns_to_single_leaf(workspace: Path, py_file: Path):
    """action_close_editor_group removes the active split and returns to single leaf."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_close_editor_group()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._split_visible is False


async def test_close_split_sets_split_visible_false(workspace: Path, py_file: Path):
    """action_close_editor_group sets _split_visible to False."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_close_editor_group()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._split_visible is False


async def test_close_split_focuses_left(workspace: Path, py_file: Path):
    """action_close_editor_group sets _active_split back to 'left'."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_close_editor_group()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._active_split == "left"


async def test_close_split_clears_right_pane_ids(workspace: Path, py_file: Path):
    """action_close_editor_group removes all right pane tracking."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        assert len(app.main_view._pane_ids["right"]) > 0
        await app.main_view.action_close_editor_group()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._pane_ids["right"] == set()


async def test_close_split_noop_when_not_open(workspace: Path, py_file: Path):
    """action_close_editor_group does nothing when no split is visible."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert not app.main_view._split_visible
        await app.main_view.action_close_editor_group()  # should not raise
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._active_split == "left"


async def test_auto_close_split_when_last_right_tab_closed(
    workspace: Path, py_file: Path
):
    """Closing the last tab in the right split auto-hides the right panel."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._split_visible is True
        # Close the right editor
        leaves = all_leaves(app.main_view._split_root)
        right_leaf = leaves[1]
        right_editor = app.main_view._get_active_code_editor_in_leaf(right_leaf)
        assert right_editor is not None
        right_editor.action_close()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        # Right split should now be hidden (auto-closed)
        assert app.main_view._split_visible is False
        assert app.main_view._active_split == "left"


# ── Group E — Split Independence ─────────────────────────────────────────────────


async def test_open_file_goes_to_active_split(workspace: Path, py_file: Path):
    """Opening a file targets the active split."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # File is in left split
        assert py_file in app.main_view._opened_files["left"]
        assert py_file not in app.main_view._opened_files.get("right", {})


async def test_same_file_can_be_open_in_both_splits(workspace: Path, py_file: Path):
    """The same file can be independently open in both splits."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        # File is now in both splits
        assert py_file in app.main_view._opened_files["left"]
        assert py_file in app.main_view._opened_files["right"]
        # But they are different pane instances
        left_pane_id = app.main_view._opened_files["left"][py_file]
        right_pane_id = app.main_view._opened_files["right"][py_file]
        assert left_pane_id != right_pane_id


async def test_split_of_pane_returns_correct_split(workspace: Path, py_file: Path):
    """_split_of_pane returns 'left' for left pane, 'right' for right pane."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        left_pane_id = app.main_view._opened_files["left"][py_file]
        assert app.main_view._split_of_pane(left_pane_id) == "left"

        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        right_pane_id = app.main_view._opened_files["right"][py_file]
        assert app.main_view._split_of_pane(right_pane_id) == "right"


async def test_split_of_pane_unknown_returns_none(workspace: Path):
    """_split_of_pane returns None for an unknown pane_id."""
    app = make_app(workspace, open_file=None, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._split_of_pane("nonexistent-pane-id") is None


async def test_opened_pane_ids_combines_both_splits(workspace: Path, py_file: Path):
    """opened_pane_ids returns pane IDs from both splits combined."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        count_before = len(app.main_view.opened_pane_ids)
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        count_after = len(app.main_view.opened_pane_ids)
        assert count_after == count_before + 1


async def test_close_right_tab_removes_from_right_tracking(
    workspace: Path, py_file: Path
):
    """Closing a tab in the right split removes it from _pane_ids['right']."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        right_pane_id = app.main_view._opened_files["right"][py_file]
        assert right_pane_id in app.main_view._pane_ids["right"]
        leaves = all_leaves(app.main_view._split_root)
        right_editor = app.main_view._get_active_code_editor_in_leaf(leaves[1])
        assert right_editor is not None
        right_editor.action_close()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        assert right_pane_id not in app.main_view._pane_ids.get("right", set())


# ── Group F — Bindings & Commands ───────────────────────────────────────────────


def test_ctrl_backslash_binding_registered():
    """ctrl+backslash binding is in MainView.BINDINGS."""
    from textual_code.widgets.main_view import MainView

    keys = [b.key for b in MainView.BINDINGS]
    assert "ctrl+backslash" in keys


def test_ctrl_shift_backslash_binding_registered():
    """ctrl+shift+backslash binding is in MainView.BINDINGS."""
    from textual_code.widgets.main_view import MainView

    keys = [b.key for b in MainView.BINDINGS]
    assert "ctrl+shift+backslash" in keys


async def test_ctrl_backslash_key_opens_split(workspace: Path, py_file: Path):
    """Pressing ctrl+backslash triggers action_split_right."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+backslash")
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._split_visible is True


async def test_split_right_cmd_no_file(workspace: Path):
    """action_split_right_cmd with no open editor still opens empty right split."""
    app = make_app(workspace, open_file=None, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Should not raise
        app.action_split_right_cmd()
        await pilot.wait_for_scheduled_animations()


# ── Group G — Move Tab to Other Split ───────────────────────────────────────────


def test_ctrl_alt_backslash_binding_registered():
    """ctrl+alt+backslash binding is in MainView.BINDINGS."""
    from textual_code.widgets.main_view import MainView

    keys = [b.key for b in MainView.BINDINGS]
    assert "ctrl+alt+backslash" in keys


async def test_move_tab_left_to_right(workspace: Path, py_file: Path, py_file2: Path):
    """Moving a tab from left split places it in the right split."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Open a second file so left doesn't become empty after move
        app.main_view._active_split = "left"
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        assert py_file in app.main_view._opened_files["left"]

        # Focus the py_file tab before moving
        app.main_view._active_split = "left"
        pane_id = app.main_view._opened_files["left"][py_file]
        app.main_view.focus_pane(pane_id)
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        await app.main_view.action_move_editor_to_next_group()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        # File is now in right split and removed from left split
        assert py_file in app.main_view._opened_files["right"]
        assert py_file not in app.main_view._opened_files["left"]


async def test_move_tab_right_to_left(workspace: Path, py_file: Path):
    """Moving a tab from right split places it in the left split."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # First open a split and move to right
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._active_split == "right"
        assert py_file in app.main_view._opened_files["right"]

        # Now move back to left
        await app.main_view.action_move_editor_to_next_group()
        await pilot.wait_for_scheduled_animations()

        assert py_file in app.main_view._opened_files["left"]
        assert py_file not in app.main_view._opened_files.get("right", {})


async def test_move_tab_creates_right_split(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Moving a tab to the right auto-creates the right split if not open."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Open a second file so left doesn't become empty after move
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._split_visible is False

        # Focus py_file tab before moving
        pane_id = app.main_view._opened_files["left"][py_file]
        app.main_view.focus_pane(pane_id)
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        await app.main_view.action_move_editor_to_next_group()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.main_view._split_visible is True


async def test_move_tab_transfers_unsaved_content(workspace: Path, py_file: Path):
    """Unsaved content is preserved when a tab is moved to the other split."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()

        # Edit the file without saving
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.replace_editor_text("unsaved content here")
        await pilot.wait_for_scheduled_animations()
        assert editor.text == "unsaved content here"

        await app.main_view.action_move_editor_to_next_group()
        await pilot.wait_for_scheduled_animations()

        # The destination editor should have the unsaved content
        leaves = all_leaves(app.main_view._split_root)
        right_leaf = leaves[-1]
        new_editor = app.main_view._get_active_code_editor_in_leaf(right_leaf)
        assert new_editor is not None
        assert new_editor.text == "unsaved content here"


async def test_move_tab_no_op_without_editor(workspace: Path):
    """action_move_editor_to_next_group is a no-op when no editor is open."""
    app = make_app(workspace, open_file=None, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Should not raise — no editor open
        await app.main_view.action_move_editor_to_next_group()
        await pilot.wait_for_scheduled_animations()
        # State unchanged
        assert app.main_view._active_split == "left"
        assert app.main_view._split_visible is False


# ── Group H — Edge Drag Creates Split ───────────────────────────────────────────


async def test_edge_drag_creates_right_split(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Posting TabMovedToOtherSplit with target_pane_id=None creates the right split."""
    from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent

    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Open a second file so left doesn't become empty after drag
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._split_visible is False

        leaves = all_leaves(app.main_view._split_root)
        left_tc = app.main_view.query_one(
            f"#{leaves[0].leaf_id}", DraggableTabbedContent
        )
        pane_id = leaves[0].opened_files[py_file]
        left_tc.post_message(
            DraggableTabbedContent.TabMovedToOtherSplit(pane_id, None, False)
        )
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.main_view._split_visible is True
        assert py_file in app.main_view._opened_files["right"]
        assert py_file not in app.main_view._opened_files["left"]


async def test_edge_drag_two_tabs_moves_one(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Edge drag with 2 tabs moves one tab; one remains in left split."""
    from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent

    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Open second file in left split
        await app.main_view.open_code_editor_pane(py_file2)
        await pilot.wait_for_scheduled_animations()
        assert len(app.main_view._pane_ids["left"]) == 2

        leaves = all_leaves(app.main_view._split_root)
        left_tc = app.main_view.query_one(
            f"#{leaves[0].leaf_id}", DraggableTabbedContent
        )
        pane_id = leaves[0].opened_files[py_file]
        left_tc.post_message(
            DraggableTabbedContent.TabMovedToOtherSplit(pane_id, None, False)
        )
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert app.main_view._split_visible is True
        # py_file moved to right
        assert py_file in app.main_view._opened_files["right"]
        # py_file2 still in left
        assert py_file2 in app.main_view._opened_files["left"]


async def test_edge_drag_single_tab_clones_to_new_split(workspace: Path, py_file: Path):
    """Single-tab edge drag clones the tab into a new split instead of blocking."""
    from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent

    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        main = app.main_view
        assert main._split_visible is False

        leaves = all_leaves(main._split_root)
        assert len(leaves) == 1
        source_leaf = leaves[0]
        assert len(source_leaf.pane_ids) == 1
        pane_id = next(iter(source_leaf.pane_ids))

        tc = main.query_one(f"#{source_leaf.leaf_id}", DraggableTabbedContent)
        tc.post_message(
            DraggableTabbedContent.TabMovedToOtherSplit(
                pane_id, None, False, split_direction="right"
            )
        )
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        # Split should be created
        assert main._split_visible is True
        leaves_after = all_leaves(main._split_root)
        assert len(leaves_after) == 2

        # File should be open in both leaves (cloned)
        assert py_file in leaves_after[0].opened_files
        assert py_file in leaves_after[1].opened_files

        # Verify CodeEditor is mounted in both leaves
        from textual_code.widgets.code_editor import CodeEditor

        for leaf in leaves_after:
            tc = main.query_one(f"#{leaf.leaf_id}", DraggableTabbedContent)
            pane = tc.get_pane(leaf.opened_files[py_file])
            editors = pane.query(CodeEditor)
            assert len(editors) == 1
            assert editors.first().path == py_file


# ── Group I — DescendantFocus updates active leaf ──────────────────────────────


async def test_descendant_focus_updates_active_split(workspace: Path, py_file: Path):
    """Focusing editor content (not tab click) must update _active_split."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)

        # Focus left editor first (to move DOM focus away from right)
        left_editor = app.main_view._get_active_code_editor_in_leaf(leaves[0])
        assert left_editor is not None
        left_editor.editor.focus()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._active_split == "left"

        # Focus right editor content directly
        right_editor = app.main_view._get_active_code_editor_in_leaf(leaves[1])
        assert right_editor is not None
        right_editor.editor.focus()
        await pilot.wait_for_scheduled_animations()

        # _active_split must update to "right"
        assert app.main_view._active_split == "right"


async def test_ctrl_w_closes_focused_split_editor(workspace: Path, py_file: Path):
    """Ctrl+W closes the editor in the focused split, not the _active_split one."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        assert len(app.main_view._pane_ids["left"]) == 1
        assert len(app.main_view._pane_ids["right"]) == 1

        # Force _active_split to "left" while focus is on right editor content
        app.main_view._active_split = "left"
        leaves = all_leaves(app.main_view._split_root)
        right_editor = app.main_view._get_active_code_editor_in_leaf(leaves[1])
        assert right_editor is not None
        right_editor.editor.focus()
        await pilot.wait_for_scheduled_animations()

        # Ctrl+W should close the right editor (the focused one)
        await pilot.press("ctrl+w")
        await pilot.wait_for_scheduled_animations()

        assert len(app.main_view._pane_ids["left"]) == 1  # left untouched
        assert len(app.main_view._pane_ids.get("right", set())) == 0  # right closed


async def test_ctrl_w_last_right_tab_auto_closes_split(workspace: Path, py_file: Path):
    """Ctrl+W on the last right tab auto-hides the right split."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._split_visible is True

        # Simulate active split being left while focus is actually in right
        app.main_view._active_split = "left"
        leaves = all_leaves(app.main_view._split_root)
        right_editor = app.main_view._get_active_code_editor_in_leaf(leaves[1])
        assert right_editor is not None
        right_editor.editor.focus()
        await pilot.wait_for_scheduled_animations()

        # Ctrl+W on the last right tab → split must auto-close
        await pilot.press("ctrl+w")
        await pilot.wait_for_scheduled_animations()

        assert app.main_view._split_visible is False
        assert app.main_view._active_split == "left"


# ── Group J — Live Sync Between Split Editors ───────────────────────────────────


async def test_split_editors_sync_live_edits(workspace: Path, py_file: Path):
    """Editing in the left editor syncs text to the right editor in real time."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)
        left_editor = app.main_view._get_active_code_editor_in_leaf(leaves[0])
        right_editor = app.main_view._get_active_code_editor_in_leaf(leaves[1])
        assert left_editor is not None
        assert right_editor is not None

        new_text = "# synced!\nprint('live')\n"
        left_editor.replace_editor_text(new_text)
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert right_editor.text == new_text


async def test_split_editors_sync_on_save(workspace: Path, py_file: Path):
    """Saving the left editor updates initial_text and _file_mtime in sibling editor."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)
        left_editor = app.main_view._get_active_code_editor_in_leaf(leaves[0])
        right_editor = app.main_view._get_active_code_editor_in_leaf(leaves[1])
        assert left_editor is not None
        assert right_editor is not None

        new_text = "# saved content\n"
        left_editor.replace_editor_text(new_text)
        await pilot.wait_for_scheduled_animations()
        left_editor.action_save()
        await pilot.wait_for_scheduled_animations()

        assert right_editor.initial_text == new_text
        assert right_editor._file_mtime == left_editor._file_mtime


async def test_find_replace_bar_focus_keeps_active_split(
    workspace: Path, py_file: Path
):
    """Opening find bar inside right split keeps _active_split as 'right'."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)

        # Focus left editor first (move DOM focus away from right)
        left_editor = app.main_view._get_active_code_editor_in_leaf(leaves[0])
        assert left_editor is not None
        left_editor.editor.focus()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._active_split == "left"

        # Focus right editor
        right_editor = app.main_view._get_active_code_editor_in_leaf(leaves[1])
        assert right_editor is not None
        right_editor.editor.focus()
        await pilot.wait_for_scheduled_animations()

        # Open find bar — focus moves to find input (still inside split_right)
        await pilot.press("ctrl+f")
        await pilot.wait_for_scheduled_animations()

        # _active_split must still be "right"
        assert app.main_view._active_split == "right"


# ── Group K — Split Left ─────────────────────────────────────────────────────


async def test_split_left_creates_second_leaf(workspace: Path, py_file: Path):
    """action_split_left creates a second leaf."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_left()
        await pilot.wait_for_scheduled_animations()
        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2


async def test_split_left_new_leaf_is_first(workspace: Path, py_file: Path):
    """action_split_left places the new leaf at index 0 (left side)."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        original_leaf_id = all_leaves(app.main_view._split_root)[0].leaf_id
        await app.main_view.action_split_left()
        await pilot.wait_for_scheduled_animations()
        leaves = all_leaves(app.main_view._split_root)
        # The new leaf should be first; original should be second
        assert leaves[1].leaf_id == original_leaf_id
        assert leaves[0].leaf_id != original_leaf_id


async def test_split_left_opens_same_file(workspace: Path, py_file: Path):
    """action_split_left opens the current file in the new (left) panel."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_left()
        await pilot.wait_for_scheduled_animations()
        # The new leaf (index 0) should have the file open
        leaves = all_leaves(app.main_view._split_root)
        new_leaf = leaves[0]
        assert py_file in new_leaf.opened_files


# ── Group L — Split Up ───────────────────────────────────────────────────────


async def test_split_up_creates_second_leaf(workspace: Path, py_file: Path):
    """action_split_up creates a second leaf."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_up()
        await pilot.wait_for_scheduled_animations()
        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2


async def test_split_up_new_leaf_is_first(workspace: Path, py_file: Path):
    """action_split_up places the new leaf at index 0 (top)."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        original_leaf_id = all_leaves(app.main_view._split_root)[0].leaf_id
        await app.main_view.action_split_up()
        await pilot.wait_for_scheduled_animations()
        leaves = all_leaves(app.main_view._split_root)
        assert leaves[1].leaf_id == original_leaf_id
        assert leaves[0].leaf_id != original_leaf_id


async def test_split_up_direction_is_vertical(workspace: Path, py_file: Path):
    """Split up produces a vertical root branch."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_up()
        await pilot.wait_for_scheduled_animations()
        root = app.main_view._split_root
        assert isinstance(root, BranchNode)
        assert root.direction == "vertical"


# ── Group M — Split Left Edge Cases ──────────────────────────────────────────


async def test_split_left_twice_creates_three_leaves(workspace: Path, py_file: Path):
    """Two split_left actions from the same leaf create 3 leaves."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(180, 30)) as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_left()
        await pilot.wait_for_scheduled_animations()
        assert len(all_leaves(app.main_view._split_root)) == 2

        await app.main_view.action_split_left()
        await pilot.wait_for_scheduled_animations()
        assert len(all_leaves(app.main_view._split_root)) == 3


async def test_split_left_then_close(workspace: Path, py_file: Path):
    """split_left then close_split returns to 1 leaf."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_left()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._split_visible is True
        await app.main_view.action_close_editor_group()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        assert app.main_view._split_visible is False
        assert len(all_leaves(app.main_view._split_root)) == 1


async def test_split_right_then_split_left(workspace: Path, py_file: Path):
    """split_right then split_left creates 3 leaves in correct order."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(180, 30)) as pilot:
        await pilot.wait_for_scheduled_animations()
        original_leaf_id = all_leaves(app.main_view._split_root)[0].leaf_id

        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()
        leaves = all_leaves(app.main_view._split_root)
        right_leaf_id = leaves[1].leaf_id

        # Now split left from the right leaf (which is active)
        await app.main_view.action_split_left()
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 3
        # Order: original, new_left_of_right, right
        assert leaves[0].leaf_id == original_leaf_id
        assert leaves[2].leaf_id == right_leaf_id


async def test_split_right_from_left_inserts_in_middle(workspace: Path, py_file: Path):
    """Split right from left editor in [A|B] should produce [A|new|B], not [A|B|new]."""
    from textual_code.widgets.split_resize_handle import SplitResizeHandle

    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(180, 30)) as pilot:
        await pilot.wait_for_scheduled_animations()
        mv = app.main_view

        # Create initial split: [A | B]
        await mv.action_split_right()
        await pilot.wait_for_scheduled_animations()

        leaves_2 = all_leaves(mv._split_root)
        assert len(leaves_2) == 2
        a_leaf, b_leaf = leaves_2

        # Focus A (left) and split right again
        mv._set_active_leaf(a_leaf)
        await mv.action_split_right()
        await pilot.wait_for_scheduled_animations()

        leaves_3 = all_leaves(mv._split_root)
        assert len(leaves_3) == 3

        # Tree order should be [A, new, B]
        assert leaves_3[0].leaf_id == a_leaf.leaf_id
        assert leaves_3[2].leaf_id == b_leaf.leaf_id
        new_leaf = leaves_3[1]

        # DOM order should match tree order
        new_dtc = mv.query_one(f"#{new_leaf.leaf_id}", DraggableTabbedContent)
        b_dtc = mv.query_one(f"#{b_leaf.leaf_id}", DraggableTabbedContent)
        a_dtc = mv.query_one(f"#{a_leaf.leaf_id}", DraggableTabbedContent)

        # All three should share the same parent SplitContainer
        assert new_dtc.parent is a_dtc.parent
        assert new_dtc.parent is b_dtc.parent

        # DOM order: A should come before new, new before B
        assert new_dtc.parent is not None
        container_children = list(new_dtc.parent.children)
        dtc_children = [
            c for c in container_children if isinstance(c, DraggableTabbedContent)
        ]
        assert dtc_children == [a_dtc, new_dtc, b_dtc]

        # Verify handle child_index values are correct
        handles = [c for c in container_children if isinstance(c, SplitResizeHandle)]
        handle_indices = sorted(h.child_index for h in handles)
        assert handle_indices == [0, 1]


async def test_split_left_resize_handle_works(workspace: Path, py_file: Path):
    """Split left creates a resize handle with correct child_index."""
    from textual_code.widgets.split_resize_handle import SplitResizeHandle

    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_left()
        await pilot.wait_for_scheduled_animations()
        handles = app.main_view.query(SplitResizeHandle)
        assert len(handles) >= 1
        # The handle should have child_index=0
        assert handles.first(SplitResizeHandle).child_index == 0


# ── Group N — Focus After Tab Move ───────────────────────────────────────────


async def test_move_tab_focuses_destination_pane(
    workspace: Path, py_file: Path, py_file2: Path
):
    """action_move_editor_to_next_group focuses the destination pane and moved tab."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Open second file so left isn't empty after move
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        # Focus py_file tab
        pane_id = app.main_view._opened_files["left"][py_file]
        app.main_view.focus_pane(pane_id)
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        await app.main_view.action_move_editor_to_next_group()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        # py_file should now be in right split
        assert py_file in app.main_view._opened_files["right"]
        leaves = all_leaves(app.main_view._split_root)
        dest_leaf = leaves[-1]
        new_pane_id = app.main_view._opened_files["right"][py_file]
        assert_focus_on_leaf(app, app.main_view, dest_leaf, new_pane_id, "L→R move")


async def test_move_tab_focuses_moved_tab_when_split_collapses(
    workspace: Path, py_file: Path
):
    """Moving the last tab from one split collapses it; focus on the moved tab."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Split right: py_file in both
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        # Now move py_file from right to left (right has 1 tab, will collapse)
        assert app.main_view._active_split == "right"
        await app.main_view.action_move_editor_to_next_group()
        await pilot.wait_for_scheduled_animations()

        # Right split should have collapsed
        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 1, f"Expected 1 leaf after collapse, got {len(leaves)}"

        # Focus should be on the remaining leaf with the moved tab
        sole_leaf = leaves[0]
        # The moved tab's pane_id is for py_file
        moved_pane_id = sole_leaf.opened_files.get(py_file)
        assert moved_pane_id is not None

        # active_leaf_id should be the sole leaf
        assert app.main_view._active_leaf_id == sole_leaf.leaf_id
        # tc.active should be the moved tab
        tc = app.main_view.query_one(f"#{sole_leaf.leaf_id}", DraggableTabbedContent)
        assert tc.active == moved_pane_id


async def test_move_tab_directional_focuses_destination(
    workspace: Path, py_file: Path, py_file2: Path
):
    """action_move_editor_right focuses the destination split and moved tab."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Open second file so left isn't empty after move
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.wait_for_scheduled_animations()

        # Create right split
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        # Focus back to left, select py_file2
        leaves = all_leaves(app.main_view._split_root)
        left_leaf = leaves[0]
        app.main_view._set_active_leaf(left_leaf)
        await pilot.wait_for_scheduled_animations()
        py_file2_pane = left_leaf.opened_files[py_file2]
        tc_left = app.main_view.query_one(
            f"#{left_leaf.leaf_id}", DraggableTabbedContent
        )
        tc_left.active = py_file2_pane
        await pilot.wait_for_scheduled_animations()

        # Move tab right
        await app.main_view.action_move_editor_right()
        await pilot.wait_for_scheduled_animations()

        # Find dest leaf (right)
        leaves = all_leaves(app.main_view._split_root)
        dest_leaf = leaves[-1]
        new_pane_id = dest_leaf.opened_files.get(py_file2)
        assert new_pane_id is not None, "py_file2 should be in right leaf"
        assert_focus_on_leaf(
            app, app.main_view, dest_leaf, new_pane_id, "directional move right"
        )


async def test_move_tab_directional_noop_single_tab(workspace: Path, py_file: Path):
    """Directional move with a single tab in a single leaf is a no-op."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()

        leaves_before = all_leaves(app.main_view._split_root)
        assert len(leaves_before) == 1
        active_leaf_before = app.main_view._active_leaf_id

        # Attempt to move right (no-op: single tab, can't create split without
        # keeping the source non-empty)
        await app.main_view.action_move_editor_right()
        await pilot.wait_for_scheduled_animations()

        # Nothing should change
        leaves_after = all_leaves(app.main_view._split_root)
        assert len(leaves_after) == 1
        assert app.main_view._active_leaf_id == active_leaf_before


async def test_move_tab_duplicate_file_focuses_existing(
    workspace: Path, py_file: Path, py_file2: Path
):
    """When dest already has the same file, focus goes to existing pane."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        main = app.main_view

        # Open second file so left isn't empty after move
        await main.action_open_code_editor(path=py_file2)
        await pilot.wait_for_scheduled_animations()

        # Focus py_file so split_right copies it to the right split
        leaves = all_leaves(main._split_root)
        left_leaf = leaves[0]
        pane_id_pyfile = left_leaf.opened_files[py_file]
        tc_left = main.query_one(f"#{left_leaf.leaf_id}", DraggableTabbedContent)
        tc_left.active = pane_id_pyfile
        await pilot.wait_for_scheduled_animations()

        # Split right copies the active file (py_file) to right
        await main.action_split_right()
        # Windows: wait for split creation + file open to register
        await wait_for_condition(
            pilot,
            lambda: (
                "right" in main._opened_files and py_file in main._opened_files["right"]
            ),
            max_retries=50,
            msg="py_file not registered in right split after split_right",
        )

        # py_file now in both splits
        assert py_file in main._opened_files["right"]
        assert py_file in main._opened_files["left"]

        # Focus left, select py_file
        leaves = all_leaves(main._split_root)
        left_leaf = leaves[0]
        main._set_active_leaf(left_leaf)
        await pilot.wait_for_scheduled_animations()
        left_pane_id = main._opened_files["left"][py_file]
        tc_left = main.query_one(f"#{left_leaf.leaf_id}", DraggableTabbedContent)
        tc_left.active = left_pane_id
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for tab switch in split

        # Move py_file from left to right (duplicate)
        await main.action_move_editor_to_next_group()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for move + deduplication

        # Focus should be on the right split's existing py_file pane
        leaves = all_leaves(main._split_root)
        dest_leaf = leaves[-1]
        existing_pane_id = dest_leaf.opened_files.get(py_file)
        assert existing_pane_id is not None

        assert main._active_leaf_id == dest_leaf.leaf_id, (
            "active leaf should be dest leaf after duplicate move"
        )


# ── Group L — Cross-split focus updates Explorer & footer (#131) ─────────────


async def test_cross_split_focus_posts_active_file_changed(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Clicking editor in another split must post ActiveFileChanged (#131)."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Split right — both splits now have py_file
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2

        # Open py_file2 in the right split (active leaf after split_right)
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.wait_for_scheduled_animations()
        # TabActivated fires → Explorer now shows py_file2

        # Focus left editor (which has py_file)
        left_editor = app.main_view._get_active_code_editor_in_leaf(leaves[0])
        assert left_editor is not None
        left_editor.editor.focus()
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for cross-split focus change

        # Explorer must update to show the left file (py_file)
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        cursor_node = explorer.directory_tree.cursor_node
        assert cursor_node is not None
        assert cursor_node.data is not None
        assert cursor_node.data.path == py_file, (
            f"Explorer should show {py_file.name} but shows "
            f"{cursor_node.data.path.name}"
        )


async def test_cross_split_focus_syncs_footer(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Focusing editor in another split must sync footer path (#131)."""
    from textual_code.widgets.code_editor import CodeEditorFooter

    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Split right — both splits have py_file
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2

        # Open py_file2 in the right split (active after split_right)
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.wait_for_scheduled_animations()

        # Focus left editor (which has py_file)
        left_editor = app.main_view._get_active_code_editor_in_leaf(leaves[0])
        assert left_editor is not None
        left_editor.editor.focus()
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for cross-split focus + footer sync

        footer = app.main_view.query_one(CodeEditorFooter)
        assert footer.path == py_file, (
            f"Footer should show {py_file.name} but shows {footer.path}"
        )

        # Focus right editor (which has py_file2)
        right_editor = app.main_view._get_active_code_editor_in_leaf(leaves[1])
        assert right_editor is not None
        right_editor.editor.focus()
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for cross-split focus + footer sync

        # Footer must sync to right editor's file
        assert footer.path == py_file2, (
            f"Footer should show {py_file2.name} but shows {footer.path}"
        )


async def test_focus_next_group_updates_explorer(
    workspace: Path, py_file: Path, py_file2: Path
):
    """action_focus_next_group (F6) must update Explorer selection (#131)."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        # Open py_file2 in the right split
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.wait_for_scheduled_animations()

        # Right split is active, Explorer shows py_file2
        # Use action_focus_next_group to cycle back to left split
        app.main_view.action_focus_next_group()
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for focus group + explorer

        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        cursor_node = explorer.directory_tree.cursor_node
        assert cursor_node is not None
        assert cursor_node.data is not None
        assert cursor_node.data.path == py_file, (
            f"Explorer should show {py_file.name} after F6 but shows "
            f"{cursor_node.data.path.name}"
        )


async def test_same_leaf_focus_no_extra_active_file_changed(
    workspace: Path, py_file: Path, monkeypatch: pytest.MonkeyPatch
):
    """Focusing within the same leaf must not post ActiveFileChanged (#131)."""
    from textual_code.widgets.main_view import MainView

    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_split_right()
        await pilot.wait_for_scheduled_animations()

        messages: list[MainView.ActiveFileChanged] = []
        original_handler = app.main_view.post_message

        def tracking_post_message(msg: Message) -> bool:
            if isinstance(msg, MainView.ActiveFileChanged):
                messages.append(msg)
            return original_handler(msg)

        monkeypatch.setattr(app.main_view, "post_message", tracking_post_message)

        # Focus the editor in the already-active leaf
        leaves = all_leaves(app.main_view._split_root)
        active_leaf = next(
            lf for lf in leaves if lf.leaf_id == app.main_view._active_leaf_id
        )
        editor = app.main_view._get_active_code_editor_in_leaf(active_leaf)
        assert editor is not None
        editor.editor.focus()
        await pilot.wait_for_scheduled_animations()

        assert len(messages) == 0, (
            f"Expected no ActiveFileChanged for same-leaf focus, got {len(messages)}"
        )
