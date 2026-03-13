# Relies on Textual internals (tested against textual 0.x):
# ContentTab, ContentTabs from textual.widgets._tabbed_content
# ContentSwitcher from textual.widgets._content_switcher
from textual import events
from textual.message import Message
from textual.widgets import TabbedContent
from textual.widgets._content_switcher import ContentSwitcher  # internal
from textual.widgets._tabbed_content import ContentTab, ContentTabs  # internal

DRAG_THRESHOLD = 3  # pixels (euclidean distance)
EDGE_ZONE_FRACTION = 0.15  # fraction of widget size that counts as edge zone


class DraggableTabbedContent(TabbedContent):
    """TabbedContent subclass that supports tab reordering via mouse drag."""

    class TabMovedToOtherSplit(Message):
        """Posted when a tab is dropped onto a ContentTab in a different split,
        or into the edge zone to create a new split.

        target_pane_id is None when dropped in the edge zone (create new split).
        """

        def __init__(
            self, source_pane_id: str, target_pane_id: str | None, before: bool
        ) -> None:
            super().__init__()
            self.source_pane_id = source_pane_id
            self.target_pane_id = target_pane_id
            self.before = before

    def __init__(self, *args, split_side: str = "left", **kwargs):
        super().__init__(*args, **kwargs)
        self._split_side = split_side  # "left", "right", "top", "bottom"
        self._drag_pane_id: str | None = None
        self._drag_start: tuple[int, int] | None = None
        self._dragging: bool = False

    # ── Edge zone helpers ──────────────────────────────────────────────────────

    def _is_vertical_split(self) -> bool:
        """Return True if this split is in a vertical (top/bottom) layout."""
        container = next((a for a in self.ancestors if a.id == "split_container"), None)
        return container is not None and container.has_class("split-vertical")

    def _edge_zone_width(self) -> int:
        """Width (or height for vertical) of the edge drop zone in cells."""
        is_vertical = self._is_vertical_split()
        size = self.region.height if is_vertical else self.region.width
        return max(5, min(15, int(size * EDGE_ZONE_FRACTION)))

    def _in_edge_zone(self, screen_x: int, screen_y: int) -> bool:
        """Return True if (screen_x, screen_y) is in the edge zone for this split."""
        if self._split_side == "left":
            return screen_x >= self.region.right - self._edge_zone_width()
        elif self._split_side == "right":
            return screen_x <= self.region.x + self._edge_zone_width()
        elif self._split_side == "top":
            return (
                screen_y >= self.region.y + self.region.height - self._edge_zone_width()
            )
        elif self._split_side == "bottom":
            return screen_y <= self.region.y + self._edge_zone_width()
        return False

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
            self.set_class(
                self._in_edge_zone(event.screen_x, event.screen_y), "-edge-hover"
            )

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
        self.remove_class("-edge-hover")

        # Determine drop target
        widget, region = self.screen.get_widget_at(event.screen_x, event.screen_y)
        self.release_mouse()

        if not isinstance(widget, ContentTab) or not widget.id:
            # Edge zone → create new split by posting with target_pane_id=None
            # Guard: don't move if it's the last tab
            if (
                drag_id
                and self._in_edge_zone(event.screen_x, event.screen_y)
                and len(list(self.query(ContentTab))) > 1
            ):
                self.post_message(self.TabMovedToOtherSplit(drag_id, None, False))
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
            owner = next(
                (a for a in widget.ancestors if isinstance(a, DraggableTabbedContent)),
                None,
            )
            if owner is not None and owner is not self:
                target_id = ContentTab.sans_prefix(widget.id)
                before = (event.screen_x - region.x) < region.width / 2
                self.post_message(self.TabMovedToOtherSplit(drag_id, target_id, before))

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
