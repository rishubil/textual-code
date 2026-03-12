# Relies on Textual internals (tested against textual 0.x):
# ContentTab, ContentTabs from textual.widgets._tabbed_content
# ContentSwitcher from textual.widgets._content_switcher
from textual import events
from textual.widgets import TabbedContent
from textual.widgets._content_switcher import ContentSwitcher  # internal
from textual.widgets._tabbed_content import ContentTab, ContentTabs  # internal

DRAG_THRESHOLD = 3  # pixels (euclidean distance)


class DraggableTabbedContent(TabbedContent):
    """TabbedContent subclass that supports tab reordering via mouse drag."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._drag_pane_id: str | None = None
        self._drag_start: tuple[int, int] | None = None
        self._dragging: bool = False

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
        if self._drag_start is None or self._dragging:
            return
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
                    (t for t in content_tabs.query(ContentTab) if t.id == drag_tab_id),
                    None,
                )
                if drag_tab:
                    drag_tab.add_class("-dragging")

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if not self._dragging:
            self._drag_pane_id = None
            self._drag_start = None
            return

        drag_id = self._drag_pane_id
        self._drag_pane_id = None
        self._drag_start = None
        self._dragging = False

        # Remove visual feedback first
        for tab in self.query(ContentTab):
            tab.remove_class("-dragging")

        # Determine drop target
        widget, region = self.screen.get_widget_at(event.screen_x, event.screen_y)
        self.release_mouse()

        if (
            not isinstance(widget, ContentTab)
            or not widget.id
            or widget not in self.query(ContentTab)
        ):
            return
        target_id = ContentTab.sans_prefix(widget.id)
        if not drag_id or target_id == drag_id:
            return

        before = (event.screen_x - region.x) < region.width / 2
        self.reorder_tab(drag_id, target_id, before=before)

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
