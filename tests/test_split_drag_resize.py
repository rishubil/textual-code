"""
Tests for the split view drag resize via SplitResizeHandle.

Covers:
- SplitResizeHandle visibility (not present when no split, present when split)
- resize_split_to() clamping logic (in SplitContainer)
- Mouse drag flow (mouse_down + mouse_move + mouse_up)
- Vertical split orientation
"""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent
from textual_code.widgets.split_container import SplitContainer
from textual_code.widgets.split_resize_handle import SPLIT_MIN_SIZE, SplitResizeHandle
from textual_code.widgets.split_tree import all_leaves


@pytest.fixture
def py_file(workspace: Path) -> Path:
    f = workspace / "main.py"
    f.write_text("print('hello')\n")
    return f


async def test_handle_not_present_without_split(workspace, py_file):
    """SplitResizeHandle should not exist in the DOM when there is no split."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        handles = list(app.main_view.query(SplitResizeHandle))
        assert len(handles) == 0


async def test_handle_visible_when_split_opened(workspace, py_file):
    """SplitResizeHandle should be visible after action_split_right()."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        handle = app.main_view.query_one(SplitResizeHandle)
        assert handle.display is True


async def test_handle_removed_when_split_closes(workspace, py_file):
    """SplitResizeHandle should be removed when split is closed."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        await app.main_view.action_close_split()
        await pilot.pause()
        await pilot.pause()
        handles = list(app.main_view.query(SplitResizeHandle))
        assert len(handles) == 0


async def test_resize_split_to_sets_width(workspace, py_file):
    """resize_split_to() should set first leaf DTC's styles.width."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        handle = app.main_view.query_one(SplitResizeHandle)
        container = app.main_view.query_one(SplitContainer)
        target_x = container.region.x + 40
        handle.resize_split_to(target_x, 0)
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        first_dtc = app.main_view.query_one(
            f"#{leaves[0].leaf_id}", DraggableTabbedContent
        )
        assert first_dtc.styles.width.value == 40


async def test_resize_split_min_clamp(workspace, py_file):
    """resize_split_to() should clamp to SPLIT_MIN_SIZE when value is too small."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        handle = app.main_view.query_one(SplitResizeHandle)
        container = app.main_view.query_one(SplitContainer)
        handle.resize_split_to(container.region.x + 2, 0)
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        first_dtc = app.main_view.query_one(
            f"#{leaves[0].leaf_id}", DraggableTabbedContent
        )
        assert first_dtc.styles.width.value == SPLIT_MIN_SIZE


async def test_resize_split_max_clamp(workspace, py_file):
    """resize_split_to() should clamp to container_width - SPLIT_MIN_SIZE."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        handle = app.main_view.query_one(SplitResizeHandle)
        container = app.main_view.query_one(SplitContainer)
        handle.resize_split_to(container.region.x + container.size.width + 100, 0)
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        first_dtc = app.main_view.query_one(
            f"#{leaves[0].leaf_id}", DraggableTabbedContent
        )
        assert first_dtc.styles.width.value == container.size.width - SPLIT_MIN_SIZE


async def test_drag_flow(workspace, py_file):
    """Full drag: mouse_down + mouse_move + mouse_up should resize first leaf."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        handle = app.main_view.query_one(SplitResizeHandle)
        container = app.main_view.query_one(SplitContainer)
        target_x = container.region.x + 50

        # Simulate drag
        await pilot.mouse_down(handle)
        await pilot.pause()
        await pilot.hover(handle, offset=(target_x - handle.region.x, 0))
        await pilot.pause()
        await pilot.mouse_up(handle)
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        first_dtc = app.main_view.query_one(
            f"#{leaves[0].leaf_id}", DraggableTabbedContent
        )
        assert first_dtc.styles.width.value == 50


async def test_resize_split_vertical(workspace, py_file):
    """Vertical split: resize sets first leaf's styles.height."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        # Toggle to vertical orientation
        app.main_view.action_toggle_split_vertical()
        await pilot.pause()

        handle = app.main_view.query_one(SplitResizeHandle)
        container = app.main_view.query_one(SplitContainer)
        target_y = container.region.y + 12
        handle.resize_split_to(0, target_y)
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        first_dtc = app.main_view.query_one(
            f"#{leaves[0].leaf_id}", DraggableTabbedContent
        )
        assert first_dtc.styles.height.value == 12
