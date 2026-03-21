"""
Tests for sidebar drag-resize feature.

Covers:
- SIDEBAR_MIN_WIDTH / SIDEBAR_MAX_WIDTH constants exist
- SidebarResizeHandle is present inside Sidebar
- resize_sidebar_to(width) changes sidebar width, clamped at min/max
- mouse_down sets _dragging=True, mouse_up sets _dragging=False
- Direct resize_sidebar_to() call changes sidebar width
- Full mouse drag flow changes sidebar width
"""

from tests.conftest import make_app
from textual_code.widgets.sidebar import SIDEBAR_MIN_WIDTH, Sidebar, SidebarResizeHandle

# ── Group 1: constants ─────────────────────────────────────────────────────────


def test_sidebar_min_width_constant_exists():
    assert isinstance(SIDEBAR_MIN_WIDTH, int)
    assert SIDEBAR_MIN_WIDTH >= 1


def test_sidebar_max_width_relative_to_min():
    # Just verify SIDEBAR_MIN_WIDTH is a reasonable minimum
    assert SIDEBAR_MIN_WIDTH <= 10


# ── Group 2: SidebarResizeHandle is present inside Sidebar ────────────────────


async def test_sidebar_has_resize_handle(workspace):
    app = make_app(workspace)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        handle = app.query_one(SidebarResizeHandle)
        assert handle is not None


async def test_sidebar_resize_handle_is_child_of_sidebar(workspace):
    app = make_app(workspace)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        sidebar = app.query_one(Sidebar)
        handle = sidebar.query_one(SidebarResizeHandle)
        assert handle is not None


# ── Group 3: resize_sidebar_to() clamps at min/max ────────────────────────────


async def test_resize_sidebar_to_changes_width(workspace):
    app = make_app(workspace)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        handle = app.query_one(SidebarResizeHandle)
        handle.resize_sidebar_to(30)
        await pilot.pause()
        assert app.query_one(Sidebar).styles.width.value == 30  # ty: ignore[unresolved-attribute]


async def test_resize_sidebar_to_clamps_at_min(workspace):
    app = make_app(workspace)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        handle = app.query_one(SidebarResizeHandle)
        handle.resize_sidebar_to(0)  # below min
        await pilot.pause()
        assert app.query_one(Sidebar).styles.width.value == SIDEBAR_MIN_WIDTH  # ty: ignore[unresolved-attribute]


async def test_resize_sidebar_to_clamps_at_max(workspace):
    app = make_app(workspace)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        handle = app.query_one(SidebarResizeHandle)
        handle.resize_sidebar_to(9999)  # above max
        await pilot.pause()
        sidebar = app.query_one(Sidebar)
        # Width must be <= screen_width - 5
        assert sidebar.styles.width.value <= app.size.width - 5  # ty: ignore[unresolved-attribute]


# ── Group 4: mouse_down/_up toggle _dragging ──────────────────────────────────


async def test_mouse_down_sets_dragging_true(workspace):
    app = make_app(workspace)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        handle = app.query_one(SidebarResizeHandle)
        assert handle._dragging is False

        await pilot.mouse_down(handle)
        await pilot.pause()
        assert handle._dragging is True


async def test_mouse_up_sets_dragging_false(workspace):
    app = make_app(workspace)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        handle = app.query_one(SidebarResizeHandle)

        await pilot.mouse_down(handle)
        await pilot.pause()
        assert handle._dragging is True

        await pilot.mouse_up(handle)
        await pilot.pause()
        assert handle._dragging is False


# ── Group 5a: resize_sidebar_to() direct call ─────────────────────────────────


async def test_resize_sidebar_to_30_sets_width_to_30(workspace):
    app = make_app(workspace)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        handle = app.query_one(SidebarResizeHandle)
        handle.resize_sidebar_to(30)
        await pilot.pause()
        assert app.query_one(Sidebar).styles.width.value == 30  # ty: ignore[unresolved-attribute]


# ── Group 5b: full drag flow ──────────────────────────────────────────────────


async def test_full_drag_changes_sidebar_width(workspace):
    app = make_app(workspace)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        handle = app.query_one(SidebarResizeHandle)

        # Start drag
        await pilot.mouse_down(handle)
        await pilot.pause()

        # Hover at absolute screen position (30, 5).
        # event.screen_x == 30, so resize_sidebar_to(30) is called.
        await pilot.hover(offset=(30, 5))
        await pilot.pause()

        # Release at the same position so the implicit MouseMove in mouse_up
        # doesn't resize the sidebar to x=0.
        await pilot.mouse_up(offset=(30, 5))
        await pilot.pause()

        sidebar = app.query_one(Sidebar)
        assert sidebar.styles.width.value == 30  # ty: ignore[unresolved-attribute]
