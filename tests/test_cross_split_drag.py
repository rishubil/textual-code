"""
Tests for cross-split tab drag: dragging a tab from one split to the other.

Uses the tree-based split model.
"""

from pathlib import Path

import pytest
from textual.widgets._tabbed_content import ContentTab, ContentTabs

from tests.conftest import assert_focus_on_leaf, make_app
from textual_code.widgets.code_editor import CodeEditor
from textual_code.widgets.draggable_tabs_content import (
    DraggableTabbedContent,
    DropTargetScreen,
)
from textual_code.widgets.markdown_preview import MarkdownPreviewPane
from textual_code.widgets.split_tree import all_leaves, find_leaf


def _highlight_is_mode(app, dtc_id: str, mode: str) -> bool:
    """Check if a DTC's highlight is in the given mode on the overlay screen."""
    for s in reversed(app.screen_stack):
        if isinstance(s, DropTargetScreen):
            highlight = s._highlights.get(dtc_id)
            if highlight:
                return highlight.is_mode(mode)
    return False


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
        tc = main.query_one(f"#{leaves[0].leaf_id}", DraggableTabbedContent)
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
        dest_tc = main.query_one(f"#{dest_leaf.leaf_id}", DraggableTabbedContent)
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
        right_tc = main.query_one(f"#{leaves[-1].leaf_id}", DraggableTabbedContent)
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
        assert _highlight_is_mode(app, right_dtc.id, "full")
        # Left DTC (source) overlay should NOT have -visible
        assert not _highlight_is_mode(app, left_dtc.id, "full")

        # Clean up: mouse_up
        await pilot.mouse_up(
            left_dtc,
            offset=(drop_x - left_dtc.region.x, drop_y - left_dtc.region.y),
        )
        await pilot.pause()

        # After mouse_up, overlay should be hidden
        assert not _highlight_is_mode(app, right_dtc.id, "full")


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
        assert _highlight_is_mode(app, right_dtc.id, "full")

        # Move back to source (left) split
        await pilot.hover(
            left_dtc,
            offset=(mid_x - left_dtc.region.x, mid_y - left_dtc.region.y),
        )
        await pilot.pause()

        # overlay should be hidden on right
        assert not _highlight_is_mode(app, right_dtc.id, "full")

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
        assert not _highlight_is_mode(app, dtc.id, "full")

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
        tc = main.query_one(f"#{source_leaf.leaf_id}", DraggableTabbedContent)
        tc.active = md_pane_id
        await pilot.pause()

        await main.action_open_markdown_preview()
        await pilot.pause()
        await pilot.pause()

        # Verify preview was created
        assert md_file in main._preview_pane_ids
        preview_pane_id = main._preview_pane_ids[md_file]
        assert preview_pane_id in source_leaf.pane_ids

        # Move preview pane to right split
        new_pane_id = await main._move_pane_to_split(preview_pane_id, "right")
        await pilot.pause()
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
        dest_tc = main.query_one(f"#{dest_leaf.leaf_id}", DraggableTabbedContent)
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
        main = app.main_view
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


