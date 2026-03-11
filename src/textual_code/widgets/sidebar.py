from pathlib import Path

from textual.app import ComposeResult
from textual.widgets import Static, TabbedContent, TabPane

from textual_code.widgets.explorer import Explorer
from textual_code.widgets.workspace_search import WorkspaceSearchPane


class Sidebar(Static):
    """
    Sidebar widget for the Textual Code application.
    """

    def __init__(self, workspace_path: Path, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # the path to open in the explorer
        self.workspace_path = workspace_path

    def compose(self) -> ComposeResult:
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
