from pathlib import Path

from rich.align import Align
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static, TabbedContent, TabPane

from textual_code.widgets.explorer import Explorer
from textual_code.widgets.workspace_search import WorkspaceSearchPane

SIDEBAR_MIN_WIDTH = 5  # matches _parse_sidebar_resize's hardcoded minimum


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

    def __init__(self, workspace_path: Path, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # the path to open in the explorer
        self.workspace_path = workspace_path

    def compose(self) -> ComposeResult:
        yield SidebarResizeHandle()
        with TabbedContent():
            with TabPane("Explorer", id="explorer_pane"):
                yield Explorer(workspace_path=self.workspace_path)
            with TabPane("Search", id="search_pane"):
                yield WorkspaceSearchPane(id="workspace_search")

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
