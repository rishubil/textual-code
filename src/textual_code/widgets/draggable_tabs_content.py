# Relies on Textual internals (tested against textual 0.x):
# ContentTab, ContentTabs from textual.widgets._tabbed_content
# ContentSwitcher from textual.widgets._content_switcher
# Underline from textual.widgets._tabs
from __future__ import annotations

from typing import cast

from textual import errors, events
from textual.css.query import NoMatches
from textual.geometry import Region
from textual.message import Message
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Static, TabbedContent
from textual.widgets._content_switcher import ContentSwitcher  # internal
from textual.widgets._tabbed_content import ContentTab, ContentTabs  # internal
from textual.widgets._tabs import Underline  # internal

from textual_code.widgets.split_tree import Direction

DRAG_THRESHOLD = 3  # pixels (euclidean distance)
EDGE_ZONE_FRACTION = 0.15  # fraction of widget size that counts as edge zone


FULL_LABEL = "Move to this pane"
EDGE_LABELS: dict[str, str] = {
    "left": "Split left",
    "right": "Split right",
    "up": "Split up",
    "down": "Split down",
}


class DropHintBox(Static):
    """A small centered label shown on a DropTargetScreen to indicate a drop zone.

    Only this box is visible on the overlay screen; the rest of the screen
    is transparent, so the pane content beneath remains fully visible.
    """

    DEFAULT_CSS = """
    DropHintBox {
        display: none;
        position: absolute;
        background: $accent;
        color: $text;
        text-style: bold;
        content-align: center middle;
        width: auto;
        height: 3;
        padding: 0 2;
    }
    """


