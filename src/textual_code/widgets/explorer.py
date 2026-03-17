from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import DirectoryTree, Static


class FilteredDirectoryTree(DirectoryTree):
    """DirectoryTree subclass that can hide dotfiles."""

    def __init__(self, path: str | Path, *, show_hidden_files: bool = True, **kwargs):
        super().__init__(path, **kwargs)
        self.show_hidden_files = show_hidden_files

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        if self.show_hidden_files:
            return paths
        return [p for p in paths if not p.name.startswith(".")]


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

    _MAX_SELECT_RETRIES = 10

    def __init__(
        self, workspace_path: Path, *args, show_hidden_files: bool = True, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)

        # the path to open in the explorer
        self.workspace_path = workspace_path
        self._show_hidden_files = show_hidden_files
        self._pending_path: Path | None = None
        self._pending_retries: int = 0

    def on_mount(self) -> None:
        if self._pending_path is not None:
            self.call_after_refresh(self._retry_pending)

    def _retry_pending(self) -> None:
        if self._pending_path is None:
            return
        self._pending_retries -= 1
        if self._pending_retries <= 0:
            self.log.warning(
                "select_file: gave up after %s retries for %s",
                self._MAX_SELECT_RETRIES,
                self._pending_path,
            )
            self._pending_path = None
            return
        pending = self._pending_path
        self._pending_path = None
        self.log.debug("select_file: retrying for %s", pending)
        self.select_file(pending)

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

        def is_visible(node) -> bool:
            """Return True if every ancestor up to root is expanded."""
            current = node.parent
            while current is not None:
                if not current.is_expanded:
                    return False
                current = current.parent
            return True

        root = self.directory_tree.root
        node = find_node(root)
        if node is not None and is_visible(node):
            self.directory_tree.move_cursor(node)
            self._pending_path = None
            return

        # File not found in loaded nodes, or is inside a collapsed folder.
        # Reset retry counter only when starting a fresh (non-retry) attempt.
        self._pending_path = path
        if self._pending_retries == 0:
            self._pending_retries = self._MAX_SELECT_RETRIES

        # Walk path components and expand the first collapsed directory, then retry.
        parts = path.relative_to(self.workspace_path).parts
        current = root
        for part in parts[:-1]:  # directory components only (exclude filename)
            child = next(
                (
                    c
                    for c in current.children
                    if c.data is not None and c.data.path.name == part
                ),
                None,
            )
            if child is None:
                # Directory not in tree yet — retry after loading
                self.call_after_refresh(self._retry_pending)
                return
            if not child.is_expanded:
                self.log.debug("select_file: expanding %s", child.data.path)
                child.expand()
                self.call_after_refresh(self._retry_pending)
                return
            current = child
        # All folders expanded but file not yet visible (still loading)
        self.call_after_refresh(self._retry_pending)

    def compose(self) -> ComposeResult:
        directory_tree = FilteredDirectoryTree(
            self.workspace_path, show_hidden_files=self._show_hidden_files
        )
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
    def directory_tree(self) -> FilteredDirectoryTree:
        return self.query_one(FilteredDirectoryTree)
