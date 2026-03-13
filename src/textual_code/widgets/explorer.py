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
        Binding("delete", "delete_node", "Delete"),
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

    @dataclass
    class FileDeleteRequested(Message):
        """
        Message to request deleting a file or directory.
        """

        explorer: "Explorer"

        # the path to the file or directory to delete.
        path: Path

        @property
        def control(self) -> "Explorer":
            return self.explorer

    def __init__(self, workspace_path: Path, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # the path to open in the explorer
        self.workspace_path = workspace_path
        self._pending_path: Path | None = None

    def on_mount(self) -> None:
        if self._pending_path is not None:
            pending = self._pending_path
            self._pending_path = None
            self.call_after_refresh(self.select_file, pending)

    def select_file(self, path: Path) -> None:
        """Move the explorer cursor to path if it is loaded and within workspace."""
        try:
            path.relative_to(self.workspace_path)
        except ValueError:
            return  # outside workspace

        def find_node(node):
            if node.data is not None and node.data.path == path:
                return node
            for child in node.children:
                result = find_node(child)
                if result is not None:
                    return result
            return None

        root = self.directory_tree.root
        node = find_node(root)
        if node is not None:
            self.directory_tree.move_cursor(node)
        else:
            self._pending_path = path

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

    def action_delete_node(self) -> None:
        """
        Delete the currently focused file or directory.
        """
        node = self.directory_tree.cursor_node
        if node is None or node.data is None:
            return
        self.post_message(self.FileDeleteRequested(explorer=self, path=node.data.path))

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
