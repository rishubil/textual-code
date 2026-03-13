"""
Tests for cross-split tab drag: dragging a tab from one split to the other.

Uses the tree-based split model.
"""

from pathlib import Path

import pytest
from textual.widgets._tabbed_content import ContentTab, ContentTabs

from tests.conftest import make_app
from textual_code.widgets.code_editor import CodeEditor
from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent
from textual_code.widgets.split_tree import all_leaves


def _tab_order(dtc: DraggableTabbedContent) -> list[str]:
    """Return pane IDs in current tab display order."""
    content_tabs = dtc.get_child_by_type(ContentTabs)
    return [
        ContentTab.sans_prefix(t.id) for t in content_tabs.query(ContentTab) if t.id
    ]


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


# ── Helper tests via _move_pane_to_split ─────────────────────────────────────


async def test_drag_left_to_right_moves_pane(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Moving a pane from left to right appears in right _pane_ids."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        main = app.main_view

        # Open a second file in left so it doesn't become empty after move
        await main.action_open_code_editor(path=py_file2)
        await pilot.pause()

        # Open right split
        await main.action_split_right()
        await pilot.pause()

        # Focus left split to select source pane
        main._active_split = "left"
        source_pane_id = main._opened_files["left"][py_file]

        # Move source pane to right split
        new_pane_id = await main._move_pane_to_split(source_pane_id, "right")
        await pilot.pause()

        assert new_pane_id is not None
        assert new_pane_id in main._pane_ids["right"]
        assert source_pane_id not in main._pane_ids["left"]


async def test_drag_right_to_left_moves_pane(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Moving a pane from right to left appears in left _pane_ids."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        main = app.main_view

        # Open right split with a different file
        await main.action_split_right()
        await pilot.pause()
        main._active_split = "right"
        await main.action_open_code_editor(path=py_file2)
        await pilot.pause()

        right_panes = [
            p
            for p in main._pane_ids["right"]
            if main._opened_files["right"].get(py_file2) == p
        ]
        assert right_panes, "Expected py_file2 pane in right split"
        source_pane_id = right_panes[0]

        # Move right pane to left
        new_pane_id = await main._move_pane_to_split(source_pane_id, "left")
        await pilot.pause()

        assert new_pane_id is not None
        assert new_pane_id in main._pane_ids["left"]
        assert source_pane_id not in main._pane_ids["right"]


async def test_drag_cross_split_preserves_unsaved_content(
    workspace: Path, py_file: Path
):
    """Unsaved content in the editor survives a cross-split move."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        main = app.main_view

        # Modify the editor without saving
        leaves = all_leaves(main._split_root)
        source_pane_id = list(leaves[0].pane_ids)[0]
        tc = main.query_one(f"#{leaves[0].leaf_id}")
        pane = tc.get_pane(source_pane_id)
        editor = pane.query_one(CodeEditor)
        editor.replace_editor_text("unsaved content")
        await pilot.pause()

        # Move to right split
        new_pane_id = await main._move_pane_to_split(source_pane_id, "right")
        await pilot.pause()

        assert new_pane_id is not None
        dest_leaves = all_leaves(main._split_root)
        dest_leaf = dest_leaves[-1]
        dest_tc = main.query_one(f"#{dest_leaf.leaf_id}")
        new_editor = dest_tc.get_pane(new_pane_id).query_one(CodeEditor)
        assert new_editor.text == "unsaved content"
        assert new_editor.text != new_editor.initial_text


async def test_drag_cross_split_closes_right_split_when_empty(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Moving the last tab from right to left collapses the right split."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        main = app.main_view

        # Open right split with one file (py_file2)
        await main.action_split_right()
        await pilot.pause()
        main._active_split = "right"
        await main.action_open_code_editor(path=py_file2)
        await pilot.pause()

        # Close the py_file copy that action_split_right opened (keep only py_file2)
        py_file_right_id = main._opened_files["right"].get(py_file)
        if py_file_right_id:
            await main.action_close_code_editor(py_file_right_id)
            await pilot.pause()

        # Confirm right split has exactly one pane (py_file2)
        right_pane_id = main._opened_files["right"].get(py_file2)
        assert right_pane_id is not None
        assert len(main._pane_ids["right"]) == 1

        # Move that pane to left split via helper
        new_pane_id = await main._move_pane_to_split(right_pane_id, "left")
        await pilot.pause()

        assert new_pane_id is not None
        assert main._split_visible is False


async def test_drag_cross_split_duplicate_file_focuses_existing(
    workspace: Path, py_file: Path, py_file2: Path
):
    """If the file is already open in the destination split, don't duplicate it."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        main = app.main_view

        # Open a second file in left so it doesn't become empty after move
        await main.action_open_code_editor(path=py_file2)
        await pilot.pause()

        # Open same file in right split too
        await main.action_split_right()
        await pilot.pause()
        main._active_split = "right"
        await main.action_open_code_editor(path=py_file)
        await pilot.pause()

        right_tab_count_before = len(main._pane_ids["right"])

        left_pane_id = main._opened_files["left"].get(py_file)
        assert left_pane_id is not None

        # Try to move left pane (py_file) to right, but py_file already open there
        new_pane_id = await main._move_pane_to_split(left_pane_id, "right")
        await pilot.pause()

        # Source pane closed, but no new pane added
        assert len(main._pane_ids["right"]) == right_tab_count_before
        # Should focus existing pane
        leaves = all_leaves(main._split_root)
        right_tc = main.query_one(f"#{leaves[-1].leaf_id}")
        assert right_tc.active == new_pane_id


# ── E2E drag test ─────────────────────────────────────────────────────────────


async def test_e2e_drag_tab_left_to_right(
    workspace: Path, py_file: Path, py_file2: Path
):
    """E2E: drag a tab from left split into right split's tab bar."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        main = app.main_view

        # Open a second file in the left split so the split doesn't become empty
        await main.action_open_code_editor(path=py_file2)
        await pilot.pause()

        # Open right split (any file)
        await main.action_split_right()
        await pilot.pause()

        # Right split should now be visible and have a tab
        assert main._split_visible is True
        right_tab_count_before = len(main._pane_ids["right"])
        left_tab_count_before = len(main._pane_ids["left"])

        # Get the first tab in left split (py_file)
        leaves = all_leaves(main._split_root)
        left_dtc = main.query_one(f"#{leaves[0].leaf_id}", DraggableTabbedContent)
        right_dtc = main.query_one(f"#{leaves[1].leaf_id}", DraggableTabbedContent)

        left_tabs_widget = left_dtc.get_child_by_type(ContentTabs)
        left_tabs = list(left_tabs_widget.query(ContentTab))
        right_tabs_widget = right_dtc.get_child_by_type(ContentTabs)
        right_tabs = list(right_tabs_widget.query(ContentTab))

        assert left_tabs, "Expected tabs in left split"
        assert right_tabs, "Expected tabs in right split"

        drag_tab = left_tabs[0]
        drop_tab = right_tabs[0]

        drag_region = drag_tab.region
        drop_region = drop_tab.region

        drag_x = drag_region.x + drag_region.width // 2
        drag_y = drag_region.y + drag_region.height // 2
        drop_x = drop_region.x + drop_region.width // 2
        drop_y = drop_region.y + drop_region.height // 2

        drag_offset = (drag_x - left_dtc.region.x, drag_y - left_dtc.region.y)
        drop_screen = (drop_x, drop_y)

        # mouse_down on first left tab
        await pilot.mouse_down(left_dtc, offset=drag_offset)
        await pilot.pause()

        # hover within left_dtc to exceed drag threshold and trigger capture_mouse()
        second_left_tab = left_tabs[1] if len(left_tabs) > 1 else left_tabs[0]
        intermediate_x = second_left_tab.region.x + second_left_tab.region.width // 2
        intermediate_y = second_left_tab.region.y + second_left_tab.region.height // 2
        intermediate_offset = (
            intermediate_x - left_dtc.region.x,
            intermediate_y - left_dtc.region.y,
        )
        await pilot.hover(left_dtc, offset=intermediate_offset)
        await pilot.pause()

        assert left_dtc._dragging, (
            "Expected _dragging to be True after threshold exceeded"
        )

        # mouse_up at the screen position of the right split tab
        drop_offset_from_left = (
            drop_screen[0] - left_dtc.region.x,
            drop_screen[1] - left_dtc.region.y,
        )
        await pilot.mouse_up(left_dtc, offset=drop_offset_from_left)
        await pilot.pause()
        await pilot.pause()

        # Right split should have gained a tab; left split unchanged or lost one
        assert (
            len(main._pane_ids["right"]) > right_tab_count_before
            or len(main._pane_ids["left"]) < left_tab_count_before
        )
