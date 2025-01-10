from dataclasses import dataclass
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import DirectoryTree, Static


class Explorer(Static):
    """
    A widget for exploring the file system.
    """

    BINDINGS = [
        Binding("ctrl+n", "create_file", "Create file"),
        Binding("ctrl+d", "create_directory", "Create directory"),
    ]

    @dataclass
    class FileOpenRequested(Message):
        """
        Message to request opening a file.
        """

        explorer: "Explorer"

        # the path to the file to open.
        path: Path

        @property
        def control(self) -> "Explorer":
            return self.explorer

    def __init__(self, workspace_path: Path, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # the path to open in the explorer
        self.workspace_path = workspace_path

    def compose(self) -> ComposeResult:
        directory_tree = DirectoryTree(self.workspace_path)
        directory_tree.show_root = False  # don't show the root directory
        yield directory_tree

    def action_create_file(self) -> None:
        """
        Create a new file at a path.
        """
        from textual_code.app import TextualCode

        assert isinstance(self.app, TextualCode)
        self.app.action_create_file_with_command_palette()

    def action_create_directory(self) -> None:
        """
        Create a new directory at a path.
        """
        from textual_code.app import TextualCode

        assert isinstance(self.app, TextualCode)
        self.app.action_create_directory_with_command_palette()

    @on(DirectoryTree.FileSelected)
    def on_file_selected(self, event: DirectoryTree.FileSelected):
        event.stop()

        # request to open the selected file
        self.post_message(
            self.FileOpenRequested(
                explorer=self,
                path=event.path.resolve(),
            )
        )

    @property
    def directory_tree(self) -> DirectoryTree:
        return self.query_one(DirectoryTree)
