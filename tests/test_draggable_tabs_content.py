"""Unit tests for DraggableTabbedContent and DropTargetScreen."""

from textual.app import App, ComposeResult
from textual.widgets import TabPane

from textual_code.widgets.draggable_tabs_content import (
    DraggableTabbedContent,
    DropHintBox,
    DropTargetScreen,
)


class EdgeZoneApp(App):
    """Minimal app for testing DraggableTabbedContent edge zone helpers."""

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
    """Left split: x near right boundary → _in_edge_zone returns True."""
    app = EdgeZoneApp(split_side="left")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        # Right edge of widget
        assert (
            dtc._in_edge_zone(
                dtc.region.right - 1, dtc.region.y + dtc.region.height // 2
            )
            is True
        )


async def test_in_edge_zone_left_center_false():
    """Left split: x at center of widget → _in_edge_zone returns False."""
    app = EdgeZoneApp(split_side="left")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        center_x = dtc.region.x + dtc.region.width // 2
        assert (
            dtc._in_edge_zone(center_x, dtc.region.y + dtc.region.height // 2) is False
        )


async def test_in_edge_zone_right_left_edge_false():
    """x near left boundary returns False (edge zone is always right)."""
    app = EdgeZoneApp(split_side="right")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        assert (
            dtc._in_edge_zone(dtc.region.x + 1, dtc.region.y + dtc.region.height // 2)
            is False
        )


async def test_in_edge_zone_right_center_false():
    """Right split: x at center → _in_edge_zone returns False."""
    app = EdgeZoneApp(split_side="right")
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        center_x = dtc.region.x + dtc.region.width // 2
        assert (
            dtc._in_edge_zone(center_x, dtc.region.y + dtc.region.height // 2) is False
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
    """show_highlight with 'edge' mode shows only right bar."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        screen = await _push_overlay(app, pilot)
        screen.show_highlight(dtc.id, dtc.region, "edge")
        highlight = screen._highlights[dtc.id]
        assert highlight.is_mode("edge")
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
            assert not h.is_mode("edge")


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
        dtc.show_edge_overlay()
        assert screen._highlights[dtc.id].is_mode("edge")


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
        assert not highlight.is_mode("edge")


async def test_highlight_hint_centered_in_dtc_region():
    """DropHintBox is centered within the DTC region."""
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
        assert not screen._highlights[dtc.id].is_mode("edge")


async def test_show_then_switch_mode():
    """Switching from full to edge mode updates correctly."""
    app = EdgeZoneApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dtc = app.query_one("#dtc", DraggableTabbedContent)
        screen = await _push_overlay(app, pilot)
        screen.show_highlight(dtc.id, dtc.region, "full")
        assert screen._highlights[dtc.id].is_mode("full")
        screen.show_highlight(dtc.id, dtc.region, "edge")
        assert screen._highlights[dtc.id].is_mode("edge")
        assert not screen._highlights[dtc.id].is_mode("full")


async def test_hint_box_label_matches_mode():
    """DropHintBox shows correct label text for each mode."""
    from textual_code.widgets.draggable_tabs_content import EDGE_LABEL, FULL_LABEL

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
        # Edge mode
        screen.show_highlight(dtc.id, dtc.region, "edge")
        await pilot.pause()
        assert EDGE_LABEL in str(hint.render())


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
        dtc.show_edge_overlay()
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
