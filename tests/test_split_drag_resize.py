"""
Tests for the split view drag resize via SplitResizeHandle.

Covers:
- SplitResizeHandle visibility (hidden when split closed, visible when open)
- resize_split_to() clamping logic
- Mouse drag flow (mouse_down + mouse_move + mouse_up)
- Vertical split orientation
"""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.widgets.split_resize_handle import SPLIT_MIN_SIZE, SplitResizeHandle


@pytest.fixture
def py_file(workspace: Path) -> Path:
    f = workspace / "main.py"
    f.write_text("print('hello')\n")
    return f


async def test_handle_exists_in_app(workspace, py_file):
    """SplitResizeHandle widget must exist in the DOM."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        handle = app.main_view.query_one(SplitResizeHandle)
        assert handle is not None


async def test_handle_hidden_when_split_closed(workspace, py_file):
    """SplitResizeHandle should be hidden (display:none) when split is closed."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        handle = app.main_view.query_one(SplitResizeHandle)
        assert handle.display is False


async def test_handle_visible_when_split_opened(workspace, py_file):
    """SplitResizeHandle should be visible after action_split_right()."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        handle = app.main_view.query_one(SplitResizeHandle)
        assert handle.display is True


async def test_handle_hidden_when_split_closes(workspace, py_file):
    """SplitResizeHandle should be hidden again when split is closed."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()
        await app.main_view.action_close_split()
        await pilot.pause()
        handle = app.main_view.query_one(SplitResizeHandle)
        assert handle.display is False


async def test_resize_split_to_sets_width(workspace, py_file):
    """resize_split_to() should set split_left.styles.width."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        handle = app.main_view.query_one(SplitResizeHandle)
        # Container starts at x=0 (after sidebar), move handle to x=40
        # split_container.region.x may vary; pass a screen_x that translates to 40
        container = app.main_view.query_one("#split_container")
        target_x = container.region.x + 40
        handle.resize_split_to(target_x, 0)
        await pilot.pause()

        width = app.main_view.query_one("#split_left").styles.width.value
        assert width == 40


async def test_resize_split_min_clamp(workspace, py_file):
    """resize_split_to() should clamp to SPLIT_MIN_SIZE when value is too small."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        handle = app.main_view.query_one(SplitResizeHandle)
        container = app.main_view.query_one("#split_container")
        # Pass a value that would result in size < SPLIT_MIN_SIZE
        handle.resize_split_to(container.region.x + 2, 0)
        await pilot.pause()

        width = app.main_view.query_one("#split_left").styles.width.value
        assert width == SPLIT_MIN_SIZE


async def test_resize_split_max_clamp(workspace, py_file):
    """resize_split_to() should clamp to container_width - SPLIT_MIN_SIZE."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        handle = app.main_view.query_one(SplitResizeHandle)
        container = app.main_view.query_one("#split_container")
        # Pass a value beyond container width
        handle.resize_split_to(container.region.x + container.size.width + 100, 0)
        await pilot.pause()

        width = app.main_view.query_one("#split_left").styles.width.value
        assert width == container.size.width - SPLIT_MIN_SIZE


async def test_drag_flow(workspace, py_file):
    """Full drag: mouse_down + mouse_move + mouse_up should resize split_left."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        handle = app.main_view.query_one(SplitResizeHandle)
        container = app.main_view.query_one("#split_container")
        target_x = container.region.x + 50

        # Simulate drag
        await pilot.mouse_down(handle)
        await pilot.pause()
        await pilot.hover(handle, offset=(target_x - handle.region.x, 0))
        await pilot.pause()
        await pilot.mouse_up(handle)
        await pilot.pause()

        width = app.main_view.query_one("#split_left").styles.width.value
        assert width == 50


async def test_resize_split_vertical(workspace, py_file):
    """In vertical split mode, resize_split_to() should set split_left.styles.height."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await app.main_view.action_split_right()
        await pilot.pause()

        container = app.main_view.query_one("#split_container")
        container.add_class("split-vertical")
        await pilot.pause()

        handle = app.main_view.query_one(SplitResizeHandle)
        target_y = container.region.y + 12
        handle.resize_split_to(0, target_y)
        await pilot.pause()

        height = app.main_view.query_one("#split_left").styles.height.value
        assert height == 12
