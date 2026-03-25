"""Unit tests for DraggableTabbedContent and DropTargetScreen."""

from textual.app import App, ComposeResult
from textual.events import MouseDown, MouseUp
from textual.widget import Widget
from textual.widgets import TabPane

from textual_code.widgets.draggable_tabs_content import (
    DraggableTabbedContent,
    DropHintBox,
    DropTargetScreen,
)


def _mouse_down(widget: Widget, sx: int, sy: int) -> MouseDown:
    """Create a MouseDown at the given screen coordinates with default modifiers."""
    return MouseDown(
        widget=widget,
        x=sx,
        y=sy,
        delta_x=0,
        delta_y=0,
        button=1,
        shift=False,
        meta=False,
        ctrl=False,
        screen_x=sx,
        screen_y=sy,
    )


def _mouse_up(widget: Widget, sx: int, sy: int) -> MouseUp:
    """Create a MouseUp at the given screen coordinates with default modifiers."""
    return MouseUp(
        widget=widget,
        x=sx,
        y=sy,
        delta_x=0,
        delta_y=0,
        button=1,
        shift=False,
        meta=False,
        ctrl=False,
        screen_x=sx,
        screen_y=sy,
    )


class EdgeZoneApp(App):
    """Minimal app for testing DraggableTabbedContent edge zone helpers."""

    CSS = """
    DraggableTabbedContent { height: 1fr; }
    """

    def __init__(self, split_side: str = "left"):
        super().__init__()
        self._split_side = split_side

    def compose(self) -> ComposeResult:
        with DraggableTabbedContent(id="dtc", split_side=self._split_side):
            yield TabPane("Tab1", id="pane1")


# ── Edge zone detection tests (unchanged) ─────────────────────────────────────


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
    """Left split: x near right boundary → _in_edge_zone returns 'right'."""
    app = EdgeZoneApp(split_side="left")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        # Right edge of widget
        assert (
            dtc._in_edge_zone(
                dtc.region.right - 1, dtc.region.y + dtc.region.height // 2
            )
            == "right"
        )


