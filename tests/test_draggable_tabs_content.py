"""Unit tests for DraggableTabbedContent edge zone detection."""

from textual.app import App, ComposeResult
from textual.widgets import TabPane

from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent


class EdgeZoneApp(App):
    """Minimal app for testing DraggableTabbedContent edge zone helpers."""

    def __init__(self, split_side: str = "left"):
        super().__init__()
        self._split_side = split_side

    def compose(self) -> ComposeResult:
        with DraggableTabbedContent(id="dtc", split_side=self._split_side):
            yield TabPane("Tab1", id="pane1")


async def test_split_side_param_stored():
    """split_side kwarg is stored on the widget."""
    app = EdgeZoneApp(split_side="left")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        assert dtc._split_side == "left"


async def test_split_side_right():
    """split_side='right' is stored correctly."""
    app = EdgeZoneApp(split_side="right")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        assert dtc._split_side == "right"


async def test_in_edge_zone_left_right_edge_true():
    """Left split: x near right boundary → _in_edge_zone returns True."""
    app = EdgeZoneApp(split_side="left")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        # Right edge of widget
        assert dtc._in_edge_zone(dtc.region.right - 1, 5) is True


async def test_in_edge_zone_left_center_false():
    """Left split: x at center of widget → _in_edge_zone returns False."""
    app = EdgeZoneApp(split_side="left")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        center_x = dtc.region.x + dtc.region.width // 2
        assert dtc._in_edge_zone(center_x, 5) is False


async def test_in_edge_zone_right_left_edge_false():
    """x near left boundary returns False (edge zone is always right)."""
    app = EdgeZoneApp(split_side="right")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        assert dtc._in_edge_zone(dtc.region.x + 1, 5) is False


async def test_in_edge_zone_right_center_false():
    """Right split: x at center → _in_edge_zone returns False."""
    app = EdgeZoneApp(split_side="right")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        center_x = dtc.region.x + dtc.region.width // 2
        assert dtc._in_edge_zone(center_x, 5) is False


async def test_tab_moved_message_target_none_allowed():
    """TabMovedToOtherSplit can be constructed with target_pane_id=None."""
    msg = DraggableTabbedContent.TabMovedToOtherSplit("some-pane", None, False)
    assert msg.source_pane_id == "some-pane"
    assert msg.target_pane_id is None
    assert msg.before is False
