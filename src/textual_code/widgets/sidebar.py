from pathlib import Path

from textual.app import ComposeResult
from textual.widgets import Static, TabbedContent, TabPane

from textual_code.widgets.explorer import Explorer


class Sidebar(Static):
    def __init__(self, workspace_path: Path, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.workspace_path = workspace_path

    def compose(self) -> ComposeResult:
        with TabbedContent(), TabPane("Explorer", id="explorer_pane"):
            yield Explorer(workspace_path=self.workspace_path)

    @property
    def tabbed_content(self) -> TabbedContent:
        return self.query_one(TabbedContent)

    @property
    def explorer_pane(self) -> TabPane:
        return self.query_one("#explorer_pane", TabPane)

    @property
    def explorer(self) -> Explorer:
        return self.query_one(Explorer)
