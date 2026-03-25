from __future__ import annotations

import contextlib
import logging
import os
import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import pathspec
from rich.style import Style
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.await_complete import AwaitComplete
from textual.binding import Binding
from textual.message import Message
from textual.widgets import DirectoryTree, Static
from textual.widgets._directory_tree import DirEntry
from textual.worker import get_current_worker

if TYPE_CHECKING:
    from textual.widgets._tree import TreeNode


_NO_ITALIC = Style(italic=False)
_log = logging.getLogger(__name__)

# Git status constants — single source of truth for status strings.
GIT_STATUS_MODIFIED = "modified"
GIT_STATUS_UNTRACKED = "untracked"

# Priority values for git statuses (higher = takes precedence)
_GIT_STATUS_PRIORITY = {GIT_STATUS_UNTRACKED: 0, GIT_STATUS_MODIFIED: 1}


class GitStatusResult(NamedTuple):
    """Result from parsing git status output."""

    status_map: dict[Path, str]
    untracked_dirs: set[Path]
    # Pre-computed string prefixes for fast child-of-untracked checks.
    # Each entry ends with os.sep so "foo/" won't false-match "foobar/".
    untracked_dir_prefixes: tuple[str, ...]


def _parse_git_status_output(stdout: str, workspace: Path) -> GitStatusResult:
    """Parse ``git status --porcelain -z -unormal`` output.

    Returns a GitStatusResult with:
    - status_map: mapping of absolute paths to status strings
    - untracked_dirs: set of untracked directory paths (from -unormal)

    Parent directories are propagated up to the workspace root so that
    folders containing changed files inherit the highest-priority status.
    """
    status_map: dict[Path, str] = {}
    untracked_dirs: set[Path] = set()

    if not stdout:
        return GitStatusResult(status_map, untracked_dirs, ())

    entries = stdout.split("\0")
    i = 0
    while i < len(entries):
        entry = entries[i]
        if len(entry) < 4:
            i += 1
            continue

        xy = entry[:2]
        filepath_str = entry[3:]

        # Classify status
        status = GIT_STATUS_UNTRACKED if xy == "??" else GIT_STATUS_MODIFIED

        # Handle renames/copies: with -z, the next entry is the destination
        if xy[0] in ("R", "C"):
            i += 1
            if i < len(entries) and entries[i]:
                filepath_str = entries[i]

        # Detect untracked directories (-unormal shows them with trailing /)
        if status == GIT_STATUS_UNTRACKED and filepath_str.endswith("/"):
            dir_path = workspace / filepath_str.rstrip("/")
            untracked_dirs.add(dir_path)
            # Also add to status_map for the directory itself
            _set_status(status_map, dir_path, status, workspace)
            i += 1
            continue

        filepath = workspace / filepath_str
        _set_status(status_map, filepath, status, workspace)

        i += 1

    # Pre-compute string prefixes with trailing separator for fast child checks.
    prefixes = tuple(str(d) + os.sep for d in untracked_dirs)
    return GitStatusResult(status_map, untracked_dirs, prefixes)


def _set_status(
    status_map: dict[Path, str],
    filepath: Path,
    status: str,
    workspace: Path,
) -> None:
    """Set status for a path and propagate to parent directories."""
    priority = _GIT_STATUS_PRIORITY.get(status, 0)

    # Set file status (only upgrade, never downgrade)
    existing = status_map.get(filepath)
    if existing is None or _GIT_STATUS_PRIORITY.get(existing, 0) < priority:
        status_map[filepath] = status

    # Propagate to parent directories up to workspace root
    parent = filepath.parent
    while parent != workspace and parent.is_relative_to(workspace):
        existing_parent = status_map.get(parent)
        if (
            existing_parent is not None
            and _GIT_STATUS_PRIORITY.get(existing_parent, 0) >= priority
        ):
            break  # All ancestors already have equal or higher priority
        status_map[parent] = status
        parent = parent.parent


