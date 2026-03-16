# Relies on Textual internals (tested against textual 0.x):
# ContentTab, ContentTabs from textual.widgets._tabbed_content
# ContentSwitcher from textual.widgets._content_switcher
# Underline from textual.widgets._tabs
from textual import events
from textual.css.query import NoMatches
from textual.message import Message
from textual.widget import Widget
from textual.widgets import TabbedContent
from textual.widgets._content_switcher import ContentSwitcher  # internal
from textual.widgets._tabbed_content import ContentTab, ContentTabs  # internal
from textual.widgets._tabs import Underline  # internal

DRAG_THRESHOLD = 3  # pixels (euclidean distance)
EDGE_ZONE_FRACTION = 0.15  # fraction of widget size that counts as edge zone


class DropTargetOverlay(Widget):
    """Transparent overlay for drop target / edge zone highlight."""

    def render(self) -> str:
        return ""

    DEFAULT_CSS = """
    DropTargetOverlay {
        display: none;
        layer: overlay;
        width: 100%;
        height: 100%;
        background: transparent;
    }
    DropTargetOverlay.-visible {
        display: block;
        border: tall $accent;
    }
    DropTargetOverlay.-edge {
        display: block;
        border-right: tall $accent;
    }
    """


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
        ) -> None:
            super().__init__()
            self.source_pane_id = source_pane_id
            self.target_pane_id = target_pane_id
            self.before = before
            self.target_dtc_id = target_dtc_id

    def __init__(self, *args, split_side: str = "left", **kwargs):
        super().__init__(*args, **kwargs)
        # split_side kept for backward compat but no longer used for edge detection
        self._split_side = split_side
        self._drag_pane_id: str | None = None
        self._drag_start: tuple[int, int] | None = None
        self._dragging: bool = False
        self._drop_target: DraggableTabbedContent | None = None

    def on_mount(self) -> None:
        self.mount(DropTargetOverlay())

    # ── Overlay helpers ───────────────────────────────────────────────────────

    def show_drop_overlay(self) -> None:
        """Show full-pane drop target highlight."""
        overlay = self.query_one(DropTargetOverlay)
        overlay.remove_class("-edge")
        overlay.add_class("-visible")

    def show_edge_overlay(self) -> None:
        """Show right-edge drop zone highlight."""
        overlay = self.query_one(DropTargetOverlay)
        overlay.remove_class("-visible")
        overlay.add_class("-edge")

    def hide_drop_overlay(self) -> None:
        """Hide all overlay highlights."""
        overlay = self.query_one(DropTargetOverlay)
        overlay.remove_class("-visible", "-edge")

    # ── Edge zone helpers ──────────────────────────────────────────────────────

    def _edge_zone_width(self) -> int:
        """Width (or height for vertical) of the edge drop zone in cells."""
        size = self.region.width
        return max(5, min(15, int(size * EDGE_ZONE_FRACTION)))

    def _in_edge_zone(self, screen_x: int, screen_y: int) -> bool:
        """Return True if (screen_x, screen_y) is in the edge zone.

        Edge zone is at the right side of this widget (for horizontal splits).
        """
        return screen_x >= self.region.right - self._edge_zone_width()

    def _find_ancestor_dtc(self, widget) -> "DraggableTabbedContent | None":
        """Find the nearest DraggableTabbedContent ancestor."""
        return next(
            (
                a
                for a in widget.ancestors_with_self
                if isinstance(a, DraggableTabbedContent)
            ),
            None,
        )

    def _update_drop_target(self, screen_x: int, screen_y: int) -> None:
        """Show/hide drop overlay on the sibling DTC under the cursor."""
        widget, _ = self.screen.get_widget_at(screen_x, screen_y)
        target = self._find_ancestor_dtc(widget)
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
        widget, _ = self.screen.get_widget_at(event.screen_x, event.screen_y)
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
            if self._in_edge_zone(event.screen_x, event.screen_y):
                self.show_edge_overlay()
            else:
                self.hide_drop_overlay()
            self._update_drop_target(event.screen_x, event.screen_y)

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if not self._dragging:
            self._drag_pane_id = None
            self._drag_start = None
            return

        drag_id = self._drag_pane_id
        self._drag_pane_id = None
        self._drag_start = None
        self._dragging = False

        # Remove visual feedback
        for tab in self.query(ContentTab):
            tab.remove_class("-dragging")
        self.hide_drop_overlay()
        if self._drop_target is not None:
            self._drop_target.hide_drop_overlay()
            self._drop_target = None

        # Determine drop target
        widget, region = self.screen.get_widget_at(event.screen_x, event.screen_y)
        self.release_mouse()

        if not isinstance(widget, ContentTab) or not widget.id:
            if not drag_id:
                return
            # Edge zone → create new split by posting with target_pane_id=None
            # Guard: don't move if it's the last tab
            if (
                self._in_edge_zone(event.screen_x, event.screen_y)
                and len(list(self.query(ContentTab))) > 1
            ):
                self.post_message(self.TabMovedToOtherSplit(drag_id, None, False))
                return
            # Non-tab area of another split → move to that split
            target_dtc = self._find_ancestor_dtc(widget)
            if target_dtc is not None and target_dtc is not self:
                self.post_message(
                    self.TabMovedToOtherSplit(
                        drag_id, None, False, target_dtc_id=target_dtc.id
                    )
                )
            return

        if widget in self.query(ContentTab):
            # Same-split reorder (existing logic)
            target_id = ContentTab.sans_prefix(widget.id)
            if drag_id and target_id != drag_id:
                before = (event.screen_x - region.x) < region.width / 2
                self.reorder_tab(drag_id, target_id, before=before)
            return

        # Cross-split: find sibling DraggableTabbedContent that owns this tab
        if drag_id:
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
        if None in (drag_tab, target_tab, drag_pane, target_pane):
            return

        # ContentTab's actual parent is Horizontal(id='tabs-list') inside ContentTabs
        tabs_list = drag_tab.parent

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