async def test_in_edge_zone_left_center_false():
    """Left split: x at center of widget → _in_edge_zone returns None."""
    app = EdgeZoneApp(split_side="left")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        center_x = dtc.region.x + dtc.region.width // 2
        assert (
            dtc._in_edge_zone(center_x, dtc.region.y + dtc.region.height // 2) is None
        )


async def test_in_edge_zone_left_edge_returns_left():
    """x near left boundary → _in_edge_zone returns 'left'."""
    app = EdgeZoneApp(split_side="right")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        assert (
            dtc._in_edge_zone(dtc.region.x + 1, dtc.region.y + dtc.region.height // 2)
            == "left"
        )


async def test_in_edge_zone_right_center_none():
    """Right split: x at center → _in_edge_zone returns None."""
    app = EdgeZoneApp(split_side="right")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        center_x = dtc.region.x + dtc.region.width // 2
        assert (
            dtc._in_edge_zone(center_x, dtc.region.y + dtc.region.height // 2) is None
        )


# ── DropTargetScreen tests ────────────────────────────────────────────────────


async def _push_overlay(app, pilot):
    """Helper: push DropTargetScreen with DTC IDs and set references."""
    dtcs = list(app.query(DraggableTabbedContent))
    dtc_ids = [dtc.id for dtc in dtcs]
    screen = DropTargetScreen(dtc_ids)
    for dtc in dtcs:
        dtc._overlay_screen = screen
    app.push_screen(screen)
    await pilot.pause()
    return screen


async def test_drop_target_screen_has_transparent_background():
    """DropTargetScreen has a fully transparent background."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        screen = await _push_overlay(app, pilot)
        # Background should be transparent (RGBA with alpha=0)
        assert screen.styles.background.a == 0


async def test_drop_target_screen_creates_highlights_for_dtcs():
    """DropTargetScreen creates DropHintBox widgets for each DTC."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        screen = await _push_overlay(app, pilot)
        # One DTC → one hint box
        hints = screen.query(DropHintBox)
        assert len(hints) == 1


async def test_show_highlight_full_mode():
    """show_highlight with 'full' mode shows all 4 bars."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        screen = await _push_overlay(app, pilot)
        screen.show_highlight(dtc.id, dtc.region, "full")
        highlight = screen._highlights[dtc.id]
        assert highlight.is_mode("full")
        assert not highlight.is_mode("edge")


async def test_show_highlight_edge_mode():
    """show_highlight with 'edge-right' mode shows edge highlight."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        screen = await _push_overlay(app, pilot)
        screen.show_highlight(dtc.id, dtc.region, "edge-right")
        highlight = screen._highlights[dtc.id]
        assert highlight.is_mode("edge-right")
        assert not highlight.is_mode("full")


async def test_hide_highlight():
    """hide_highlight hides all bars."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        screen = await _push_overlay(app, pilot)
        screen.show_highlight(dtc.id, dtc.region, "full")
        screen.hide_highlight(dtc.id)
        highlight = screen._highlights[dtc.id]
        assert not highlight.is_mode("full")
        assert not highlight.is_mode("edge")


async def test_clear_all_highlights():
    """clear_all hides all highlights."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        screen = await _push_overlay(app, pilot)
        screen.show_highlight(dtc.id, dtc.region, "full")
        screen.clear_all()
        for h in screen._highlights.values():
            assert not h.is_mode("full")
            assert not h.is_mode("edge-right")


async def test_show_drop_overlay_via_dtc():
    """DTC.show_drop_overlay() updates DropTargetScreen highlight."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        screen = await _push_overlay(app, pilot)
        dtc.show_drop_overlay()
        assert screen._highlights[dtc.id].is_mode("full")


async def test_show_edge_overlay_via_dtc():
    """DTC.show_edge_overlay() updates DropTargetScreen highlight."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        screen = await _push_overlay(app, pilot)
        dtc.show_edge_overlay("right")
        assert screen._highlights[dtc.id].is_mode("edge-right")


async def test_hide_drop_overlay_via_dtc():
    """DTC.hide_drop_overlay() removes highlight."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        screen = await _push_overlay(app, pilot)
        dtc.show_drop_overlay()
        dtc.hide_drop_overlay()
        highlight = screen._highlights[dtc.id]
        assert not highlight.is_mode("full")
        assert not highlight.is_mode("edge-right")


async def test_highlight_hint_centered_in_dtc_region():
    """DropHintBox is exactly centered within the DTC region in full mode."""
    from textual_code.widgets.draggable_tabs_content import FULL_LABEL

    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        screen = await _push_overlay(app, pilot)
        screen.show_highlight(dtc.id, dtc.region, "full")
        highlight = screen._highlights[dtc.id]
        # Hint box should be visible and within DTC region bounds
        assert highlight.hint.styles.display == "block"
        hint_x = highlight.hint.styles.offset.x.value
        hint_y = highlight.hint.styles.offset.y.value
        assert hint_x >= dtc.region.x
        assert hint_y >= dtc.region.y
        # Exact centering check
        box_w = len(FULL_LABEL) + 4
        box_h = 3
        expected_x = dtc.region.x + max(0, (dtc.region.width - box_w) // 2)
        expected_y = dtc.region.y + max(0, (dtc.region.height - box_h) // 2)
        assert hint_x == expected_x
        assert hint_y == expected_y


# ── Additional tests ──────────────────────────────────────────────────────────


async def test_hide_highlight_is_idempotent():
    """Calling hide_highlight when already hidden is a no-op (cached)."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        screen = await _push_overlay(app, pilot)
        # Never shown — hide should be a no-op
        screen.hide_highlight(dtc.id)
        assert not screen._highlights[dtc.id].is_mode("full")
        assert not screen._highlights[dtc.id].is_mode("edge-right")


async def test_show_then_switch_mode():
    """Switching from full to edge-right mode updates correctly."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        screen = await _push_overlay(app, pilot)
        screen.show_highlight(dtc.id, dtc.region, "full")
        assert screen._highlights[dtc.id].is_mode("full")
        screen.show_highlight(dtc.id, dtc.region, "edge-right")
        assert screen._highlights[dtc.id].is_mode("edge-right")
        assert not screen._highlights[dtc.id].is_mode("full")


async def test_hint_box_label_matches_mode():
    """DropHintBox shows correct label text for each mode."""
    from textual_code.widgets.draggable_tabs_content import EDGE_LABELS, FULL_LABEL

    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        screen = await _push_overlay(app, pilot)
        # Full mode
        screen.show_highlight(dtc.id, dtc.region, "full")
        hint = screen._highlights[dtc.id].hint
        await pilot.pause()
        assert FULL_LABEL in str(hint.render())
        # Edge-right mode
        screen.show_highlight(dtc.id, dtc.region, "edge-right")
        await pilot.pause()
        assert EDGE_LABELS["right"] in str(hint.render())
        # Edge-down mode
        screen.show_highlight(dtc.id, dtc.region, "edge-down")
        await pilot.pause()
        assert EDGE_LABELS["down"] in str(hint.render())


async def test_overlay_screen_no_dtc_ids():
    """DropTargetScreen with no DTC IDs has no highlights."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        screen = DropTargetScreen()
        app.push_screen(screen)
        await pilot.pause()
        assert len(screen._highlights) == 0
        assert len(screen.query(DropHintBox)) == 0


async def test_show_drop_overlay_noop_without_screen():
    """show_drop_overlay is a no-op when no overlay screen is pushed."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        assert dtc._overlay_screen is None
        # Should not raise
        dtc.show_drop_overlay()
        dtc.show_edge_overlay("right")
        dtc.hide_drop_overlay()


async def test_push_pop_overlay_screen_via_dtc():
    """_push_overlay_screen and _pop_overlay_screen manage screen lifecycle."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        dtc.capture_mouse()
        dtc._push_overlay_screen()
        await pilot.pause()
        assert dtc._overlay_screen is not None
        assert len(app.screen_stack) == 2
        # Mouse capture should be re-established
        assert app.mouse_captured is dtc
        dtc._pop_overlay_screen()
        await pilot.pause()
        assert dtc._overlay_screen is None
        assert len(app.screen_stack) == 1


async def test_mouse_event_forwarded_through_overlay():
    """Mouse events are forwarded through DropTargetScreen to captured widget."""
    from textual.widgets._tabbed_content import ContentTabs

    class TwoTabApp(App):
        def compose(self):
            with DraggableTabbedContent(id="dtc"):
                yield TabPane("Tab1", id="pane1")
                yield TabPane("Tab2", id="pane2")

    app = TwoTabApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        tabs = list(dtc.get_child_by_type(ContentTabs).query("ContentTab"))
        # Mouse down on first tab
        tab_region = tabs[0].region
        offset = (
            tab_region.x - dtc.region.x + tab_region.width // 2,
            tab_region.y - dtc.region.y + tab_region.height // 2,
        )
        await pilot.mouse_down(dtc, offset=offset)
        await pilot.pause()
        assert dtc._drag_start is not None
        # Hover to second tab to trigger drag
        tab2_region = tabs[1].region
        offset2 = (
            tab2_region.x - dtc.region.x + tab2_region.width // 2,
            tab2_region.y - dtc.region.y + tab2_region.height // 2,
        )
        await pilot.hover(dtc, offset=offset2)
        await pilot.pause()
        assert dtc._dragging is True
        assert dtc._overlay_screen is not None
        # Mouse up — should be forwarded through overlay screen
        await pilot.mouse_up(dtc, offset=offset2)
        await pilot.pause()
        assert dtc._dragging is False
        assert dtc._overlay_screen is None


# ── Message tests ─────────────────────────────────────────────────────────────


async def test_tab_moved_message_target_none_allowed():
    """TabMovedToOtherSplit can be constructed with target_pane_id=None."""
    msg = DraggableTabbedContent.TabMovedToOtherSplit("some-pane", None, False)
    assert msg.source_pane_id == "some-pane"
    assert msg.target_pane_id is None
    assert msg.before is False


async def test_tab_moved_message_with_split_direction():
    """TabMovedToOtherSplit stores split_direction."""
    msg = DraggableTabbedContent.TabMovedToOtherSplit(
        "pane-1", None, False, split_direction="down"
    )
    assert msg.split_direction == "down"
    # Default is None
    msg2 = DraggableTabbedContent.TabMovedToOtherSplit("pane-1", None, False)
    assert msg2.split_direction is None


# ── 4-direction edge zone tests ───────────────────────────────────────────────


async def test_in_edge_zone_top_edge_returns_up():
    """Cursor near top boundary → _in_edge_zone returns 'up'."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        center_x = dtc.region.x + dtc.region.width // 2
        assert dtc._in_edge_zone(center_x, dtc.region.y) == "up"


async def test_in_edge_zone_bottom_edge_returns_down():
    """Cursor near bottom boundary → _in_edge_zone returns 'down'."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        center_x = dtc.region.x + dtc.region.width // 2
        assert dtc._in_edge_zone(center_x, dtc.region.bottom - 1) == "down"


async def test_in_edge_zone_corner_picks_deeper_axis():
    """Corner: edge with deeper fractional penetration wins."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        # Right edge zone width ~12, bottom edge zone height ~3.
        # At (right - 3, bottom - 1): fraction_right = 2/12 ≈ 0.17,
        # fraction_down = 0/3 = 0.0. "down" wins (deeper penetration).
        result = dtc._in_edge_zone(dtc.region.right - 3, dtc.region.bottom - 1)
        assert result == "down"
        # At (right - 1, bottom - 1): both at exact edge (fraction 0).
        # Tie-break: horizontal wins → "right"
        result = dtc._in_edge_zone(dtc.region.right - 1, dtc.region.bottom - 1)
        assert result == "right"


async def test_in_edge_zone_small_pane():
    """Edge zone detection works with small pane dimensions."""
    app = EdgeZoneApp()
    async with app.run_test(size=(20, 10)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        # Right edge should still work on small pane
        result = dtc._in_edge_zone(
            dtc.region.right - 1, dtc.region.y + dtc.region.height // 2
        )
        assert result == "right"
        # Left edge
        result = dtc._in_edge_zone(dtc.region.x, dtc.region.y + dtc.region.height // 2)
        assert result == "left"


async def test_show_edge_overlay_all_directions():
    """show_edge_overlay with each direction shows the correct mode."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        screen = await _push_overlay(app, pilot)
        for direction in ("left", "right", "up", "down"):
            dtc.show_edge_overlay(direction)
            assert screen._highlights[dtc.id].is_mode(f"edge-{direction}")


async def test_hint_box_positioned_near_edge():
    """DropHintBox is positioned near the corresponding edge in edge modes."""
    from textual_code.widgets.draggable_tabs_content import EDGE_LABELS

    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        screen = await _push_overlay(app, pilot)
        region = dtc.region
        highlight = screen._highlights[dtc.id]
        box_h = 3
        centered_y = region.y + max(0, (region.height - box_h) // 2)

        # edge-left: near left edge, vertically centered
        screen.show_highlight(dtc.id, region, "edge-left")
        box_w = len(EDGE_LABELS["left"]) + 4
        assert highlight.hint.styles.offset.x.value == region.x + 1
        assert highlight.hint.styles.offset.y.value == centered_y

        # edge-right: near right edge, vertically centered
        screen.show_highlight(dtc.id, region, "edge-right")
        box_w = len(EDGE_LABELS["right"]) + 4
        assert (
            highlight.hint.styles.offset.x.value == region.x + region.width - box_w - 1
        )
        assert highlight.hint.styles.offset.y.value == centered_y

        # edge-up: horizontally centered, near top edge
        screen.show_highlight(dtc.id, region, "edge-up")
        box_w = len(EDGE_LABELS["up"]) + 4
        centered_x = region.x + max(0, (region.width - box_w) // 2)
        assert highlight.hint.styles.offset.x.value == centered_x
        assert highlight.hint.styles.offset.y.value == region.y

        # edge-down: horizontally centered, near bottom edge
        screen.show_highlight(dtc.id, region, "edge-down")
        box_w = len(EDGE_LABELS["down"]) + 4
        centered_x = region.x + max(0, (region.width - box_w) // 2)
        assert highlight.hint.styles.offset.x.value == centered_x
        assert highlight.hint.styles.offset.y.value == region.y + region.height - box_h


async def test_hint_box_clamped_in_small_region():
    """DropHintBox stays within region bounds even for regions smaller than the box."""
    from textual.geometry import Region

    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        screen = await _push_overlay(app, pilot)
        highlight = screen._highlights[dtc.id]
        # Region smaller than any hint box (box_w ~14, box_h 3)
        small = Region(5, 3, 10, 4)
        for direction in ("left", "right", "up", "down"):
            screen.show_highlight(dtc.id, small, f"edge-{direction}")
            hint_x = highlight.hint.styles.offset.x.value
            hint_y = highlight.hint.styles.offset.y.value
            assert hint_x >= small.x, (
                f"edge-{direction}: hint_x={hint_x} < region.x={small.x}"
            )
            assert hint_y >= small.y, (
                f"edge-{direction}: hint_y={hint_y} < region.y={small.y}"
            )


# ── NoWidget crash tests ─────────────────────────────────────────────────────


async def test_update_drop_target_no_crash_at_screen_edge():
    """_update_drop_target does not crash when cursor is at screen boundary."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        # Coordinates at and beyond screen edge — should not raise NoWidget
        dtc._update_drop_target(80, 12)  # x == screen width
        dtc._update_drop_target(100, 12)  # x beyond screen
        dtc._update_drop_target(40, 24)  # y == screen height
        dtc._update_drop_target(40, 100)  # y beyond screen


async def test_on_mouse_down_no_crash_at_screen_edge():
    """on_mouse_down does not crash when click is at screen boundary."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        dtc.on_mouse_down(_mouse_down(dtc, 80, 12))  # should not raise


async def test_on_mouse_up_no_crash_at_screen_edge():
    """on_mouse_up does not crash when release is at screen boundary."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        # Set up drag state to make on_mouse_up process the event
        dtc._dragging = True
        dtc._drag_pane_id = "pane1"
        dtc._drag_start = (40, 12)
        dtc.on_mouse_up(_mouse_up(dtc, 80, 12))  # should not raise


async def test_update_drop_target_negative_coordinates():
    """_update_drop_target does not crash with negative coordinates."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        dtc._update_drop_target(-1, 12)
        dtc._update_drop_target(40, -1)
        dtc._update_drop_target(-10, -10)


async def test_update_drop_target_corner_out_of_bounds():
    """_update_drop_target does not crash at corners beyond screen bounds."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        # All four corners beyond screen
        dtc._update_drop_target(80, 24)  # bottom-right
        dtc._update_drop_target(-1, -1)  # top-left beyond
        dtc._update_drop_target(80, -1)  # top-right beyond
        dtc._update_drop_target(-1, 24)  # bottom-left beyond


async def test_update_drop_target_clears_existing_target_on_edge():
    """When cursor moves to screen edge, any existing drop target is cleared."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        # First call with valid coordinate to set _drop_target
        dtc._update_drop_target(40, 12)
        # Then move to screen edge — should clear without crash
        dtc._update_drop_target(80, 12)
        assert dtc._drop_target is None


async def test_on_mouse_down_at_screen_edge_no_drag_start():
    """Mouse down at screen edge does not initiate drag."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        assert dtc._drag_start is None
        dtc.on_mouse_down(_mouse_down(dtc, 80, 12))
        # Drag should not have started because no ContentTab at that position
        assert dtc._drag_start is None
        assert dtc._drag_pane_id is None


async def test_on_mouse_up_at_screen_edge_with_edge_direction():
    """on_mouse_up at screen edge with an edge_direction does not crash."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        # Set up drag state with edge direction (as if dragging to edge zone)
        dtc._dragging = True
        dtc._drag_pane_id = "pane1"
        dtc._drag_start = (40, 12)
        dtc._edge_direction = "right"
        dtc.on_mouse_up(_mouse_up(dtc, 80, 12))
        # Drag state should be cleaned up
        assert dtc._dragging is False
        assert dtc._drag_pane_id is None


async def test_on_mouse_up_at_screen_edge_resets_drag_state():
    """on_mouse_up at screen edge properly resets all drag state."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        dtc._dragging = True
        dtc._drag_pane_id = "pane1"
        dtc._drag_start = (40, 12)
        dtc._edge_direction = None
        dtc._drop_target = None
        dtc.on_mouse_up(_mouse_up(dtc, -1, -1))
        assert dtc._dragging is False
        assert dtc._drag_start is None
        assert dtc._drag_pane_id is None