async def test_drop_highlight_classes_on_dtc(workspace: Path, py_file: Path):
    """DTC does not have drop highlight classes by default."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        main = app.main_view
        leaves = all_leaves(main._split_root)
        dtc = main.query_one(f"#{leaves[0].leaf_id}", DraggableTabbedContent)
        assert not _highlight_is_mode(app, dtc.id, "full")
        assert not _highlight_is_mode(app, dtc.id, "edge-right")


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

        # Verify all DTCs have no drop highlight by default
        for leaf in leaves:
            dtc = main.query_one(f"#{leaf.leaf_id}", DraggableTabbedContent)
            assert not _highlight_is_mode(app, dtc.id, "full")


# ── Edge zone bounds check tests ──────────────────────────────────────────────


async def test_in_edge_zone_rejects_outside_region(
    workspace: Path, py_file: Path, py_file2: Path
):
    """_in_edge_zone must return False when cursor is outside the DTC region."""
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

        # screen_x far beyond the right edge of left_dtc
        outside_x = left_dtc.region.right + 10
        mid_y = left_dtc.region.y + left_dtc.region.height // 2
        assert not left_dtc._in_edge_zone(outside_x, mid_y)

        # Also below the DTC
        inside_x = left_dtc.region.right - 1
        below_y = left_dtc.region.bottom + 5
        assert not left_dtc._in_edge_zone(inside_x, below_y)


async def test_edge_highlight_not_shown_when_cursor_over_other_dtc(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Source DTC edge highlight must NOT show when cursor is over target DTC."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        main, left_dtc, right_dtc = await _setup_two_splits(
            pilot, workspace, py_file, py_file2
        )

        await _start_drag(pilot, left_dtc)

        # Move cursor over right DTC's content area
        right_region = right_dtc.region
        target_x = right_region.x + right_region.width // 2
        target_y = right_region.y + right_region.height // 2
        await pilot.hover(
            left_dtc,
            offset=(target_x - left_dtc.region.x, target_y - left_dtc.region.y),
        )
        await pilot.pause()

        # Source DTC must NOT have edge overlay
        assert not _highlight_is_mode(app, left_dtc.id, "edge-right")

        # Cleanup
        await pilot.mouse_up(
            left_dtc,
            offset=(target_x - left_dtc.region.x, target_y - left_dtc.region.y),
        )
        await pilot.pause()


async def test_e2e_drag_tab_three_way_split_correct_target(
    workspace: Path, py_file: Path, py_file2: Path
):
    """3-way split [A|B|C]: drag A's tab to C, tab must arrive in C (not B)."""
    py_file3 = workspace / "third.py"
    py_file3.write_text("z = 3\n")

    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(180, 40)) as pilot:
        await pilot.pause()
        main = app.main_view

        # A has py_file + py_file2
        await main.action_open_code_editor(path=py_file2)
        await pilot.pause()

        # Split right → creates B
        await main.action_split_right()
        await pilot.pause()

        # Open py_file3 in B, then split right → creates C
        leaves = all_leaves(main._split_root)
        b_leaf = leaves[-1]
        main._active_leaf_id = b_leaf.leaf_id
        await main.action_open_code_editor(path=py_file3)
        await pilot.pause()
        await main.action_split_right()
        await pilot.pause()

        leaves = all_leaves(main._split_root)
        assert len(leaves) >= 3, f"Expected 3+ leaves, got {len(leaves)}"
        dtc_a = main.query_one(f"#{leaves[0].leaf_id}", DraggableTabbedContent)
        dtc_c = main.query_one(f"#{leaves[-1].leaf_id}", DraggableTabbedContent)
        leaf_c = leaves[-1]

        pane_count_c_before = len(leaf_c.pane_ids)

        # Drag from A
        await _start_drag(pilot, dtc_a)

        # Drop on C's content area (center)
        c_region = dtc_c.region
        drop_x = c_region.x + c_region.width // 2
        drop_y = c_region.y + c_region.height // 2
        await pilot.mouse_up(
            dtc_a,
            offset=(drop_x - dtc_a.region.x, drop_y - dtc_a.region.y),
        )
        await pilot.pause()

        # Tab must arrive in C (the last leaf)
        leaves_after = all_leaves(main._split_root)
        leaf_c_after = leaves_after[-1]
        assert len(leaf_c_after.pane_ids) > pane_count_c_before, (
            f"Tab should have moved to leaf C. "
            f"C pane_ids before={pane_count_c_before}, "
            f"after={len(leaf_c_after.pane_ids)}"
        )


