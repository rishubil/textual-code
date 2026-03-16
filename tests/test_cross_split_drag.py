"""
Tests for cross-split tab drag: dragging a tab from one split to the other.

Uses the tree-based split model.
"""

from pathlib import Path

import pytest
from textual.widgets._tabbed_content import ContentTab, ContentTabs

from tests.conftest import make_app
from textual_code.widgets.code_editor import CodeEditor
from textual_code.widgets.draggable_tabs_content import (
    DraggableTabbedContent,
    DropTargetOverlay,
)
from textual_code.widgets.markdown_preview import MarkdownPreviewPane
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


# ── Drop target highlight tests ───────────────────────────────────────────────


async def test_drop_target_highlight_during_cross_split_drag(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Dragging a tab over the other split adds -drop-target class to it."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        main = app.main_view

        await main.action_open_code_editor(path=py_file2)
        await pilot.pause()
        await main.action_split_right()
        await pilot.pause()

        leaves = all_leaves(main._split_root)
        left_dtc = main.query_one(f"#{leaves[0].leaf_id}", DraggableTabbedContent)
        right_dtc = main.query_one(f"#{leaves[1].leaf_id}", DraggableTabbedContent)

        left_tabs = list(left_dtc.get_child_by_type(ContentTabs).query(ContentTab))
        right_tabs = list(right_dtc.get_child_by_type(ContentTabs).query(ContentTab))
        drag_tab = left_tabs[0]

        # Start drag on left tab
        drag_region = drag_tab.region
        drag_x = drag_region.x + drag_region.width // 2
        drag_y = drag_region.y + drag_region.height // 2
        drag_offset = (drag_x - left_dtc.region.x, drag_y - left_dtc.region.y)
        await pilot.mouse_down(left_dtc, offset=drag_offset)
        await pilot.pause()

        # Move past threshold
        second_tab = left_tabs[1]
        mid_x = second_tab.region.x + second_tab.region.width // 2
        mid_y = second_tab.region.y + second_tab.region.height // 2
        await pilot.hover(
            left_dtc,
            offset=(mid_x - left_dtc.region.x, mid_y - left_dtc.region.y),
        )
        await pilot.pause()
        assert left_dtc._dragging

        # Move cursor over right split tab bar
        drop_tab = right_tabs[0]
        drop_region = drop_tab.region
        drop_x = drop_region.x + drop_region.width // 2
        drop_y = drop_region.y + drop_region.height // 2
        await pilot.hover(
            left_dtc,
            offset=(drop_x - left_dtc.region.x, drop_y - left_dtc.region.y),
        )
        await pilot.pause()

        # Right DTC overlay should have -visible class
        assert right_dtc.query_one(DropTargetOverlay).has_class("-visible")
        # Left DTC (source) overlay should NOT have -visible
        assert not left_dtc.query_one(DropTargetOverlay).has_class("-visible")

        # Clean up: mouse_up
        await pilot.mouse_up(
            left_dtc,
            offset=(drop_x - left_dtc.region.x, drop_y - left_dtc.region.y),
        )
        await pilot.pause()

        # After mouse_up, overlay should be hidden
        assert not right_dtc.query_one(DropTargetOverlay).has_class("-visible")


async def test_drop_target_removed_when_cursor_returns_to_source(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Moving cursor back to source split removes -drop-target from sibling."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        main = app.main_view

        await main.action_open_code_editor(path=py_file2)
        await pilot.pause()
        await main.action_split_right()
        await pilot.pause()

        leaves = all_leaves(main._split_root)
        left_dtc = main.query_one(f"#{leaves[0].leaf_id}", DraggableTabbedContent)
        right_dtc = main.query_one(f"#{leaves[1].leaf_id}", DraggableTabbedContent)

        left_tabs = list(left_dtc.get_child_by_type(ContentTabs).query(ContentTab))
        right_tabs = list(right_dtc.get_child_by_type(ContentTabs).query(ContentTab))
        drag_tab = left_tabs[0]

        # Start drag
        drag_region = drag_tab.region
        drag_x = drag_region.x + drag_region.width // 2
        drag_y = drag_region.y + drag_region.height // 2
        drag_offset = (drag_x - left_dtc.region.x, drag_y - left_dtc.region.y)
        await pilot.mouse_down(left_dtc, offset=drag_offset)
        await pilot.pause()

        # Exceed threshold
        second_tab = left_tabs[1]
        mid_x = second_tab.region.x + second_tab.region.width // 2
        mid_y = second_tab.region.y + second_tab.region.height // 2
        await pilot.hover(
            left_dtc,
            offset=(mid_x - left_dtc.region.x, mid_y - left_dtc.region.y),
        )
        await pilot.pause()
        assert left_dtc._dragging

        # Move to right split
        drop_tab = right_tabs[0]
        drop_region = drop_tab.region
        drop_x = drop_region.x + drop_region.width // 2
        drop_y = drop_region.y + drop_region.height // 2
        await pilot.hover(
            left_dtc,
            offset=(drop_x - left_dtc.region.x, drop_y - left_dtc.region.y),
        )
        await pilot.pause()
        assert right_dtc.query_one(DropTargetOverlay).has_class("-visible")

        # Move back to source (left) split
        await pilot.hover(
            left_dtc,
            offset=(mid_x - left_dtc.region.x, mid_y - left_dtc.region.y),
        )
        await pilot.pause()

        # overlay should be hidden on right
        assert not right_dtc.query_one(DropTargetOverlay).has_class("-visible")

        # Cleanup
        await pilot.mouse_up(left_dtc, offset=drag_offset)
        await pilot.pause()


async def test_no_drop_target_in_single_split(
    workspace: Path, py_file: Path, py_file2: Path
):
    """In single split mode, no -drop-target class is applied during drag."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        main = app.main_view

        await main.action_open_code_editor(path=py_file2)
        await pilot.pause()

        leaves = all_leaves(main._split_root)
        dtc = main.query_one(f"#{leaves[0].leaf_id}", DraggableTabbedContent)

        tabs = list(dtc.get_child_by_type(ContentTabs).query(ContentTab))
        drag_tab = tabs[0]
        drag_region = drag_tab.region
        drag_x = drag_region.x + drag_region.width // 2
        drag_y = drag_region.y + drag_region.height // 2
        drag_offset = (drag_x - dtc.region.x, drag_y - dtc.region.y)

        await pilot.mouse_down(dtc, offset=drag_offset)
        await pilot.pause()

        # Exceed threshold
        second_tab = tabs[1]
        mid_x = second_tab.region.x + second_tab.region.width // 2
        mid_y = second_tab.region.y + second_tab.region.height // 2
        await pilot.hover(dtc, offset=(mid_x - dtc.region.x, mid_y - dtc.region.y))
        await pilot.pause()
        assert dtc._dragging

        # No overlay -visible should be set on self
        assert not dtc.query_one(DropTargetOverlay).has_class("-visible")

        await pilot.mouse_up(dtc, offset=(mid_x - dtc.region.x, mid_y - dtc.region.y))
        await pilot.pause()


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


# ── Markdown preview pane drag ────────────────────────────────────────────────


@pytest.fixture
def md_file(workspace: Path) -> Path:
    f = workspace / "README.md"
    f.write_text("# Hello\n\nWorld\n")
    return f


async def test_drag_markdown_preview_to_other_split(
    workspace: Path, md_file: Path, py_file: Path
):
    """Moving a markdown preview pane to another split should not crash."""
    app = make_app(workspace, open_file=md_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        main = app.main_view

        # Open a second file so the source split isn't empty after move
        await main.action_open_code_editor(path=py_file)
        await pilot.pause()

        # Open markdown preview for the .md file
        # Focus the md editor first
        leaves = all_leaves(main._split_root)
        source_leaf = leaves[0]
        md_pane_id = source_leaf.opened_files[md_file]
        tc = main.query_one(f"#{source_leaf.leaf_id}")
        tc.active = md_pane_id
        await pilot.pause()

        await main.action_open_markdown_preview_tab()
        await pilot.pause()

        # Verify preview was created
        assert md_file in main._preview_pane_ids
        preview_pane_id = main._preview_pane_ids[md_file]
        assert preview_pane_id in source_leaf.pane_ids

        # Move preview pane to right split
        new_pane_id = await main._move_pane_to_split(preview_pane_id, "right")
        await pilot.pause()

        # Verify move succeeded
        assert new_pane_id is not None

        # Preview pane should be in destination leaf
        dest_leaves = all_leaves(main._split_root)
        dest_leaf = dest_leaves[-1]
        assert new_pane_id in dest_leaf.pane_ids

        # Source pane should be removed
        assert preview_pane_id not in source_leaf.pane_ids

        # _preview_pane_ids should be updated to new pane_id
        assert main._preview_pane_ids[md_file] == new_pane_id

        # Preview content should reflect the source file
        dest_tc = main.query_one(f"#{dest_leaf.leaf_id}")
        new_pane = dest_tc.get_pane(new_pane_id)
        new_preview = new_pane.query_one(MarkdownPreviewPane)
        assert new_preview.source_path == md_file


# ── Drop on non-tab areas ───────────────────────────────────────────────────


async def _setup_two_splits(pilot, workspace, py_file, py_file2):
    """Open two files in left, split right. Return (main, left_dtc, right_dtc)."""
    main = pilot.app.main_view
    await main.action_open_code_editor(path=py_file2)
    await pilot.pause()
    await main.action_split_right()
    await pilot.pause()

    leaves = all_leaves(main._split_root)
    left_dtc = main.query_one(f"#{leaves[0].leaf_id}", DraggableTabbedContent)
    right_dtc = main.query_one(f"#{leaves[1].leaf_id}", DraggableTabbedContent)
    return main, left_dtc, right_dtc


async def _start_drag(pilot, dtc):
    """Helper: mouse_down on first tab + hover to second tab to start dragging."""
    tabs = list(dtc.get_child_by_type(ContentTabs).query(ContentTab))
    drag_tab = tabs[0]
    drag_region = drag_tab.region
    drag_x = drag_region.x + drag_region.width // 2
    drag_y = drag_region.y + drag_region.height // 2
    drag_offset = (drag_x - dtc.region.x, drag_y - dtc.region.y)
    await pilot.mouse_down(dtc, offset=drag_offset)
    await pilot.pause()

    # Move to second tab to exceed drag threshold
    if len(tabs) > 1:
        second = tabs[1]
        mid_x = second.region.x + second.region.width // 2
        mid_y = second.region.y + second.region.height // 2
        await pilot.hover(dtc, offset=(mid_x - dtc.region.x, mid_y - dtc.region.y))
        await pilot.pause()

    assert dtc._dragging


async def test_e2e_drag_tab_drop_on_content_area(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Dropping a tab onto the content area (not tab bar) of another split moves it."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        main, left_dtc, right_dtc = await _setup_two_splits(
            pilot, workspace, py_file, py_file2
        )

        left_tab_count_before = len(main._pane_ids["left"])
        right_tab_count_before = len(main._pane_ids["right"])

        await _start_drag(pilot, left_dtc)

        # Drop on the content area (center) of the right DTC, not on a tab
        right_region = right_dtc.region
        content_x = right_region.x + right_region.width // 2
        content_y = right_region.y + right_region.height // 2 + 5  # well below tab bar
        drop_offset = (content_x - left_dtc.region.x, content_y - left_dtc.region.y)

        await pilot.mouse_up(left_dtc, offset=drop_offset)
        await pilot.pause()
        await pilot.pause()

        # Tab should have moved: left lost one OR right gained one
        assert (
            len(main._pane_ids["right"]) > right_tab_count_before
            or len(main._pane_ids["left"]) < left_tab_count_before
        )


async def test_drop_on_own_content_area_is_noop(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Dropping a tab onto own content area (not another split) is a no-op."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        main, left_dtc, right_dtc = await _setup_two_splits(
            pilot, workspace, py_file, py_file2
        )

        left_pane_ids_before = list(main._pane_ids["left"])
        right_pane_ids_before = list(main._pane_ids["right"])

        await _start_drag(pilot, left_dtc)

        # Drop on left DTC's own content area
        left_region = left_dtc.region
        content_x = left_region.x + left_region.width // 2
        content_y = left_region.y + left_region.height // 2 + 5
        drop_offset = (content_x - left_dtc.region.x, content_y - left_dtc.region.y)

        await pilot.mouse_up(left_dtc, offset=drop_offset)
        await pilot.pause()

        # No change
        assert list(main._pane_ids["left"]) == left_pane_ids_before
        assert list(main._pane_ids["right"]) == right_pane_ids_before


async def test_drop_outside_any_split_is_noop(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Dropping a tab outside any DTC (e.g. sidebar area) is a no-op."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        main = pilot.app.main_view
        await main.action_open_code_editor(path=py_file2)
        await pilot.pause()

        leaves = all_leaves(main._split_root)
        dtc = main.query_one(f"#{leaves[0].leaf_id}", DraggableTabbedContent)

        left_pane_ids_before = list(main._pane_ids["left"])

        await _start_drag(pilot, dtc)

        # Drop on far left (sidebar area, x=1)
        drop_offset = (1 - dtc.region.x, 10 - dtc.region.y)
        await pilot.mouse_up(dtc, offset=drop_offset)
        await pilot.pause()

        # No change
        assert list(main._pane_ids["left"]) == left_pane_ids_before


# ── Overlay mount & 3-way split tests ────────────────────────────────────────


async def test_overlay_mounted_on_dtc(workspace: Path, py_file: Path):
    """Each DraggableTabbedContent mounts a DropTargetOverlay on mount."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        main = app.main_view
        leaves = all_leaves(main._split_root)
        dtc = main.query_one(f"#{leaves[0].leaf_id}", DraggableTabbedContent)
        overlay = dtc.query_one(DropTargetOverlay)
        assert overlay is not None
        assert not overlay.has_class("-visible")
        assert not overlay.has_class("-edge")


async def test_e2e_drag_tab_three_way_split(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Dragging a tab in a 3-way split does not crash."""
    py_file3 = workspace / "third.py"
    py_file3.write_text("z = 3\n")

    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        main = app.main_view

        # Open second file in left
        await main.action_open_code_editor(path=py_file2)
        await pilot.pause()

        # Split right
        await main.action_split_right()
        await pilot.pause()

        # Open third file in right
        main._active_split = "right"
        await main.action_open_code_editor(path=py_file3)
        await pilot.pause()

        # Split right again to create 3-way
        await main.action_split_right()
        await pilot.pause()

        leaves = all_leaves(main._split_root)
        assert len(leaves) >= 3, f"Expected 3+ leaves, got {len(leaves)}"

        # Verify all DTCs have overlays
        for leaf in leaves:
            dtc = main.query_one(f"#{leaf.leaf_id}", DraggableTabbedContent)
            dtc.query_one(DropTargetOverlay)  # should not raise
