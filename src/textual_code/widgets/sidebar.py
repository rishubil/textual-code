from pathlib import Path

from rich.align import Align
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.widget import Widget
from textual.widgets import Static, TabbedContent, TabPane

from textual_code.widgets.explorer import Explorer
from textual_code.widgets.workspace_search import WorkspaceSearchPane

SIDEBAR_MIN_WIDTH = 5  # matches _parse_sidebar_resize's hardcoded minimum

# Responsive icon labels: (full_label, icon_only)
_TAB_LABELS = {
    "explorer_pane": ("📁 Explorer", "📁"),
    "search_pane": ("🔍 Search", "🔍"),
}
# 2-stage collapse: buttons lose text first (wider), then tabs (narrower)
_BTN_ICON_ONLY_THRESHOLD = 40
_TAB_ICON_ONLY_THRESHOLD = 15


class SidebarResizeHandle(Widget):
    """Drag handle docked at the right border of the Sidebar for resizing."""

    def __init__(self) -> None:
        super().__init__()
        self._dragging = False

    def render(self):
        return Align.center(Text("│", style="dim"), vertical="middle")

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self._dragging = True
        self.capture_mouse()
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._dragging:
            self.resize_sidebar_to(event.screen_x)

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._dragging:
            self._dragging = False
            self.release_mouse()

    def resize_sidebar_to(self, width: int) -> None:
        """Resize the Sidebar to the given width (clamped to min/max)."""
        max_width = self.app.size.width - 5
        clamped = max(SIDEBAR_MIN_WIDTH, min(max_width, width))
        self.app.query_one(Sidebar).styles.width = clamped


class Sidebar(Static):
    """
    Sidebar widget for the Textual Code application.
    """

    def __init__(
        self, workspace_path: Path, *args, show_hidden_files: bool = True, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.workspace_path = workspace_path
        self._show_hidden_files = show_hidden_files
        self._compact_tabs: bool | None = None
        self._compact_buttons: bool | None = None

    def compose(self) -> ComposeResult:
        yield SidebarResizeHandle()
        with TabbedContent():
            for pane_id, (full, _icon) in _TAB_LABELS.items():
                with TabPane(full, id=pane_id):
                    if pane_id == "explorer_pane":
                        yield Explorer(
                            workspace_path=self.workspace_path,
                            show_hidden_files=self._show_hidden_files,
                        )
                    else:
                        yield WorkspaceSearchPane(id="workspace_search")

    def on_resize(self, event: events.Resize) -> None:
        """Update tab and button labels based on sidebar width."""
        width = event.size.width
        compact_tabs = width < _TAB_ICON_ONLY_THRESHOLD
        compact_buttons = width < _BTN_ICON_ONLY_THRESHOLD
        if (
            compact_tabs == self._compact_tabs
            and compact_buttons == self._compact_buttons
        ):
            return
        self._compact_tabs = compact_tabs
        self._compact_buttons = compact_buttons
        try:
            tc = self.tabbed_content
            for pane_id, (full, icon) in _TAB_LABELS.items():
                tc.get_tab(pane_id).label = icon if compact_tabs else full
            self.workspace_search.update_button_labels(compact=compact_buttons)
        except (NoMatches, ValueError):
            pass  # widgets not yet mounted

    @property
    def tabbed_content(self) -> TabbedContent:
        return self.query_one(TabbedContent)

    @property
    def explorer_pane(self) -> TabPane:
        return self.query_one("#explorer_pane", TabPane)

    @property
    def explorer(self) -> Explorer:
        return self.query_one(Explorer)

    @property
    def search_pane(self) -> TabPane:
        return self.query_one("#search_pane", TabPane)

    @property
    def workspace_search(self) -> WorkspaceSearchPane:
        return self.query_one(WorkspaceSearchPane)