async def test_e2e_drag_tab_mixed_nested_split(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Mixed nested split [A | [B / C]]: drag A's tab to C (vertical child)."""
    py_file3 = workspace / "third.py"
    py_file3.write_text("z = 3\n")

    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        main = app.main_view

        # A has py_file + py_file2
        await main.action_open_code_editor(path=py_file2)
        await pilot.pause()

        # Split right → creates B (horizontal)
        await main.action_split_right()
        await pilot.pause()

        # In B, open py_file3, then split down → creates C (vertical)
        leaves = all_leaves(main._split_root)
        b_leaf = leaves[-1]
        main._active_leaf_id = b_leaf.leaf_id
        await main.action_open_code_editor(path=py_file3)
        await pilot.pause()
        await main.action_split_down()
        await pilot.pause()

        leaves = all_leaves(main._split_root)
        assert len(leaves) >= 3, f"Expected 3+ leaves, got {len(leaves)}"
        dtc_a = main.query_one(f"#{leaves[0].leaf_id}", DraggableTabbedContent)
        # C is the last leaf (bottom-right)
        leaf_c = leaves[-1]
        dtc_c = main.query_one(f"#{leaf_c.leaf_id}", DraggableTabbedContent)

        pane_count_c_before = len(leaf_c.pane_ids)

        # Drag from A
        await _start_drag(pilot, dtc_a)

        # Drop on C's content area
        c_region = dtc_c.region
        drop_x = c_region.x + c_region.width // 2
        drop_y = c_region.y + c_region.height // 2
        await pilot.mouse_up(
            dtc_a,
            offset=(drop_x - dtc_a.region.x, drop_y - dtc_a.region.y),
        )
        await pilot.pause()

        # Tab must arrive in C
        leaves_after = all_leaves(main._split_root)
        leaf_c_after = leaves_after[-1]
        assert len(leaf_c_after.pane_ids) > pane_count_c_before, (
            f"Tab should have moved to leaf C. "
            f"C pane_ids before={pane_count_c_before}, "
            f"after={len(leaf_c_after.pane_ids)}"
        )


# ── Focus tests for cross-split moves ────────────────────────────────────────


async def test_drag_cross_split_focuses_moved_tab(
    workspace: Path, py_file: Path, py_file2: Path
):
    """action_move_editor_to_next_group focuses the destination pane."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        main = app.main_view

        # Open second file so left isn't empty after move
        await main.action_open_code_editor(path=py_file2)
        await pilot.pause()

        # Open right split
        await main.action_split_right()
        await pilot.pause()

        # Focus left split, select py_file
        leaves = all_leaves(main._split_root)
        left_leaf = leaves[0]
        main._set_active_leaf(left_leaf)
        await pilot.pause()
        pane_id = main._opened_files["left"][py_file]
        tc_left = main.query_one(f"#{left_leaf.leaf_id}", DraggableTabbedContent)
        tc_left.active = pane_id
        await pilot.pause()

        # Move to right via action
        await main.action_move_editor_to_next_group()
        await pilot.pause()

        # Find where py_file landed
        leaves = all_leaves(main._split_root)
        dest_leaf = leaves[-1]
        new_pane_id = dest_leaf.opened_files.get(py_file)
        assert new_pane_id is not None
        assert_focus_on_leaf(
            app, main, dest_leaf, new_pane_id, "cross-split action move"
        )


async def test_drag_mouse_cross_split_focuses_moved_tab(
    workspace: Path, py_file: Path, py_file2: Path
):
    """E2E mouse drag from left to right focuses the moved tab in dest."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        main, left_dtc, right_dtc = await _setup_two_splits(
            pilot, workspace, py_file, py_file2
        )

        # Record which file is being dragged (first tab in left)
        left_tabs = list(left_dtc.get_child_by_type(ContentTabs).query(ContentTab))
        drag_tab = left_tabs[0]
        drag_pane_id = ContentTab.sans_prefix(drag_tab.id)
        leaves_before = all_leaves(main._split_root)
        left_leaf = leaves_before[0]
        dragged_path = next(
            (p for p, pid in left_leaf.opened_files.items() if pid == drag_pane_id),
            None,
        )
        assert dragged_path is not None, "Could not find dragged file path"

        await _start_drag(pilot, left_dtc)

        # Drop on right split's tab bar
        right_tabs = list(right_dtc.get_child_by_type(ContentTabs).query(ContentTab))
        drop_tab = right_tabs[0]
        drop_region = drop_tab.region
        drop_x = drop_region.x + drop_region.width // 2
        drop_y = drop_region.y + drop_region.height // 2
        await pilot.mouse_up(
            left_dtc,
            offset=(drop_x - left_dtc.region.x, drop_y - left_dtc.region.y),
        )
        await pilot.pause()

        # Verify focus is on destination leaf with moved tab
        leaves = all_leaves(main._split_root)
        dest_leaf = None
        for leaf in leaves:
            if dragged_path in leaf.opened_files:
                dest_leaf = leaf
                break
        assert dest_leaf is not None, "Dragged file not found in any leaf after move"
        assert main._active_leaf_id == dest_leaf.leaf_id, (
            "active leaf should be destination after mouse drag"
        )


