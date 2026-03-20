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

from tests.conftest import assert_focus_on_leaf, make_app
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
        await pilot.pause()
        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 1


async def test_split_not_visible_initially(workspace: Path, py_file: Path):
    """_split_visible is False on startup."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.main_view._split_visible is False


async def test_active_split_initially_left(workspace: Path, py_file: Path):
    """_active_split is 'left' on startup."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.main_view._active_split == "left"


async def test_initial_file_tracked_in_left_split(workspace: Path, py_file: Path):
    """File opened on startup is in the left split's tracking."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert py_file in app.main_view._opened_files["left"]


async def test_right_pane_ids_initially_empty(workspace: Path, py_file: Path):
    """Right split has no open panes on startup."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.main_view._pane_ids["right"] == set()


# ── Group B — Split Right ────────────────────────────────────────────────────────


async def test_split_right_creates_second_leaf(workspace: Path, py_file: Path):
    """action_split_right creates a second leaf."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2


async def test_split_right_sets_split_visible(workspace: Path, py_file: Path):
    """action_split_right sets _split_visible to True."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        assert app.main_view._split_visible is True


async def test_split_right_opens_same_file(workspace: Path, py_file: Path):
    """action_split_right opens the current file in the right panel."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        assert py_file in app.main_view._opened_files["right"]


async def test_split_right_sets_active_split_to_right(workspace: Path, py_file: Path):
    """action_split_right switches focus to the right split."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        assert app.main_view._active_split == "right"