class DropHighlight:
    """Manages a DropHintBox widget positioned over a DTC region."""

    def __init__(self, dtc_id: str) -> None:
        self.dtc_id = dtc_id
        self.hint: DropHintBox = DropHintBox(id=f"hl-hint-{dtc_id}")
        self._mode: str | None = None

    @property
    def widgets(self) -> list[DropHintBox]:
        return [self.hint]

    def show(self, region: Region, mode: str) -> None:
        """Position and display the hint box in the given region.

        For 'full' mode the box is centered.  For edge modes it is placed
        near the corresponding edge so the user sees the hint close to
        where the split will appear.
        """
        self._mode = mode
        x, y, w, h = region.x, region.y, region.width, region.height

        if mode.startswith("edge-"):
            direction = mode.split("-", 1)[1]
            label = EDGE_LABELS[direction]
        else:
            direction = None
            label = FULL_LABEL
        box_w = len(label) + 4  # 2 padding each side
        box_h = 3
        cx = x + max(0, (w - box_w) // 2)
        cy = y + max(0, (h - box_h) // 2)

        if direction is not None:
            margin_x = 1
            margin_y = 0
            if direction == "left":
                cx = x + margin_x
            elif direction == "right":
                cx = max(x, x + w - box_w - margin_x)
            elif direction == "up":
                cy = y + margin_y
            elif direction == "down":
                cy = max(y, y + h - box_h - margin_y)

        self.hint.update(label)
        self.hint.styles.offset = (cx, cy)
        self.hint.styles.width = box_w
        self.hint.styles.height = box_h
        self.hint.display = True

    def hide(self) -> None:
        """Hide the hint box."""
        self._mode = None
        self.hint.display = False

    def is_mode(self, mode: str) -> bool:
        """Check if this highlight is currently in the given mode."""
        return self._mode == mode


class DropTargetScreen(Screen):
    """Transparent overlay screen for semi-transparent drop-target highlights.

    Pushed during tab drag to show highlight widgets that composite
    transparently over the content beneath (Textual composites screens
    with true alpha blending, unlike widget layers).

    All mouse and Enter/Leave events are forwarded to the screen below
    so that drag-and-drop continues to function normally.
    """

    DEFAULT_CSS = """
    DropTargetScreen {
        background: transparent;
    }
    """

    def __init__(self, dtc_ids: list[str] | None = None) -> None:
        super().__init__()
        self._highlights: dict[str, DropHighlight] = {}
        # Cache: dtc_id → (region, mode) to skip redundant updates
        self._highlight_state: dict[str, tuple[Region, str]] = {}
        # Pre-create highlight bar groups so they're available before mount
        for dtc_id in dtc_ids or []:
            self._highlights[dtc_id] = DropHighlight(dtc_id)

    def compose(self):
        for highlight in self._highlights.values():
            yield from highlight.widgets

    def _forward_event(self, event: events.Event) -> None:
        """Forward mouse and Enter/Leave events to the screen below."""
        if event.is_forwarded:
            return
        if isinstance(event, (events.MouseEvent, events.Enter, events.Leave)):
            if len(self.app.screen_stack) >= 2:
                try:
                    prev_screen = self.app.screen_stack[-2]
                    prev_screen._forward_event(event)
                except (LookupError, AttributeError):
                    self.log.warning(
                        f"Failed to forward {type(event).__name__} to previous screen"
                    )
            return
        super()._forward_event(event)

    def show_highlight(self, dtc_id: str, region: Region, mode: str) -> None:
        """Show a highlight over the given DTC region."""
        cached = self._highlight_state.get(dtc_id)
        if cached and cached == (region, mode):
            return
        self._highlight_state[dtc_id] = (region, mode)

        highlight = self._highlights.get(dtc_id)
        if highlight is None:
            return
        highlight.show(region, mode)
        self.log.debug(f"Show highlight {mode} on {dtc_id} at {region}")

    def hide_highlight(self, dtc_id: str) -> None:
        """Hide the highlight for the given DTC."""
        if dtc_id not in self._highlight_state:
            return
        self._highlight_state.pop(dtc_id, None)
        highlight = self._highlights.get(dtc_id)
        if highlight is None:
            return
        highlight.hide()
        self.log.debug(f"Hide highlight on {dtc_id}")

    def clear_all(self) -> None:
        """Hide all highlight widgets."""
        self._highlight_state.clear()
        for highlight in self._highlights.values():
            highlight.hide()
        self.log.debug("Cleared all highlights")


class DraggableTabbedContent(TabbedContent):
    """TabbedContent subclass that supports tab reordering via mouse drag."""

    class TabMovedToOtherSplit(Message):
        """Posted when a tab is dropped onto a ContentTab in a different split,
        or into the edge zone to create a new split.

        target_pane_id is None when dropped in the edge zone (create new split).
        target_dtc_id identifies the destination DraggableTabbedContent (leaf).
        """

        def __init__(
            self,
            source_pane_id: str,
            target_pane_id: str | None,
            before: bool,
            target_dtc_id: str | None = None,
            split_direction: Direction | None = None,
        ) -> None:
            super().__init__()
            self.source_pane_id = source_pane_id
            self.target_pane_id = target_pane_id
            self.before = before
            self.target_dtc_id = target_dtc_id
            self.split_direction = split_direction

    def __init__(self, *args, split_side: str = "left", **kwargs):
        super().__init__(*args, **kwargs)
        # split_side kept for backward compat but no longer used for edge detection
        self._split_side = split_side
        self._drag_pane_id: str | None = None
        self._drag_start: tuple[int, int] | None = None
        self._dragging: bool = False
        self._drop_target: DraggableTabbedContent | None = None
        self._overlay_screen: DropTargetScreen | None = None
        self._edge_direction: Direction | None = None

    # ── Drop highlight helpers ────────────────────────────────────────────────

    def show_drop_overlay(self) -> None:
        """Show full-pane drop target highlight via overlay screen."""
        if self._overlay_screen:
            self._overlay_screen.show_highlight(self.id, self.region, "full")

    def show_edge_overlay(self, direction: Direction = "right") -> None:
        """Show edge drop zone highlight via overlay screen."""
        if self._overlay_screen:
            self._overlay_screen.show_highlight(
                self.id, self.region, f"edge-{direction}"
            )

    def hide_drop_overlay(self) -> None:
        """Hide all drop highlight overlays."""
        if self._overlay_screen:
            self._overlay_screen.hide_highlight(self.id)

    def _push_overlay_screen(self) -> None:
        """Push the transparent overlay screen and set references on all DTCs."""
        dtcs = list(self.screen.query(DraggableTabbedContent))
        dtc_ids = [dtc.id for dtc in dtcs]
        overlay_screen = DropTargetScreen(dtc_ids)
        self._overlay_screen = overlay_screen
        # Set overlay_screen on all sibling DTCs so they can update highlights
        for dtc in dtcs:
            dtc._overlay_screen = overlay_screen
        self.app.push_screen(overlay_screen)
        # push_screen releases mouse capture; re-establish it so mouse events
        # continue to be routed to this DTC via the overlay screen's forwarding.
        self.app.capture_mouse(self)
        self.log.debug("Pushed DropTargetScreen")

    def _pop_overlay_screen(self) -> None:
        """Pop the overlay screen and clear references on all DTCs."""
        if self._overlay_screen:
            self._overlay_screen.clear_all()
            self.app.pop_screen()
            self.log.debug("Popped DropTargetScreen")
        # Clear references on all sibling DTCs
        for dtc in self.screen.query(DraggableTabbedContent):
            dtc._overlay_screen = None

    # ── Edge zone helpers ──────────────────────────────────────────────────────

    def _edge_zone_width(self) -> int:
        """Width of the horizontal edge drop zone in cells."""
        size = self.region.width
        return max(5, min(15, int(size * EDGE_ZONE_FRACTION)))

    def _edge_zone_height(self) -> int:
        """Height of the vertical edge drop zone in cells."""
        size = self.region.height
        return max(2, min(8, int(size * EDGE_ZONE_FRACTION)))

    def _in_edge_zone(self, screen_x: int, screen_y: int) -> Direction | None:
        """Return split direction if cursor is in an edge zone, else None.

        Checks all 4 edges. On corner overlap, the edge with deeper fractional
        penetration wins; horizontal (left/right) wins ties.
        """
        if not self.region.contains_point((screen_x, screen_y)):
            return None
        region = self.region
        edge_w = self._edge_zone_width()
        edge_h = self._edge_zone_height()

        candidates: list[tuple[Direction, float]] = []
        # Only check an axis if edge zones don't overlap (cover center)
        if edge_w * 2 < region.width:
            dist_right = region.right - 1 - screen_x
            if dist_right < edge_w:
                candidates.append(("right", dist_right / edge_w))
            dist_left = screen_x - region.x
            if dist_left < edge_w:
                candidates.append(("left", dist_left / edge_w))
        if edge_h * 2 < region.height:
            dist_bottom = region.bottom - 1 - screen_y
            if dist_bottom < edge_h:
                candidates.append(("down", dist_bottom / edge_h))
            dist_top = screen_y - region.y
            if dist_top < edge_h:
                candidates.append(("up", dist_top / edge_h))

        if not candidates:
            return None
        # Pick edge with smallest fractional depth (deepest penetration).
        # Sort by fraction, then prefer horizontal (left/right) on tie.
        candidates.sort(key=lambda c: (c[1], c[0] in ("up", "down")))
        return candidates[0][0]

    def _find_ancestor_dtc(self, widget) -> DraggableTabbedContent | None:
        """Find the nearest DraggableTabbedContent ancestor."""
        return next(
            (
                a
                for a in widget.ancestors_with_self
                if isinstance(a, DraggableTabbedContent)
            ),
            None,
        )

    def _get_widget_at_or_none(
        self, screen_x: int, screen_y: int
    ) -> tuple[Widget | None, Region | None]:
        """Like screen.get_widget_at but returns (None, None) at screen edges."""
        try:
            return self.screen.get_widget_at(screen_x, screen_y)
        except errors.NoWidget:
            return None, None

    def _update_drop_target(self, screen_x: int, screen_y: int) -> None:
        """Show/hide drop overlay on the sibling DTC under the cursor."""
        widget, _ = self._get_widget_at_or_none(screen_x, screen_y)
        target = self._find_ancestor_dtc(widget) if widget is not None else None
        if target is self or target is None:
            target = None

        if target is self._drop_target:
            return

        if self._drop_target is not None:
            self._drop_target.hide_drop_overlay()
        self._drop_target = target
        if self._drop_target is not None:
            self._drop_target.show_drop_overlay()

    # ── Mouse event handlers ───────────────────────────────────────────────────

    def on_mouse_down(self, event: events.MouseDown) -> None:
        widget, _ = self._get_widget_at_or_none(event.screen_x, event.screen_y)
        # Verify the widget is a ContentTab owned by this TabbedContent
        if (
            isinstance(widget, ContentTab)
            and widget.id
            and widget in self.query(ContentTab)
        ):
            self._drag_pane_id = ContentTab.sans_prefix(widget.id)
            self._drag_start = (event.screen_x, event.screen_y)

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._drag_start is None:
            return
        if not self._dragging:
            dx = event.screen_x - self._drag_start[0]
            dy = event.screen_y - self._drag_start[1]
            if dx * dx + dy * dy >= DRAG_THRESHOLD * DRAG_THRESHOLD:
                self._dragging = True
                self.capture_mouse()
                self._push_overlay_screen()
                # Visual feedback: highlight dragged tab
                # IDs like "--content-tab-..." are invalid CSS selectors,
                # so match by .id attribute directly instead of query_one.
                if self._drag_pane_id:
                    drag_tab_id = ContentTab.add_prefix(self._drag_pane_id)
                    content_tabs = self.get_child_by_type(ContentTabs)
                    drag_tab = next(
                        (
                            t
                            for t in content_tabs.query(ContentTab)
                            if t.id == drag_tab_id
                        ),
                        None,
                    )
                    if drag_tab:
                        drag_tab.add_class("-dragging")

        # Update edge hover visual during drag
        if self._dragging:
            edge_dir = self._in_edge_zone(event.screen_x, event.screen_y)
            if edge_dir is not None:
                self._edge_direction = edge_dir
                self.show_edge_overlay(edge_dir)
            else:
                self._edge_direction = None
                self.hide_drop_overlay()
            self._update_drop_target(event.screen_x, event.screen_y)

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if not self._dragging:
            self._drag_pane_id = None
            self._drag_start = None
            return

        drag_id = self._drag_pane_id
        edge_direction = self._edge_direction
        self._drag_pane_id = None
        self._drag_start = None
        self._dragging = False
        self._edge_direction = None

        # Remove visual feedback
        for tab in self.query(ContentTab):
            tab.remove_class("-dragging")
        self.hide_drop_overlay()

        # Capture tracked drop target before clearing
        tracked_target = self._drop_target
        if self._drop_target is not None:
            self._drop_target.hide_drop_overlay()
            self._drop_target = None

        # Pop overlay screen before determining drop target
        self._pop_overlay_screen()

        # Determine drop target
        widget, region = self._get_widget_at_or_none(event.screen_x, event.screen_y)
        self.release_mouse()

        if not isinstance(widget, ContentTab) or not widget.id:
            if not drag_id:
                return
            # Edge zone → create new split by posting with target_pane_id=None
            # Use stored _edge_direction (regions may shift after overlay pop)
            if edge_direction is not None and len(list(self.query(ContentTab))) > 1:
                self.post_message(
                    self.TabMovedToOtherSplit(
                        drag_id, None, False, split_direction=edge_direction
                    )
                )
                return
            # Use tracked drop target (highlighted DTC) as primary,
            # fall back to hit-test
            target_dtc = tracked_target
            if target_dtc is None and widget is not None:
                target_dtc = self._find_ancestor_dtc(widget)
            if target_dtc is not None and target_dtc is not self:
                self.post_message(
                    self.TabMovedToOtherSplit(
                        drag_id, None, False, target_dtc_id=target_dtc.id
                    )
                )
            else:
                self.log.debug(f"Drop ignored: no valid target DTC for pane {drag_id}")
            return

        if widget in self.query(ContentTab):
            # Same-split reorder (existing logic)
            assert region is not None  # widget found ⇒ region exists
            target_id = ContentTab.sans_prefix(widget.id)
            if drag_id and target_id != drag_id:
                before = (event.screen_x - region.x) < region.width / 2
                self.reorder_tab(drag_id, target_id, before=before)
            return

        # Cross-split: find sibling DraggableTabbedContent that owns this tab
        if drag_id:
            assert region is not None  # widget found ⇒ region exists
            owner = self._find_ancestor_dtc(widget)
            if owner is not None and owner is not self:
                target_id = ContentTab.sans_prefix(widget.id)
                before = (event.screen_x - region.x) < region.width / 2
                self.post_message(
                    self.TabMovedToOtherSplit(
                        drag_id, target_id, before, target_dtc_id=owner.id
                    )
                )

    def reorder_tab(self, pane_id: str, target_id: str, *, before: bool = True) -> None:
        """Reorder pane_id to be before/after target_id.

        No-op if not mounted or if pane_id/target_id are invalid.
        """
        if not self.is_mounted:
            return
        content_tabs = self.get_child_by_type(ContentTabs)
        content_switcher = self.get_child_by_type(ContentSwitcher)

        # ContentTab widgets live inside Horizontal(id='tabs-list'), not directly
        # under ContentTabs. Use the actual parent for move_child.
        # get_child_by_id uses CSS selectors; IDs like "--content-tab-..." are
        # invalid CSS, so we match by .id attribute directly.
        drag_tab_id = ContentTab.add_prefix(pane_id)
        target_tab_id = ContentTab.add_prefix(target_id)

        all_tabs = list(content_tabs.query(ContentTab))
        drag_tab = next((t for t in all_tabs if t.id == drag_tab_id), None)
        target_tab = next((t for t in all_tabs if t.id == target_tab_id), None)
        drag_pane = next(
            (p for p in content_switcher.children if p.id == pane_id), None
        )
        target_pane = next(
            (p for p in content_switcher.children if p.id == target_id), None
        )

        # Guard: any of these being None means invalid pane_id → noop
        if (
            drag_tab is None
            or target_tab is None
            or drag_pane is None
            or target_pane is None
        ):
            return

        # ContentTab's actual parent is Horizontal(id='tabs-list') inside ContentTabs
        tabs_list = cast(Widget, drag_tab.parent)

        with self.app.batch_update():
            if before:
                tabs_list.move_child(drag_tab, before=target_tab)
                content_switcher.move_child(drag_pane, before=target_pane)
            else:
                tabs_list.move_child(drag_tab, after=target_tab)
                content_switcher.move_child(drag_pane, after=target_pane)
        content_tabs.refresh(layout=True)

        # move_child() doesn't update the underline position; trigger manually.
        # We implement move_underline inline (instead of calling _highlight_active)
        # to avoid the double call_after_refresh chain inside _highlight_active.
        # Retry if layout hasn't propagated yet (virtual_region returns degenerate
        # region with start >= end before the compositor updates tab positions).
        def _move_underline(retries_left: int = 5) -> None:
            if not content_tabs.is_mounted:
                return
            try:
                active_tab = content_tabs.query_one("#tabs-list > Tab.-active")
                underline = content_tabs.query_one(Underline)
            except NoMatches:
                return
            active_region = active_tab.virtual_region
            if active_region.width < 3:
                # Layout or CSS not yet applied (min valid width = 1 char + 2 padding).
                # Retry after the next refresh cycle.
                if retries_left > 0:
                    content_tabs.call_after_refresh(
                        lambda: _move_underline(retries_left - 1)
                    )
                return
            tab_region = active_region.shrink(active_tab.styles.gutter)
            start, end = tab_region.column_span
            if start >= end:
                # Degenerate region; layout not yet propagated to compositor.
                if retries_left > 0:
                    content_tabs.call_after_refresh(
                        lambda: _move_underline(retries_left - 1)
                    )
                return
            # Stop any running slide animation before setting static values.
            # Opening a tab starts a 300ms animate() on highlight_start/end;
            # without stopping it, the animator will override our values.
            # force_stop_animation is synchronous; stop_animation is async.
            content_tabs.app.animator.force_stop_animation(underline, "highlight_start")
            content_tabs.app.animator.force_stop_animation(underline, "highlight_end")
            underline.highlight_start = start
            underline.highlight_end = end

        content_tabs.call_after_refresh(_move_underline)

    def get_ordered_pane_ids(self) -> list[str]:
        """Return the pane IDs in their current visual (tab-bar) order."""
        content_tabs = self.get_child_by_type(ContentTabs)
        return [
            ContentTab.sans_prefix(t.id) for t in content_tabs.query(ContentTab) if t.id
        ]

    def reorder_active_tab_by_delta(self, delta: int) -> bool:
        """Move the active tab by *delta* positions within this tab group.

        *delta* should be 1 (right) or -1 (left).
        Returns True if the tab was moved, False otherwise (boundary / single tab).
        """
        if not self.is_mounted:
            return False
        pane_ids = self.get_ordered_pane_ids()
        active_id = self.active
        if not active_id or active_id not in pane_ids:
            return False
        idx = pane_ids.index(active_id)
        target_idx = idx + delta
        if target_idx < 0 or target_idx >= len(pane_ids):
            return False
        self.reorder_tab(active_id, pane_ids[target_idx], before=(delta < 0))
        # reorder_tab schedules _move_underline via call_after_refresh, but
        # external events (e.g. command palette dismissal) can trigger
        # _highlight_active(animate=True) which starts a 300ms animation
        # that overrides the underline position. Schedule a second update
        # after a delay to win the race against any interfering animation.
        content_tabs = self.get_child_by_type(ContentTabs)
        content_tabs.set_timer(
            0.05,
            lambda: content_tabs._highlight_active(animate=False),
        )
        return True