async def test_drag_edge_zone_new_split_focuses_moved_tab(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Edge zone drag (TabMovedToOtherSplit with no target) focuses the new split."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        main = app.main_view

        # Open second file so left isn't empty after edge drag
        await main.action_open_code_editor(path=py_file2)
        await pilot.pause()
        assert main._split_visible is False

        leaves = all_leaves(main._split_root)
        left_tc = main.query_one(f"#{leaves[0].leaf_id}", DraggableTabbedContent)
        pane_id = leaves[0].opened_files[py_file]

        # Post edge zone message with explicit right direction
        left_tc.post_message(
            DraggableTabbedContent.TabMovedToOtherSplit(
                pane_id, None, False, split_direction="right"
            )
        )
        await pilot.pause()
        await pilot.pause()

        # Split should be created
        assert main._split_visible is True
        assert py_file in main._opened_files["right"]

        # Focus should be on the new (right) leaf
        leaves = all_leaves(main._split_root)
        dest_leaf = leaves[-1]
        new_pane_id = dest_leaf.opened_files.get(py_file)
        assert new_pane_id is not None

        assert main._active_leaf_id == dest_leaf.leaf_id, (
            "active leaf should be dest leaf after edge zone drag"
        )
        tc_dest = main.query_one(f"#{dest_leaf.leaf_id}", DraggableTabbedContent)
        assert tc_dest.active == new_pane_id, (
            "active tab in dest TC should be the moved tab"
        )


# ── Directional edge zone split tests ────────────────────────────────────────


async def _edge_zone_split_test(workspace, py_file, py_file2, direction):
    """Helper: post edge zone message with given direction and verify split."""
    from textual_code.widgets.split_tree import BranchNode

    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        main = app.main_view

        await main.action_open_code_editor(path=py_file2)
        await pilot.pause()
        assert main._split_visible is False

        leaves = all_leaves(main._split_root)
        tc = main.query_one(f"#{leaves[0].leaf_id}", DraggableTabbedContent)
        pane_id = leaves[0].opened_files[py_file]

        tc.post_message(
            DraggableTabbedContent.TabMovedToOtherSplit(
                pane_id, None, False, split_direction=direction
            )
        )
        await pilot.pause()
        await pilot.pause()

        assert main._split_visible is True
        root = main._split_root
        assert isinstance(root, BranchNode)

        expected_dir = "horizontal" if direction in ("left", "right") else "vertical"
        assert root.direction == expected_dir, (
            f"Expected {expected_dir} split for direction={direction}, "
            f"got {root.direction}"
        )

        leaves = all_leaves(root)
        assert len(leaves) == 2

        # For "before" directions (left, up), the moved pane should be first
        if direction in ("left", "up"):
            assert py_file in leaves[0].opened_files
        else:
            assert py_file in leaves[1].opened_files


async def test_edge_zone_drag_split_left(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Edge zone drag with direction='left' creates horizontal split before."""
    await _edge_zone_split_test(workspace, py_file, py_file2, "left")


async def test_edge_zone_drag_split_up(workspace: Path, py_file: Path, py_file2: Path):
    """Edge zone drag with direction='up' creates vertical split above."""
    await _edge_zone_split_test(workspace, py_file, py_file2, "up")


async def test_edge_zone_drag_split_down(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Edge zone drag with direction='down' creates vertical split below."""
    await _edge_zone_split_test(workspace, py_file, py_file2, "down")


# ── Edge zone split from existing multi-leaf split ───────────────────────────


async def _edge_zone_split_from_existing_split_test(
    workspace, py_file, py_file2, initial_split_dir, edge_direction
):
    """Helper: from an existing split, edge-zone drag should create a new
    sub-split, NOT move the tab to the adjacent existing pane."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(160, 40)) as pilot:
        await pilot.pause()
        main = app.main_view

        # Open a second file so source pane has 2 tabs
        await main.action_open_code_editor(path=py_file2)
        await pilot.pause()

        # Create initial split
        if initial_split_dir == "horizontal":
            await main.action_split_right()
        else:
            await main.action_split_down()
        await pilot.pause()

        assert main._split_visible is True
        leaves_before = all_leaves(main._split_root)
        assert len(leaves_before) == 2

        # Focus back to first leaf (the source) which has 2 tabs
        source_leaf = leaves_before[0]
        main._set_active_leaf(source_leaf)
        tc = main.query_one(f"#{source_leaf.leaf_id}", DraggableTabbedContent)
        pane_id = source_leaf.opened_files[py_file]
        source_tab_count_before = len(source_leaf.pane_ids)

        # Record adjacent leaf state
        adj_leaf = leaves_before[1]
        adj_pane_count_before = len(adj_leaf.pane_ids)

        # Post edge zone message with explicit direction
        tc.post_message(
            DraggableTabbedContent.TabMovedToOtherSplit(
                pane_id, None, False, split_direction=edge_direction
            )
        )
        await pilot.pause()
        await pilot.pause()

        # A new split should be created (3 leaves total)
        leaves_after = all_leaves(main._split_root)
        assert len(leaves_after) == 3, (
            f"Expected 3 leaves after edge-zone split from existing split, "
            f"got {len(leaves_after)}. Tab was likely moved to adjacent pane "
            f"instead of creating a new split."
        )

        # The adjacent leaf should be untouched
        adj_leaf_after = find_leaf(main._split_root, adj_leaf.leaf_id)
        assert adj_leaf_after is not None
        assert len(adj_leaf_after.pane_ids) == adj_pane_count_before, (
            "Adjacent pane should not have received the tab"
        )

        # Source leaf should have 1 fewer tab
        source_leaf_after = find_leaf(main._split_root, source_leaf.leaf_id)
        assert source_leaf_after is not None
        assert len(source_leaf_after.pane_ids) == source_tab_count_before - 1, (
            "Source pane should have one fewer tab after the split"
        )

        # The dragged file should be in one of the new leaves
        found = any(py_file in leaf.opened_files for leaf in leaves_after)
        assert found, "Dragged file should exist in one of the leaves"


async def test_edge_zone_split_down_from_horizontal_split(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Bug fix: edge-zone 'down' from a left|right split should create a vertical
    sub-split below, NOT move the tab to the right pane."""
    await _edge_zone_split_from_existing_split_test(
        workspace, py_file, py_file2, "horizontal", "down"
    )


async def test_edge_zone_split_right_from_vertical_split(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Edge-zone 'right' from a top/bottom split should create a horizontal
    sub-split to the right, NOT move the tab to the bottom pane."""
    await _edge_zone_split_from_existing_split_test(
        workspace, py_file, py_file2, "vertical", "right"
    )
