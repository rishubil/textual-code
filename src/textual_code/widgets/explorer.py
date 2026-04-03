from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import DirectoryTree, Static

from textual_code.widgets.filtered_tree import (
    GIT_STATUS_MODIFIED as GIT_STATUS_MODIFIED,
)
from textual_code.widgets.filtered_tree import (
    GIT_STATUS_UNTRACKED as GIT_STATUS_UNTRACKED,
)

# Re-export for backward compatibility — test files and other modules
# import these symbols from textual_code.widgets.explorer.
from textual_code.widgets.filtered_tree import (
    FilteredDirectoryTree as FilteredDirectoryTree,
)
from textual_code.widgets.filtered_tree import (
    GitStatusResult as GitStatusResult,
)
from textual_code.widgets.filtered_tree import (
    _parse_git_status_output as _parse_git_status_output,
)


class Explorer(Static):
    """
    A widget for exploring the file system.
    """

    BINDINGS = [
        Binding("ctrl+n", "create_file", "New File"),
        Binding("ctrl+d", "create_directory", "New Folder"),
        Binding("delete", "delete_node", "Delete"),
        Binding("f2", "rename_node", "Rename"),
        Binding("ctrl+c", "copy_node", "Copy", show=False),
        Binding("ctrl+x", "cut_node", "Cut", show=False),
        Binding("ctrl+v", "paste_node", "Paste", show=False),
    ]

    @dataclass
    class FileOpenRequested(Message):
        """
        Message to request opening a file.
        """

        explorer: Explorer

        # the path to the file to open.
        path: Path

        @property
        def control(self) -> Explorer:
            return self.explorer

    @dataclass
    class FileDeleteRequested(Message):
        """
        Message to request deleting a file or directory.
        """

        explorer: Explorer

        # the path to the file or directory to delete.
        path: Path

        @property
        def control(self) -> Explorer:
            return self.explorer

    @dataclass
    class FileRenameRequested(Message):
        """
        Message to request renaming a file or directory.
        """

        explorer: Explorer

        # the path to the file or directory to rename.
        path: Path

        @property
        def control(self) -> Explorer:
            return self.explorer

    @dataclass
    class FileMoveRequested(Message):
        """
        Message to request moving a file or directory.
        """

        explorer: Explorer

        # the path to the file or directory to move.
        path: Path

        @property
        def control(self) -> Explorer:
            return self.explorer

    @dataclass
    class FileCopyRequested(Message):
        """Message to request copying a file or directory to clipboard."""

        explorer: Explorer

        # the path to the file or directory to copy.
        path: Path

        @property
        def control(self) -> Explorer:
            return self.explorer

    @dataclass
    class FileCutRequested(Message):
        """Message to request cutting a file or directory to clipboard."""

        explorer: Explorer

        # the path to the file or directory to cut.
        path: Path

        @property
        def control(self) -> Explorer:
            return self.explorer

    @dataclass
    class FilePasteRequested(Message):
        """Message to request pasting from the file clipboard."""

        explorer: Explorer

        # the target directory to paste into.
        target_dir: Path

        @property
        def control(self) -> Explorer:
            return self.explorer

    _MAX_SELECT_RETRIES = 10
    _SELECT_RETRY_DELAY = 0.05

    def __init__(
        self,
        workspace_path: Path,
        *args,
        show_hidden_files: bool = True,
        dim_gitignored: bool = True,
        dim_hidden_files: bool = False,
        show_git_status: bool = True,
        compact_folders: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        # the path to open in the explorer
        self.workspace_path = workspace_path
        self._show_hidden_files = show_hidden_files
        self._dim_gitignored = dim_gitignored
        self._dim_hidden_files = dim_hidden_files
        self._show_git_status = show_git_status
        self._compact_folders = compact_folders
        self._pending_path: Path | None = None
        self._pending_retries: int = 0
        self._pending_depth: int = -1

    def on_mount(self) -> None:
        if self._pending_path is not None:
            self.set_timer(self._SELECT_RETRY_DELAY, self._retry_pending)

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
            self._pending_depth = -1
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
            self._pending_depth = -1
            return

        # File not found in loaded nodes, or is inside a collapsed folder.
        # Reset depth tracker when switching to a different target path, so
        # that a shallower new path doesn't inherit stale depth from the old.
        if self._pending_path != path:
            self._pending_depth = -1
        self._pending_path = path
        if self._pending_retries == 0:
            self._pending_retries = self._MAX_SELECT_RETRIES

        # Walk tree using is_relative_to matching — handles compact folder nodes
        # where intermediate directories don't have individual tree nodes.
        max_depth = len(path.relative_to(self.workspace_path).parts)
        depth_reached = 0
        current = root
        for _ in range(max_depth):
            # Find a directory child that contains the target path
            dir_child = next(
                (
                    c
                    for c in current.children
                    if c.data is not None
                    and c.allow_expand
                    and path.is_relative_to(c.data.path)
                ),
                None,
            )
            if dir_child is None:
                # Directory not in tree yet — retry after loading
                break
            if not dir_child.is_expanded:
                assert dir_child.data is not None
                self.log.debug("select_file: expanding %s", dir_child.data.path)
                dir_child.expand()
                depth_reached += 1
                break
            current = dir_child
            depth_reached += 1
            # Check if the file node is now a direct child
            file_match = next(
                (
                    c
                    for c in current.children
                    if c.data is not None and c.data.path == path
                ),
                None,
            )
            if file_match is not None:
                # File node exists but find_node didn't reach it — still loading
                break

        # Reset retry counter when deeper progress is made in the tree walk.
        # This makes the mechanism depth-independent: each new level of
        # expansion grants a fresh set of retries for async loading to finish.
        if depth_reached > self._pending_depth:
            self._pending_depth = depth_reached
            self._pending_retries = self._MAX_SELECT_RETRIES

        # Use set_timer instead of call_after_refresh to give async directory
        # loading (NodeExpanded handler → _add_to_load_queue → _loader) enough
        # time to complete between retries.
        self.set_timer(self._SELECT_RETRY_DELAY, self._retry_pending)

    def compose(self) -> ComposeResult:
        directory_tree = FilteredDirectoryTree(
            self.workspace_path,
            show_hidden_files=self._show_hidden_files,
            dim_gitignored=self._dim_gitignored,
            dim_hidden_files=self._dim_hidden_files,
            show_git_status=self._show_git_status,
            compact_folders=self._compact_folders,
        )
        directory_tree.show_root = False  # don't show the root directory
        yield directory_tree

    def _get_selected_dir(self) -> Path:
        """Return the absolute directory path of the selected node.

        If a file is selected, returns its parent directory.
        Falls back to the workspace root when nothing is selected.
        """
        node = self.directory_tree.cursor_node
        if node is None or node.data is None:
            return self.workspace_path
        path = node.data.path
        if not node.allow_expand:  # it's a file
            path = path.parent
        return path

    def _get_selected_dir_relative(self) -> str:
        """Return relative path of the selected directory (trailing '/')."""
        path = self._get_selected_dir()
        if path == self.workspace_path:
            return ""
        try:
            return str(path.relative_to(self.workspace_path)) + "/"
        except ValueError:
            return ""

    async def action_create_file(self) -> None:
        """
        Create a new file at a path.
        """
        from textual_code.app import TextualCode

        assert isinstance(self.app, TextualCode)
        await self.app.action_new_file(initial_path=self._get_selected_dir_relative())

    def action_delete_node(self) -> None:
        """
        Delete the currently focused file or directory.
        """
        node = self.directory_tree.cursor_node
        if node is None or node.data is None:
            return
        self.post_message(self.FileDeleteRequested(explorer=self, path=node.data.path))

    def action_rename_node(self) -> None:
        """
        Rename the currently focused file or directory.
        """
        node = self.directory_tree.cursor_node
        if node is None or node.data is None:
            return
        self.post_message(self.FileRenameRequested(explorer=self, path=node.data.path))

    def action_move_node(self) -> None:
        """
        Move the currently focused file or directory.
        """
        node = self.directory_tree.cursor_node
        if node is None or node.data is None:
            return
        self.post_message(self.FileMoveRequested(explorer=self, path=node.data.path))

    def action_copy_node(self) -> None:
        """Copy the currently focused file or directory to clipboard."""
        node = self.directory_tree.cursor_node
        if node is None or node.data is None:
            return
        self.post_message(self.FileCopyRequested(explorer=self, path=node.data.path))

    def action_cut_node(self) -> None:
        """Cut the currently focused file or directory to clipboard."""
        node = self.directory_tree.cursor_node
        if node is None or node.data is None:
            return
        self.post_message(self.FileCutRequested(explorer=self, path=node.data.path))

    def action_paste_node(self) -> None:
        """Paste from clipboard into the currently focused directory."""
        target = self._get_selected_dir()
        self.post_message(self.FilePasteRequested(explorer=self, target_dir=target))

    async def action_create_directory(self) -> None:
        """
        Create a new directory at a path.
        """
        from textual_code.app import TextualCode

        assert isinstance(self.app, TextualCode)
        await self.app.action_new_folder(initial_path=self._get_selected_dir_relative())

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
