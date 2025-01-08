from dataclasses import dataclass
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import DirectoryTree, Static


class Explorer(Static):
    @dataclass
    class FileOpenRequested(Message):
        explorer: "Explorer"
        path: Path

        @property
        def control(self) -> "Explorer":
            return self.explorer

    def __init__(self, workspace_path: Path, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.workspace_path = workspace_path

    def compose(self) -> ComposeResult:
        directory_tree = DirectoryTree(self.workspace_path)
        directory_tree.show_root = False
        yield directory_tree

    @on(DirectoryTree.FileSelected)
    def file_selected(self, event: DirectoryTree.FileSelected):
        event.stop()
        self.post_message(
            self.FileOpenRequested(
                explorer=self,
                path=event.path.resolve(),
            )
        )

    @property
    def directory_tree(self) -> DirectoryTree:
        return self.query_one(DirectoryTree)