class FilteredDirectoryTree(DirectoryTree):
    """DirectoryTree subclass that can hide dotfiles and dim gitignored files."""

    class WorkspaceChanged(Message):
        """Posted when external workspace changes are detected by polling."""

    COMPONENT_CLASSES = DirectoryTree.COMPONENT_CLASSES | {
        "directory-tree--gitignored",
        "directory-tree--hidden",
        "directory-tree--git-modified",
        "directory-tree--git-untracked",
    }

    DEFAULT_CSS = """
    FilteredDirectoryTree {
        & > .directory-tree--gitignored,
        & > .directory-tree--hidden {
            text-style: dim;
        }
        & > .directory-tree--git-modified {
            color: $warning;
        }
        & > .directory-tree--git-untracked {
            color: $success;
        }
        &:ansi > .directory-tree--gitignored,
        &:ansi > .directory-tree--hidden {
            color: ansi_default;
            text-style: dim;
        }
        &:ansi > .directory-tree--git-modified {
            color: ansi_yellow;
        }
        &:ansi > .directory-tree--git-untracked {
            color: ansi_green;
        }
    }
    """

    def __init__(
        self,
        path: str | Path,
        *,
        show_hidden_files: bool = True,
        dim_gitignored: bool = True,
        dim_hidden_files: bool = False,
        show_git_status: bool = True,
        **kwargs,
    ):
        super().__init__(path, **kwargs)
        self.show_hidden_files = show_hidden_files
        self.dim_gitignored = dim_gitignored
        self.dim_hidden_files = dim_hidden_files
        self.show_git_status = show_git_status
        self._gitignore_specs: list[tuple[Path, pathspec.PathSpec]] | None = None
        self._gitignore_cache: dict[Path, bool] = {}
        self._git_result: GitStatusResult | None = None
        self._git_bin: str | None = shutil.which("git")
        # Workspace polling state for auto-refresh
        self._dir_mtimes: dict[Path, float | None] = {}
        self._git_ref_mtimes: tuple[float | None, float | None] = (
            None,
            None,
        )  # (index_mtime, head_mtime)
        self._ws_polling_paused: bool = False
        # Performance: scandir is_dir cache (populated by _load_directory_sync)
        self._is_dir_cache: dict[Path, bool] = {}
        # Performance: lazy gitignore loading (no workspace-wide traversal)
        self._gitignore_checked_dirs: set[Path] = set()
        # Performance: background git status loading flag
        self._bg_loading_started: bool = False

    def on_mount(self) -> None:
        self._bg_loading_started = True
        self._start_bg_loading()
        self.call_after_refresh(self._init_ws_polling)

    @work(thread=True, exclusive=True, group="bg_loading")
    def _start_bg_loading(self) -> None:
        """Load git status in a background thread.

        Git status is inherently workspace-wide and cannot be lazy-loaded
        per-directory, so it runs in a background worker to avoid blocking
        the first render.
        """
        _log.debug("starting background git status loading")
        git_result = self._load_git_status()
        worker = get_current_worker()
        if worker.is_cancelled:
            return
        self._git_result = git_result
        _log.debug("background git status loading completed")
        self.app.call_from_thread(self.refresh)

    def _init_ws_polling(self) -> None:
        """Initialize workspace polling snapshot and start timer."""
        self._dir_mtimes = self._collect_expanded_dir_mtimes()
        self._git_ref_mtimes = self._get_git_ref_mtimes()
        if not self.app.is_headless:
            self.set_interval(2.0, self._poll_workspace_change)

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        if self.show_hidden_files:
            return paths
        return [p for p in paths if not p.name.startswith(".")]

    # ── Gitignore support ────────────────────────────────────────────────

    def _load_gitignore_for_dir(self, dir_path: Path) -> None:
        """Load .gitignore from a specific directory if not already checked.

        Skips directories inside hidden paths (e.g. .git/, .venv/).
        Each directory is checked at most once per tree lifetime (or until
        reload clears _gitignore_checked_dirs).
        """
        if dir_path in self._gitignore_checked_dirs:
            return
        self._gitignore_checked_dirs.add(dir_path)

        # Skip hidden directories
        workspace = Path(self.path)
        try:
            rel = dir_path.relative_to(workspace)
        except ValueError:
            return
        if any(part.startswith(".") for part in rel.parts):
            return

        gitignore_path = dir_path / ".gitignore"
        try:
            content = gitignore_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            return
        try:
            spec = pathspec.PathSpec.from_lines("gitignore", content.splitlines())
            if self._gitignore_specs is None:
                self._gitignore_specs = []
            self._gitignore_specs.append((dir_path, spec))
        except Exception as e:
            _log.warning("Failed to parse %s: %s", gitignore_path, e)

    def _ensure_ancestor_gitignores(self, file_path: Path) -> None:
        """Ensure .gitignore files are loaded for all ancestor directories.

        Walks from the file's parent up to the workspace root, loading
        any .gitignore files found along the way.
        """
        workspace = Path(self.path)
        current = file_path.parent
        while current.is_relative_to(workspace):
            self._load_gitignore_for_dir(current)
            if current == workspace:
                break
            current = current.parent

    def _get_gitignore_specs(self) -> list[tuple[Path, pathspec.PathSpec]]:
        """Return current gitignore specs."""
        if self._gitignore_specs is None:
            self._gitignore_specs = []
        return self._gitignore_specs

    def _is_gitignored(self, file_path: Path, *, is_dir: bool | None = None) -> bool:
        """Check if a path is matched by any gitignore spec.

        Returns False when dim_gitignored is disabled or when the path
        is a dotfile (hidden files are exempt from dimming).
        Lazily loads .gitignore files for ancestor directories on first
        access. Iterates specs deepest-first so a subdirectory .gitignore
        can override a parent's patterns (matching real git behavior).

        Args:
            file_path: The path to check.
            is_dir: If provided, skip the stat call for is_dir detection.
                Callers with known directory status (e.g. render_label
                using node.allow_expand) should pass this to avoid
                unnecessary stat calls.
        """
        if not self.dim_gitignored:
            return False
        # Hidden files are exempt from dimming
        if file_path.name.startswith("."):
            return False
        # Check result cache
        if file_path in self._gitignore_cache:
            return self._gitignore_cache[file_path]
        # Lazily load ancestor gitignore files
        self._ensure_ancestor_gitignores(file_path)
        result = False
        if is_dir is None:
            is_dir = file_path.is_dir()
        # Iterate deepest-first so nested .gitignore overrides parent
        for gitignore_dir, spec in reversed(self._get_gitignore_specs()):
            if not file_path.is_relative_to(gitignore_dir):
                continue
            rel_to_dir = file_path.relative_to(gitignore_dir)
            # Append "/" for directories so patterns like "build/" match
            rel_str = str(rel_to_dir) + "/" if is_dir else str(rel_to_dir)
            if spec.match_file(rel_str):
                result = True
                break
        self._gitignore_cache[file_path] = result
        return result

    # ── Git status support ───────────────────────────────────────────────

    def _has_git_repo(self) -> bool:
        """Check if .git directory exists at workspace root."""
        return (Path(self.path) / ".git").is_dir()

    def _load_git_status(self) -> GitStatusResult:
        """Run git status and parse the output.

        Returns empty result when:
        - show_git_status is disabled
        - No .git directory at workspace root
        - git binary not found
        - git command fails or times out
        """
        empty = GitStatusResult({}, set(), ())
        if not self.show_git_status:
            return empty
        if self._git_bin is None:
            _log.debug("git status: git binary not found")
            return empty
        if not self._has_git_repo():
            _log.debug("git status: no .git directory at %s", self.path)
            return empty

        workspace = Path(self.path)
        try:
            result = subprocess.run(
                [self._git_bin, "status", "--porcelain", "-z", "-unormal"],
                capture_output=True,
                text=True,
                cwd=str(workspace),
                timeout=5,
            )
        except subprocess.TimeoutExpired:
            _log.warning("git status: timed out for %s", workspace)
            return empty
        except OSError as e:
            _log.debug("git status: OS error: %s", e)
            return empty

        if result.returncode != 0:
            _log.debug(
                "git status: non-zero exit %d for %s",
                result.returncode,
                workspace,
            )
            return empty

        return _parse_git_status_output(result.stdout, workspace)

    def _ensure_git_status_loaded(self) -> GitStatusResult:
        """Load git status cache if not already loaded.

        When background loading is active (mounted tree), returns empty
        result until the worker completes. For unmounted trees (unit tests),
        falls back to synchronous loading.
        """
        if self._git_result is None:
            if self._bg_loading_started:
                return GitStatusResult({}, set(), ())
            self._git_result = self._load_git_status()
        return self._git_result

    def _get_git_status(self, file_path: Path) -> str | None:
        """Return the git status for a path, or None if clean/unknown.

        Also checks if the path is inside an untracked directory
        (from -unormal output where entire directories are listed).
        """
        result = self._ensure_git_status_loaded()

        status = result.status_map.get(file_path)
        if status is not None:
            return status

        # Check if the file is inside an untracked directory using
        # pre-computed string prefixes (305x faster than is_relative_to).
        if result.untracked_dir_prefixes:
            path_str = str(file_path)
            for prefix in result.untracked_dir_prefixes:
                if path_str.startswith(prefix):
                    # Cache the result so subsequent renders get O(1) dict hit.
                    result.status_map[file_path] = GIT_STATUS_UNTRACKED
                    return GIT_STATUS_UNTRACKED

        return None

    def reload(self) -> AwaitComplete:
        """Reload the tree, invalidate caches, and re-snapshot for polling."""
        self._ws_polling_paused = True
        self._gitignore_specs = None
        self._gitignore_checked_dirs.clear()
        self._gitignore_cache.clear()
        self._git_result = None
        self._is_dir_cache.clear()
        parent_awaitable = super().reload()

        async def _reload_then_resume():
            try:
                await parent_awaitable
            finally:
                self._dir_mtimes = self._collect_expanded_dir_mtimes()
                self._git_ref_mtimes = self._get_git_ref_mtimes()
                self._ws_polling_paused = False
                if self._bg_loading_started:
                    self._start_bg_loading()

        return AwaitComplete(_reload_then_resume())

    # ── Workspace auto-refresh polling ──────────────────────────────────

    def _collect_expanded_dir_mtimes(self) -> dict[Path, float | None]:
        """Stat workspace root and all expanded directories in the tree."""
        result: dict[Path, float | None] = {}
        workspace = Path(self.path)
        try:
            result[workspace] = workspace.stat().st_mtime
        except OSError:
            result[workspace] = None

        def walk(node):
            for child in node.children:
                if (
                    child.data is not None
                    and child.is_expanded
                    and child.data.path.is_dir()
                ):
                    try:
                        result[child.data.path] = child.data.path.stat().st_mtime
                    except OSError:
                        result[child.data.path] = None
                    walk(child)

        walk(self.root)
        return result

    def _get_git_ref_mtimes(self) -> tuple[float | None, float | None]:
        """Stat .git/index and .git/HEAD for git change detection."""
        git_dir = Path(self.path) / ".git"
        if not git_dir.is_dir():
            return (None, None)
        index_mtime = None
        head_mtime = None
        with contextlib.suppress(OSError):
            index_mtime = (git_dir / "index").stat().st_mtime
        with contextlib.suppress(OSError):
            head_mtime = (git_dir / "HEAD").stat().st_mtime
        return (index_mtime, head_mtime)

    def _poll_workspace_change(self) -> None:
        """Check for workspace dir changes and git ref changes."""
        if self._ws_polling_paused:
            return

        new_dir_mtimes = self._collect_expanded_dir_mtimes()
        dir_changed = new_dir_mtimes != self._dir_mtimes

        new_git_mtimes = self._get_git_ref_mtimes()
        git_changed = new_git_mtimes != self._git_ref_mtimes

        if dir_changed:
            _log.debug("workspace dir change detected, reloading explorer")
            self._git_ref_mtimes = new_git_mtimes
            self.reload()
            self.post_message(self.WorkspaceChanged())
        elif git_changed:
            _log.debug("git ref change detected, refreshing explorer labels")
            self._git_ref_mtimes = new_git_mtimes
            self._git_result = None
            self.refresh()
            if self._bg_loading_started:
                self._start_bg_loading()

    def render_label(self, node: TreeNode, base_style: Style, style: Style) -> Text:
        """Override to strip italic and apply gitignored/hidden/git-status styles.

        The base DirectoryTree.render_label applies italic to file extensions
        via highlight_regex(r\"\\..+$\") with the directory-tree--extension
        component class.  This override strips italic unconditionally so no
        filename or directory name is rendered in italic.

        Gitignored files are dimmed using the same component-class mechanism
        as hidden files for consistent appearance across terminal modes.
        Git-modified files are colored with $warning, untracked with $success.
        """
        text = super().render_label(node, base_style, style)
        if node.data is not None:
            is_dotfile = node.data.path.name.startswith(".")
            # Strip italic from ALL nodes — the base class extension regex
            # r"\..+$" applies unwanted italic to any name containing a dot.
            text.stylize(_NO_ITALIC)
            # Apply gitignored dim via component class for consistency with
            # the hidden-file styling (both use CSS text-style: dim).
            if not is_dotfile and self._is_gitignored(
                node.data.path, is_dir=node.allow_expand
            ):
                text.stylize_before(
                    self.get_component_rich_style(
                        "directory-tree--gitignored", partial=True
                    )
                )
            # Dim hidden files (dotfiles/dotfolders) when enabled.
            # Uses a separate component class so it doesn't conflict with
            # gitignored dimming.
            if is_dotfile and self.dim_hidden_files:
                text.stylize_before(
                    self.get_component_rich_style(
                        "directory-tree--hidden", partial=True
                    )
                )
            # Apply git status color highlighting.
            git_status = self._get_git_status(node.data.path)
            if git_status == GIT_STATUS_MODIFIED:
                text.stylize_before(
                    self.get_component_rich_style(
                        "directory-tree--git-modified", partial=True
                    )
                )
            elif git_status == GIT_STATUS_UNTRACKED:
                text.stylize_before(
                    self.get_component_rich_style(
                        "directory-tree--git-untracked", partial=True
                    )
                )
        return text

    # ── os.scandir directory loading optimization ────────────────────────

    def _load_directory_sync(self, path: Path) -> list[Path]:
        """Load directory contents using os.scandir and populate _is_dir_cache.

        Uses os.scandir instead of path.iterdir so that is_dir info comes
        from the directory entry itself (no extra stat calls on Linux/macOS).

        Args:
            path: The directory to scan. Will be resolved to an absolute path.

        Returns:
            Sorted list of filtered paths (directories first, then by name).
        """
        path = path.resolve()
        entries: list[Path] = []
        try:
            with os.scandir(path) as it:
                for entry in it:
                    entry_path = Path(entry.path)
                    try:
                        is_dir = entry.is_dir(follow_symlinks=True)
                    except OSError:
                        is_dir = False
                    self._is_dir_cache[entry_path] = is_dir
                    entries.append(entry_path)
        except OSError:
            pass
        filtered = list(self.filter_paths(entries))
        filtered.sort(
            key=lambda p: (not self._is_dir_cache.get(p, False), p.name.lower())
        )
        return filtered

    @work(thread=True, exit_on_error=False)
    def _load_directory(self, node: TreeNode[DirEntry]) -> list[Path]:
        """Load directory contents using os.scandir (no redundant stat calls).

        Overrides the base DirectoryTree._load_directory to eliminate
        duplicate stat calls per entry.
        """
        assert node.data is not None
        return self._load_directory_sync(node.data.path.expanduser())

    def _populate_node(self, node: TreeNode[DirEntry], content: Iterable[Path]) -> None:
        """Populate tree node using cached is_dir results.

        Overrides the base DirectoryTree._populate_node to read from
        _is_dir_cache (populated by _load_directory_sync) instead of
        calling _safe_is_dir which would make another stat call per entry.
        """
        node.remove_children()
        for path in content:
            is_dir = self._is_dir_cache.pop(path, None)
            if is_dir is None:
                is_dir = self._safe_is_dir(path)
            node.add(
                path.name,
                data=DirEntry(path),
                allow_expand=is_dir,
            )
        node.expand()


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

    def __init__(
        self,
        workspace_path: Path,
        *args,
        show_hidden_files: bool = True,
        dim_gitignored: bool = True,
        dim_hidden_files: bool = False,
        show_git_status: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        # the path to open in the explorer
        self.workspace_path = workspace_path
        self._show_hidden_files = show_hidden_files
        self._dim_gitignored = dim_gitignored
        self._dim_hidden_files = dim_hidden_files
        self._show_git_status = show_git_status
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
                assert child.data is not None
                self.log.debug("select_file: expanding %s", child.data.path)
                child.expand()
                self.call_after_refresh(self._retry_pending)
                return
            current = child
        # All folders expanded but file not yet visible (still loading)
        self.call_after_refresh(self._retry_pending)

    def compose(self) -> ComposeResult:
        directory_tree = FilteredDirectoryTree(
            self.workspace_path,
            show_hidden_files=self._show_hidden_files,
            dim_gitignored=self._dim_gitignored,
            dim_hidden_files=self._dim_hidden_files,
            show_git_status=self._show_git_status,
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
        await self.app.action_create_file_with_command_palette(
            initial_path=self._get_selected_dir_relative()
        )

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
        await self.app.action_create_directory_with_command_palette(
            initial_path=self._get_selected_dir_relative()
        )

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
