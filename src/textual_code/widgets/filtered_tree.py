"""FilteredDirectoryTree with gitignore support and git status display."""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import pathspec
from rich.style import Style
from rich.text import Text
from textual import work
from textual.await_complete import AwaitComplete
from textual.message import Message
from textual.widgets import DirectoryTree
from textual.widgets._directory_tree import DirEntry
from textual.worker import get_current_worker

from textual_code.cancellable_worker import run_cancellable

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


def scan_directory_sync(
    path: Path, show_hidden_files: bool
) -> tuple[list[Path], dict[Path, bool]]:
    """Scan a directory with os.scandir and return sorted paths + is_dir cache.

    Module-level function so it can be pickled by :func:`run_cancellable`.

    Args:
        path: The directory to scan. Will be resolved to an absolute path.
        show_hidden_files: If False, entries starting with '.' are excluded.

    Returns:
        A tuple of (sorted_paths, is_dir_cache).
    """
    path = path.resolve()
    entries: list[Path] = []
    is_dir_cache: dict[Path, bool] = {}
    try:
        with os.scandir(path) as it:
            for entry in it:
                entry_path = Path(entry.path)
                try:
                    is_dir = entry.is_dir(follow_symlinks=True)
                except OSError:
                    is_dir = False
                is_dir_cache[entry_path] = is_dir
                entries.append(entry_path)
    except OSError:
        pass
    if not show_hidden_files:
        entries = [p for p in entries if not p.name.startswith(".")]
    entries.sort(key=lambda p: (not is_dir_cache.get(p, False), p.name.lower()))
    return entries, is_dir_cache


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
            color: $text-warning;
        }
        & > .directory-tree--git-untracked {
            color: $text-success;
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
        compact_folders: bool = True,
        **kwargs,
    ):
        super().__init__(path, **kwargs)
        self.show_hidden_files = show_hidden_files
        self.dim_gitignored = dim_gitignored
        self.dim_hidden_files = dim_hidden_files
        self.show_git_status = show_git_status
        self.compact_folders = compact_folders
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
            _log.debug("bg_loading worker cancelled, skipping callback")
            return
        self._git_result = git_result
        _log.debug("background git status loading completed")
        try:
            self.app.call_from_thread(self.refresh)
        except RuntimeError as exc:
            if "loop" not in str(exc).lower() and "closed" not in str(exc).lower():
                raise
            _log.debug("call_from_thread suppressed (app exiting): %s", exc)

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
                encoding="utf-8",
                errors="replace",
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
        if not self.show_git_status:
            return None
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
        # Keep stale git data visible during the tree rebuild only when the
        # background worker is active (mounted tree) — it will atomically replace
        # _git_result once the fresh status is ready, avoiding a blank flash.
        # For unmounted trees (_bg_loading_started is False) clear immediately so
        # the next _ensure_git_status_loaded() call triggers a synchronous reload.
        if not self._bg_loading_started:
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
            _log.debug(
                "git ref change detected, scheduling background git status reload"
            )
            self._git_ref_mtimes = new_git_mtimes
            # Do NOT clear _git_result here — keep stale data visible until the
            # background worker atomically replaces it (VS Code pattern: old
            # decorations stay until new data arrives, avoiding a blank flash).
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
        Git-modified files are colored with $text-warning, untracked with $text-success.
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

        Delegates to :func:`scan_directory_sync` (module-level, picklable).

        Args:
            path: The directory to scan. Will be resolved to an absolute path.

        Returns:
            Sorted list of filtered paths (directories first, then by name).
        """
        paths, cache = scan_directory_sync(path, self.show_hidden_files)
        self._is_dir_cache.update(cache)
        return paths

    @work(exit_on_error=False)
    async def _load_directory(self, node: TreeNode[DirEntry]) -> list[Path]:
        """Load directory contents in a subprocess via :func:`run_cancellable`.

        Overrides the base DirectoryTree._load_directory to eliminate
        duplicate stat calls per entry and enable true cancellation.
        """
        assert node.data is not None
        paths, cache = await run_cancellable(
            scan_directory_sync,
            node.data.path.expanduser(),
            self.show_hidden_files,
        )
        self._is_dir_cache.update(cache)
        return paths

    def _resolve_compact_chain(self, path: Path) -> tuple[str, Path]:
        """Walk a single-child directory chain and return joined label + deepest path.

        Starting from *path*, repeatedly loads subdirectory contents.  If a
        directory has exactly one visible child that is also a directory, the
        chain continues.  Otherwise the chain ends.

        Returns:
            A tuple of (joined_label, deepest_directory_path).
        """
        segments = [path.name]
        current = path
        seen: set[Path] = set()
        while True:
            children = self._load_directory_sync(current)
            if len(children) != 1:
                break
            child = children[0]
            is_dir = self._is_dir_cache.get(child, self._safe_is_dir(child))
            if not is_dir:
                break
            # Guard against symlink cycles
            resolved = child.resolve()
            if resolved in seen:
                break
            seen.add(resolved)
            segments.append(child.name)
            current = child
        if len(segments) > 1:
            _log.debug("compact chain: %s → %s", path.name, "/".join(segments))
        return "/".join(segments), current

    def _populate_node(self, node: TreeNode[DirEntry], content: Iterable[Path]) -> None:
        """Populate tree node using cached is_dir results.

        Overrides the base DirectoryTree._populate_node to read from
        _is_dir_cache (populated by _load_directory_sync) instead of
        calling _safe_is_dir which would make another stat call per entry.

        When compact_folders is enabled, single-child directory chains are
        merged into a single node with a joined label (e.g. "src/main/java").
        """
        node.remove_children()
        for path in content:
            is_dir = self._is_dir_cache.pop(path, None)
            if is_dir is None:
                is_dir = self._safe_is_dir(path)
            if is_dir and self.compact_folders:
                label, deepest = self._resolve_compact_chain(path)
                node.add(
                    label,
                    data=DirEntry(deepest),
                    allow_expand=True,
                )
            else:
                node.add(
                    path.name,
                    data=DirEntry(path),
                    allow_expand=is_dir,
                )
        node.expand()
