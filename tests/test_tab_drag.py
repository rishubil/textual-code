"""
Tests for DraggableTabbedContent: tab reordering via drag.

TDD: Red → Green approach.
"""

from pathlib import Path

from textual.widgets._tabbed_content import ContentTab, ContentTabs

from tests.conftest import make_app
from textual_code.widgets.code_editor import CodeEditor
from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent
from textual_code.widgets.split_tree import all_leaves


def _first_dtc(app) -> DraggableTabbedContent:
    """Get the first leaf's DraggableTabbedContent."""
    leaves = all_leaves(app.main_view._split_root)
    return app.main_view.query_one(f"#{leaves[0].leaf_id}", DraggableTabbedContent)


def _tab_order(dtc: DraggableTabbedContent) -> list[str]:
    """Return pane IDs in current tab display order."""
    content_tabs = dtc.get_child_by_type(ContentTabs)
    return [
        ContentTab.sans_prefix(t.id) for t in content_tabs.query(ContentTab) if t.id
    ]


# ── Unit tests for reorder_tab ────────────────────────────────────────────────


async def test_reorder_tab_moves_before(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    """reorder_tab(A, B, before=True) puts A before B."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=sample_json_file)
        await pilot.pause()

        dtc = _first_dtc(app)
        order = _tab_order(dtc)
        assert len(order) == 2
        a_id, b_id = order  # A is first (py), B is second (json)

        # Move B before A
        dtc.reorder_tab(b_id, a_id, before=True)
        await pilot.pause()

        new_order = _tab_order(dtc)
        assert new_order.index(b_id) < new_order.index(a_id)


async def test_reorder_tab_moves_after(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    """reorder_tab(A, B, before=False) puts A after B."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=sample_json_file)
        await pilot.pause()

        dtc = _first_dtc(app)
        order = _tab_order(dtc)
        assert len(order) == 2
        a_id, b_id = order  # A is first (py), B is second (json)

        # Move A after B
        dtc.reorder_tab(a_id, b_id, before=False)
        await pilot.pause()

        new_order = _tab_order(dtc)
        assert new_order.index(a_id) > new_order.index(b_id)


async def test_reorder_tab_correct_order_and_content(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    """Tab order and editor text are both preserved after reorder."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=sample_json_file)
        await pilot.pause()

        dtc = _first_dtc(app)
        order_before = _tab_order(dtc)
        assert len(order_before) == 2
        py_id, json_id = order_before

        # Swap: move py_id after json_id
        dtc.reorder_tab(py_id, json_id, before=False)
        await pilot.pause()

        order_after = _tab_order(dtc)
        assert order_after == [json_id, py_id]

        # Editor content should still be intact
        py_editor = app.main_view.query_one(f"#{py_id} CodeEditor", CodeEditor)
        assert "print" in py_editor.text

        json_editor = app.main_view.query_one(f"#{json_id} CodeEditor", CodeEditor)
        assert "key" in json_editor.text


async def test_reorder_tab_same_id_noop(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    """reorder_tab with same src and target is a no-op."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=sample_json_file)
        await pilot.pause()

        dtc = _first_dtc(app)
        order_before = _tab_order(dtc)

        dtc.reorder_tab(order_before[0], order_before[0], before=True)
        await pilot.pause()

        assert _tab_order(dtc) == order_before


async def test_reorder_tab_invalid_target_id_noop(
    workspace: Path, sample_py_file: Path
):
    """reorder_tab with non-existent pane_id does not raise and is a noop."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()

        dtc = _first_dtc(app)
        order_before = _tab_order(dtc)

        # Neither raises nor changes order
        dtc.reorder_tab("nonexistent-id", order_before[0], before=True)
        await pilot.pause()

        assert _tab_order(dtc) == order_before


# ── Drag threshold tests ──────────────────────────────────────────────────────


async def test_drag_threshold_not_exceeded_no_capture(
    workspace: Path, sample_py_file: Path
):
    """Moving less than threshold keeps _dragging=False."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()

        dtc = _first_dtc(app)
        # Simulate state as if mouse_down was captured on a tab
        dtc._drag_start = (10, 10)
        dtc._drag_pane_id = "some-pane"

        # Move only 2px (< threshold of 3px)
        from textual.events import MouseMove

        event = MouseMove(
            widget=None,
            x=0,
            y=0,
            delta_x=0,
            delta_y=0,
            button=0,
            shift=False,
            meta=False,
            ctrl=False,
            screen_x=12,
            screen_y=10,
            style=None,
        )
        dtc.on_mouse_move(event)

        assert dtc._dragging is False


# ── E2E drag test ─────────────────────────────────────────────────────────────


async def test_drag_reorders_tabs(
    workspace: Path, sample_py_file: Path, sample_json_file: Path
):
    """E2E: mouse_down → mouse_move (threshold exceeded) → mouse_up reorders tabs."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor(path=sample_json_file)
        await pilot.pause()

        dtc = _first_dtc(app)
        order_before = _tab_order(dtc)
        assert len(order_before) == 2

        content_tabs = dtc.get_child_by_type(ContentTabs)
        tabs = list(content_tabs.query(ContentTab))
        first_tab = tabs[0]
        second_tab = tabs[1]

        # Get screen positions of the two tabs
        first_region = first_tab.region
        second_region = second_tab.region

        first_x = first_region.x + first_region.width // 4  # left quarter of first tab
        first_y = first_region.y + first_region.height // 2
        # Drop on right 3/4 of second tab to ensure before=False (swap)
        second_x = second_region.x + second_region.width * 3 // 4
        second_y = second_region.y + second_region.height // 2

        # Simulate drag: mouse_down on first tab, hover to second, mouse_up
        first_offset = (first_x - dtc.region.x, first_y - dtc.region.y)
        second_offset = (second_x - dtc.region.x, second_y - dtc.region.y)

        await pilot.mouse_down(dtc, offset=first_offset)
        await pilot.pause()

        # Hover to exceed threshold distance
        await pilot.hover(dtc, offset=second_offset)
        await pilot.pause()

        await pilot.mouse_up(dtc, offset=second_offset)
        await pilot.pause()

        order_after = _tab_order(dtc)
        # Order should have changed
        assert order_after != order_before