async def test_split_right_with_no_file(workspace: Path):
    """action_split_right with no open file opens an empty editor in right."""
    app = make_app(workspace, open_file=None, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        assert app.main_view._split_visible is True
        assert len(app.main_view._pane_ids["right"]) == 1


async def test_split_right_twice_creates_three_way_split(
    workspace: Path, py_file: Path
):
    """A second action_split_right creates a third split (recursive splitting)."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(180, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        leaf_count_after_first = len(all_leaves(app.main_view._split_root))
        assert leaf_count_after_first == 2

        # Switch back to left and split right again
        app.main_view._active_split = "left"
        await app.main_view.action_split_right()
        await pilot.pause()

        # Now we should have 3 leaves
        assert app.main_view._split_visible is True
        assert len(all_leaves(app.main_view._split_root)) == 3


# ── Group C — Focus Navigation ───────────────────────────────────────────────────


async def test_focus_left_split_updates_active_split(workspace: Path, py_file: Path):
    """action_focus_left_split sets _active_split to 'left'."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        assert app.main_view._active_split == "right"
        app.main_view.action_focus_left_split()
        await pilot.pause()
        assert app.main_view._active_split == "left"


async def test_focus_right_split_when_open(workspace: Path, py_file: Path):
    """action_focus_right_split switches to right when split is visible."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        app.main_view.action_focus_left_split()
        await pilot.pause()
        assert app.main_view._active_split == "left"
        app.main_view.action_focus_right_split()
        await pilot.pause()
        assert app.main_view._active_split == "right"


async def test_focus_right_split_noop_when_closed(workspace: Path, py_file: Path):
    """action_focus_right_split is a no-op when no split is open."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.main_view._active_split == "left"
        app.main_view.action_focus_right_split()
        await pilot.pause()
        assert app.main_view._active_split == "left"


# ── Group D — Close Split ────────────────────────────────────────────────────────


async def test_close_split_returns_to_single_leaf(workspace: Path, py_file: Path):
    """action_close_split removes the active split and returns to single leaf."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        await app.main_view.action_close_split()
        await pilot.pause()
        await pilot.pause()
        assert app.main_view._split_visible is False


async def test_close_split_sets_split_visible_false(workspace: Path, py_file: Path):
    """action_close_split sets _split_visible to False."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        await app.main_view.action_close_split()
        await pilot.pause()
        await pilot.pause()
        assert app.main_view._split_visible is False


async def test_close_split_focuses_left(workspace: Path, py_file: Path):
    """action_close_split sets _active_split back to 'left'."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        await app.main_view.action_close_split()
        await pilot.pause()
        await pilot.pause()
        assert app.main_view._active_split == "left"


async def test_close_split_clears_right_pane_ids(workspace: Path, py_file: Path):
    """action_close_split removes all right pane tracking."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        assert len(app.main_view._pane_ids["right"]) > 0
        await app.main_view.action_close_split()
        await pilot.pause()
        await pilot.pause()
        assert app.main_view._pane_ids["right"] == set()


async def test_close_split_noop_when_not_open(workspace: Path, py_file: Path):
    """action_close_split does nothing when no split is visible."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert not app.main_view._split_visible
        await app.main_view.action_close_split()  # should not raise
        await pilot.pause()
        assert app.main_view._active_split == "left"


async def test_auto_close_split_when_last_right_tab_closed(
    workspace: Path, py_file: Path
):
    """Closing the last tab in the right split auto-hides the right panel."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        assert app.main_view._split_visible is True
        # Close the right editor
        leaves = all_leaves(app.main_view._split_root)
        right_leaf = leaves[1]
        right_editor = app.main_view._get_active_code_editor_in_leaf(right_leaf)
        assert right_editor is not None
        right_editor.action_close()
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()
        # Right split should now be hidden (auto-closed)
        assert app.main_view._split_visible is False
        assert app.main_view._active_split == "left"


# ── Group E — Split Independence ─────────────────────────────────────────────────


async def test_open_file_goes_to_active_split(workspace: Path, py_file: Path):
    """Opening a file targets the active split."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        # File is in left split
        assert py_file in app.main_view._opened_files["left"]
        assert py_file not in app.main_view._opened_files.get("right", {})


async def test_same_file_can_be_open_in_both_splits(workspace: Path, py_file: Path):
    """The same file can be independently open in both splits."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
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
        await pilot.pause()
        left_pane_id = app.main_view._opened_files["left"][py_file]
        assert app.main_view._split_of_pane(left_pane_id) == "left"

        await app.main_view.action_split_right()
        await pilot.pause()
        right_pane_id = app.main_view._opened_files["right"][py_file]
        assert app.main_view._split_of_pane(right_pane_id) == "right"


async def test_split_of_pane_unknown_returns_none(workspace: Path):
    """_split_of_pane returns None for an unknown pane_id."""
    app = make_app(workspace, open_file=None, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.main_view._split_of_pane("nonexistent-pane-id") is None


async def test_opened_pane_ids_combines_both_splits(workspace: Path, py_file: Path):
    """opened_pane_ids returns pane IDs from both splits combined."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        count_before = len(app.main_view.opened_pane_ids)
        await app.main_view.action_split_right()
        await pilot.pause()
        count_after = len(app.main_view.opened_pane_ids)
        assert count_after == count_before + 1


async def test_close_right_tab_removes_from_right_tracking(
    workspace: Path, py_file: Path
):
    """Closing a tab in the right split removes it from _pane_ids['right']."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        right_pane_id = app.main_view._opened_files["right"][py_file]
        assert right_pane_id in app.main_view._pane_ids["right"]
        leaves = all_leaves(app.main_view._split_root)
        right_editor = app.main_view._get_active_code_editor_in_leaf(leaves[1])
        right_editor.action_close()
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()
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
        await pilot.pause()
        await pilot.press("ctrl+backslash")
        await pilot.pause()
        assert app.main_view._split_visible is True


async def test_split_right_cmd_no_file(workspace: Path):
    """action_split_right_cmd with no open editor still opens empty right split."""
    app = make_app(workspace, open_file=None, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Should not raise
        app.action_split_right_cmd()
        await pilot.pause()


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
        await pilot.pause()
        # Open a second file so left doesn't become empty after move
        app.main_view._active_split = "left"
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.pause()
        await pilot.pause()
        assert py_file in app.main_view._opened_files["left"]

        # Focus the py_file tab before moving
        app.main_view._active_split = "left"
        pane_id = app.main_view._opened_files["left"][py_file]
        app.main_view.focus_pane(pane_id)
        await pilot.pause()
        await pilot.pause()

        await app.main_view.action_move_tab_to_other_split()
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()

        # File is now in right split and removed from left split
        assert py_file in app.main_view._opened_files["right"]
        assert py_file not in app.main_view._opened_files["left"]


async def test_move_tab_right_to_left(workspace: Path, py_file: Path):
    """Moving a tab from right split places it in the left split."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        # First open a split and move to right
        await app.main_view.action_split_right()
        await pilot.pause()
        assert app.main_view._active_split == "right"
        assert py_file in app.main_view._opened_files["right"]

        # Now move back to left
        await app.main_view.action_move_tab_to_other_split()
        await pilot.pause()

        assert py_file in app.main_view._opened_files["left"]
        assert py_file not in app.main_view._opened_files.get("right", {})


async def test_move_tab_creates_right_split(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Moving a tab to the right auto-creates the right split if not open."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Open a second file so left doesn't become empty after move
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.pause()
        await pilot.pause()
        assert app.main_view._split_visible is False

        # Focus py_file tab before moving
        pane_id = app.main_view._opened_files["left"][py_file]
        app.main_view.focus_pane(pane_id)
        await pilot.pause()
        await pilot.pause()

        await app.main_view.action_move_tab_to_other_split()
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()

        assert app.main_view._split_visible is True


async def test_move_tab_transfers_unsaved_content(workspace: Path, py_file: Path):
    """Unsaved content is preserved when a tab is moved to the other split."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Edit the file without saving
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.replace_editor_text("unsaved content here")
        await pilot.pause()
        assert editor.text == "unsaved content here"

        await app.main_view.action_move_tab_to_other_split()
        await pilot.pause()

        # The destination editor should have the unsaved content
        leaves = all_leaves(app.main_view._split_root)
        right_leaf = leaves[-1]
        new_editor = app.main_view._get_active_code_editor_in_leaf(right_leaf)
        assert new_editor is not None
        assert new_editor.text == "unsaved content here"


async def test_move_tab_no_op_without_editor(workspace: Path):
    """action_move_tab_to_other_split is a no-op when no editor is open."""
    app = make_app(workspace, open_file=None, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Should not raise — no editor open
        await app.main_view.action_move_tab_to_other_split()
        await pilot.pause()
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
        await pilot.pause()
        # Open a second file so left doesn't become empty after drag
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.pause()
        assert app.main_view._split_visible is False

        leaves = all_leaves(app.main_view._split_root)
        left_tc = app.main_view.query_one(
            f"#{leaves[0].leaf_id}", DraggableTabbedContent
        )
        pane_id = leaves[0].opened_files[py_file]
        left_tc.post_message(
            DraggableTabbedContent.TabMovedToOtherSplit(pane_id, None, False)
        )
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()

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
        await pilot.pause()
        # Open second file in left split
        await app.main_view.open_code_editor_pane(py_file2)
        await pilot.pause()
        assert len(app.main_view._pane_ids["left"]) == 2

        leaves = all_leaves(app.main_view._split_root)
        left_tc = app.main_view.query_one(
            f"#{leaves[0].leaf_id}", DraggableTabbedContent
        )
        pane_id = leaves[0].opened_files[py_file]
        left_tc.post_message(
            DraggableTabbedContent.TabMovedToOtherSplit(pane_id, None, False)
        )
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()

        assert app.main_view._split_visible is True
        # py_file moved to right
        assert py_file in app.main_view._opened_files["right"]
        # py_file2 still in left
        assert py_file2 in app.main_view._opened_files["left"]


# ── Group I — DescendantFocus updates active leaf ──────────────────────────────


async def test_descendant_focus_updates_active_split(workspace: Path, py_file: Path):
    """Focusing editor content (not tab click) must update _active_split."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)

        # Focus left editor first (to move DOM focus away from right)
        left_editor = app.main_view._get_active_code_editor_in_leaf(leaves[0])
        assert left_editor is not None
        left_editor.editor.focus()
        await pilot.pause()
        assert app.main_view._active_split == "left"

        # Focus right editor content directly
        right_editor = app.main_view._get_active_code_editor_in_leaf(leaves[1])
        assert right_editor is not None
        right_editor.editor.focus()
        await pilot.pause()

        # _active_split must update to "right"
        assert app.main_view._active_split == "right"


async def test_ctrl_w_closes_focused_split_editor(workspace: Path, py_file: Path):
    """Ctrl+W closes the editor in the focused split, not the _active_split one."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        assert len(app.main_view._pane_ids["left"]) == 1
        assert len(app.main_view._pane_ids["right"]) == 1

        # Force _active_split to "left" while focus is on right editor content
        app.main_view._active_split = "left"
        leaves = all_leaves(app.main_view._split_root)
        right_editor = app.main_view._get_active_code_editor_in_leaf(leaves[1])
        assert right_editor is not None
        right_editor.editor.focus()
        await pilot.pause()

        # Ctrl+W should close the right editor (the focused one)
        await pilot.press("ctrl+w")
        await pilot.pause()

        assert len(app.main_view._pane_ids["left"]) == 1  # left untouched
        assert len(app.main_view._pane_ids.get("right", set())) == 0  # right closed


async def test_ctrl_w_last_right_tab_auto_closes_split(workspace: Path, py_file: Path):
    """Ctrl+W on the last right tab auto-hides the right split."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        assert app.main_view._split_visible is True

        # Simulate active split being left while focus is actually in right
        app.main_view._active_split = "left"
        leaves = all_leaves(app.main_view._split_root)
        right_editor = app.main_view._get_active_code_editor_in_leaf(leaves[1])
        assert right_editor is not None
        right_editor.editor.focus()
        await pilot.pause()

        # Ctrl+W on the last right tab → split must auto-close
        await pilot.press("ctrl+w")
        await pilot.pause()

        assert app.main_view._split_visible is False
        assert app.main_view._active_split == "left"


# ── Group J — Live Sync Between Split Editors ───────────────────────────────────


async def test_split_editors_sync_live_edits(workspace: Path, py_file: Path):
    """Editing in the left editor syncs text to the right editor in real time."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        left_editor = app.main_view._get_active_code_editor_in_leaf(leaves[0])
        right_editor = app.main_view._get_active_code_editor_in_leaf(leaves[1])
        assert left_editor is not None
        assert right_editor is not None

        new_text = "# synced!\nprint('live')\n"
        left_editor.replace_editor_text(new_text)
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()

        assert right_editor.text == new_text


async def test_split_editors_sync_on_save(workspace: Path, py_file: Path):
    """Saving the left editor updates initial_text and _file_mtime in sibling editor."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        left_editor = app.main_view._get_active_code_editor_in_leaf(leaves[0])
        right_editor = app.main_view._get_active_code_editor_in_leaf(leaves[1])
        assert left_editor is not None
        assert right_editor is not None

        new_text = "# saved content\n"
        left_editor.replace_editor_text(new_text)
        await pilot.pause()
        left_editor.action_save()
        await pilot.pause()

        assert right_editor.initial_text == new_text
        assert right_editor._file_mtime == left_editor._file_mtime


async def test_find_replace_bar_focus_keeps_active_split(
    workspace: Path, py_file: Path
):
    """Opening find bar inside right split keeps _active_split as 'right'."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)

        # Focus left editor first (move DOM focus away from right)
        left_editor = app.main_view._get_active_code_editor_in_leaf(leaves[0])
        assert left_editor is not None
        left_editor.editor.focus()
        await pilot.pause()
        assert app.main_view._active_split == "left"

        # Focus right editor
        right_editor = app.main_view._get_active_code_editor_in_leaf(leaves[1])
        assert right_editor is not None
        right_editor.editor.focus()
        await pilot.pause()

        # Open find bar — focus moves to find input (still inside split_right)
        await pilot.press("ctrl+f")
        await pilot.pause()

        # _active_split must still be "right"
        assert app.main_view._active_split == "right"


# ── Group K — Split Left ─────────────────────────────────────────────────────


async def test_split_left_creates_second_leaf(workspace: Path, py_file: Path):
    """action_split_left creates a second leaf."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_left()
        await pilot.pause()
        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2


async def test_split_left_new_leaf_is_first(workspace: Path, py_file: Path):
    """action_split_left places the new leaf at index 0 (left side)."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        original_leaf_id = all_leaves(app.main_view._split_root)[0].leaf_id
        await app.main_view.action_split_left()
        await pilot.pause()
        leaves = all_leaves(app.main_view._split_root)
        # The new leaf should be first; original should be second
        assert leaves[1].leaf_id == original_leaf_id
        assert leaves[0].leaf_id != original_leaf_id


async def test_split_left_opens_same_file(workspace: Path, py_file: Path):
    """action_split_left opens the current file in the new (left) panel."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_left()
        await pilot.pause()
        # The new leaf (index 0) should have the file open
        leaves = all_leaves(app.main_view._split_root)
        new_leaf = leaves[0]
        assert py_file in new_leaf.opened_files


# ── Group L — Split Up ───────────────────────────────────────────────────────


async def test_split_up_creates_second_leaf(workspace: Path, py_file: Path):
    """action_split_up creates a second leaf."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_up()
        await pilot.pause()
        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2


async def test_split_up_new_leaf_is_first(workspace: Path, py_file: Path):
    """action_split_up places the new leaf at index 0 (top)."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        original_leaf_id = all_leaves(app.main_view._split_root)[0].leaf_id
        await app.main_view.action_split_up()
        await pilot.pause()
        leaves = all_leaves(app.main_view._split_root)
        assert leaves[1].leaf_id == original_leaf_id
        assert leaves[0].leaf_id != original_leaf_id


async def test_split_up_direction_is_vertical(workspace: Path, py_file: Path):
    """Split up produces a vertical root branch."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_up()
        await pilot.pause()
        root = app.main_view._split_root
        assert isinstance(root, BranchNode)
        assert root.direction == "vertical"


# ── Group M — Split Left Edge Cases ──────────────────────────────────────────


async def test_split_left_twice_creates_three_leaves(workspace: Path, py_file: Path):
    """Two split_left actions from the same leaf create 3 leaves."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(180, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_left()
        await pilot.pause()
        assert len(all_leaves(app.main_view._split_root)) == 2

        await app.main_view.action_split_left()
        await pilot.pause()
        assert len(all_leaves(app.main_view._split_root)) == 3


async def test_split_left_then_close(workspace: Path, py_file: Path):
    """split_left then close_split returns to 1 leaf."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_left()
        await pilot.pause()
        assert app.main_view._split_visible is True
        await app.main_view.action_close_split()
        await pilot.pause()
        await pilot.pause()
        assert app.main_view._split_visible is False
        assert len(all_leaves(app.main_view._split_root)) == 1


async def test_split_right_then_split_left(workspace: Path, py_file: Path):
    """split_right then split_left creates 3 leaves in correct order."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(180, 30)) as pilot:
        await pilot.pause()
        original_leaf_id = all_leaves(app.main_view._split_root)[0].leaf_id

        await app.main_view.action_split_right()
        await pilot.pause()
        leaves = all_leaves(app.main_view._split_root)
        right_leaf_id = leaves[1].leaf_id

        # Now split left from the right leaf (which is active)
        await app.main_view.action_split_left()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 3
        # Order: original, new_left_of_right, right
        assert leaves[0].leaf_id == original_leaf_id
        assert leaves[2].leaf_id == right_leaf_id


async def test_split_left_resize_handle_works(workspace: Path, py_file: Path):
    """Split left creates a resize handle with correct child_index."""
    from textual_code.widgets.split_resize_handle import SplitResizeHandle

    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_split_left()
        await pilot.pause()
        handles = app.main_view.query(SplitResizeHandle)
        assert len(handles) >= 1
        # The handle should have child_index=0
        assert handles.first(SplitResizeHandle).child_index == 0


# ── Group N — Focus After Tab Move ───────────────────────────────────────────


async def test_move_tab_focuses_destination_pane(
    workspace: Path, py_file: Path, py_file2: Path
):
    """action_move_tab_to_other_split focuses the destination pane and moved tab."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Open second file so left isn't empty after move
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.pause()
        await pilot.pause()

        # Focus py_file tab
        pane_id = app.main_view._opened_files["left"][py_file]
        app.main_view.focus_pane(pane_id)
        await pilot.pause()
        await pilot.pause()

        await app.main_view.action_move_tab_to_other_split()
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()

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
        await pilot.pause()
        # Split right: py_file in both
        await app.main_view.action_split_right()
        await pilot.pause()

        # Now move py_file from right to left (right has 1 tab, will collapse)
        assert app.main_view._active_split == "right"
        await app.main_view.action_move_tab_to_other_split()
        await pilot.pause()

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
    """action_move_tab_right focuses the destination split and moved tab."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Open second file so left isn't empty after move
        await app.main_view.action_open_code_editor(path=py_file2)
        await pilot.pause()

        # Create right split
        await app.main_view.action_split_right()
        await pilot.pause()

        # Focus back to left, select py_file2
        leaves = all_leaves(app.main_view._split_root)
        left_leaf = leaves[0]
        app.main_view._set_active_leaf(left_leaf)
        await pilot.pause()
        py_file2_pane = left_leaf.opened_files[py_file2]
        tc_left = app.main_view.query_one(
            f"#{left_leaf.leaf_id}", DraggableTabbedContent
        )
        tc_left.active = py_file2_pane
        await pilot.pause()

        # Move tab right
        await app.main_view.action_move_tab_right()
        await pilot.pause()

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
        await pilot.pause()

        leaves_before = all_leaves(app.main_view._split_root)
        assert len(leaves_before) == 1
        active_leaf_before = app.main_view._active_leaf_id

        # Attempt to move right (no-op: single tab, can't create split without
        # keeping the source non-empty)
        await app.main_view.action_move_tab_right()
        await pilot.pause()

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
        await pilot.pause()
        main = app.main_view

        # Open second file so left isn't empty after move
        await main.action_open_code_editor(path=py_file2)
        await pilot.pause()

        # Focus py_file so split_right copies it to the right split
        leaves = all_leaves(main._split_root)
        left_leaf = leaves[0]
        pane_id_pyfile = left_leaf.opened_files[py_file]
        tc_left = main.query_one(f"#{left_leaf.leaf_id}", DraggableTabbedContent)
        tc_left.active = pane_id_pyfile
        await pilot.pause()

        # Split right copies the active file (py_file) to right
        await main.action_split_right()
        await pilot.pause()

        # py_file now in both splits
        assert py_file in main._opened_files["right"]
        assert py_file in main._opened_files["left"]

        # Focus left, select py_file
        leaves = all_leaves(main._split_root)
        left_leaf = leaves[0]
        main._set_active_leaf(left_leaf)
        await pilot.pause()
        left_pane_id = main._opened_files["left"][py_file]
        tc_left = main.query_one(f"#{left_leaf.leaf_id}", DraggableTabbedContent)
        tc_left.active = left_pane_id
        await pilot.pause()

        # Move py_file from left to right (duplicate)
        await main.action_move_tab_to_other_split()
        await pilot.pause()
        await pilot.pause()
        await pilot.pause()

        # Focus should be on the right split's existing py_file pane
        leaves = all_leaves(main._split_root)
        dest_leaf = leaves[-1]
        existing_pane_id = dest_leaf.opened_files.get(py_file)
        assert existing_pane_id is not None

        assert main._active_leaf_id == dest_leaf.leaf_id, (
            "active leaf should be dest leaf after duplicate move"
        )
