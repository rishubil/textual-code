import asyncio
import heapq
import logging
import os
from collections.abc import Callable, Generator
from functools import partial
from pathlib import Path
from typing import Any

from textual.command import DiscoveryHit, Hit, Hits, Provider

logger = logging.getLogger(__name__)

_MAX_SEARCH_HITS = 20
"""Maximum number of hits returned by a single command provider search."""


def _safe_rglob(path: Path, pattern: str) -> Generator[Path, None, None]:
    """Yield entries from path.rglob(), skipping OSError."""
    try:
        yield from path.rglob(pattern)
    except OSError:
        logger.debug("OSError during rglob of %s, skipping remaining entries", path)


def _prune_dirs(dirnames: list[str], show_hidden_files: bool) -> None:
    """Remove directories from *dirnames* in-place to prevent os.walk descent."""
    if show_hidden_files:
        dirnames[:] = [d for d in dirnames if d != ".git"]
    else:
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]


def _read_workspace_files(
    workspace_path: Path, *, show_hidden_files: bool = True
) -> list[Path]:
    """Return relative paths for files under workspace_path.

    When *show_hidden_files* is True (default) dot-prefixed entries are
    included but ``.git`` subtrees are always excluded.  When False every
    dot-prefixed path component causes the entry to be skipped.

    Uses ``os.walk`` with in-place directory pruning so that excluded
    subtrees (e.g. ``.git``, ``.venv`` when hidden) are never traversed.
    """
    result: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(
        workspace_path, onerror=lambda e: logger.debug("os.walk error: %s", e)
    ):
        _prune_dirs(dirnames, show_hidden_files)
        dir_path = Path(dirpath)
        for fname in filenames:
            if fname == ".git":
                continue
            if not show_hidden_files and fname.startswith("."):
                continue
            try:
                result.append((dir_path / fname).relative_to(workspace_path))
            except OSError:
                logger.debug("OSError accessing %s/%s, skipping", dirpath, fname)
    result.sort()
    return result


def create_open_file_command_provider(
    workspace_path: Path, post_message_callback: Callable[[Path], Any]
) -> type[Provider]:
    class OpenFileCommandProvider(Provider):
        """A command provider to open a file in the viewer."""

        async def startup(self) -> None:
            worker = self.app.run_worker(
                partial(_read_workspace_files, workspace_path), thread=True
            )
            self.file_paths = await worker.wait()

        async def search(self, query: str) -> Hits:
            matcher = self.matcher(query)
            file_paths = self.file_paths

            def _match() -> list[tuple[float, str]]:
                results: list[tuple[float, str]] = []
                for path in file_paths:
                    command = str(path)
                    score = matcher.match(command)
                    if score > 0:
                        results.append((score, command))
                return heapq.nlargest(_MAX_SEARCH_HITS, results)

            top = await asyncio.to_thread(_match)
            for score, command in top:
                yield Hit(
                    score,
                    matcher.highlight(command),
                    partial(
                        post_message_callback,
                        workspace_path / command,
                    ),
                    help="Open this file in the viewer",
                )

    return OpenFileCommandProvider


def _read_workspace_paths(
    workspace_path: Path, *, show_hidden_files: bool = True
) -> list[Path]:
    """Return all files and directories under workspace_path.

    When *show_hidden_files* is True (default) dot-prefixed entries are
    included but ``.git`` subtrees are always excluded.  When False every
    dot-prefixed path component causes the entry to be skipped.

    Uses ``os.walk`` with in-place directory pruning so that excluded
    subtrees are never traversed.
    """
    result: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(
        workspace_path, onerror=lambda e: logger.debug("os.walk error: %s", e)
    ):
        _prune_dirs(dirnames, show_hidden_files)
        dir_path = Path(dirpath)
        for dname in dirnames:
            result.append(dir_path / dname)
        for fname in filenames:
            if fname == ".git":
                continue
            if not show_hidden_files and fname.startswith("."):
                continue
            result.append(dir_path / fname)
    result.sort()
    return result


def _create_path_action_command_provider(
    workspace_path: Path,
    post_message_callback: Callable[[Path], Any],
    action_verb: str,
) -> type[Provider]:
    """Create a command provider that lists workspace paths for an action."""
    passed_workspace_path = workspace_path
    passed_post_message_callback = post_message_callback
    passed_action_verb = action_verb

    class PathActionCommandProvider(Provider):
        async def startup(self) -> None:
            worker = self.app.run_worker(
                partial(_read_workspace_paths, passed_workspace_path), thread=True
            )
            self.paths = await worker.wait()

        async def search(self, query: str) -> Hits:
            matcher = self.matcher(query)
            paths = self.paths

            def _match() -> list[tuple[float, str, Path, bool]]:
                results: list[tuple[float, str, Path, bool]] = []
                for path in paths:
                    relative = path.relative_to(passed_workspace_path)
                    command = str(relative)
                    score = matcher.match(command)
                    if score > 0:
                        results.append((score, command, path, path.is_dir()))
                return heapq.nlargest(_MAX_SEARCH_HITS, results)

            top = await asyncio.to_thread(_match)
            for score, command, path, is_dir in top:
                kind = "directory" if is_dir else "file"
                yield Hit(
                    score,
                    matcher.highlight(command),
                    partial(passed_post_message_callback, path),
                    help=f"{passed_action_verb} {kind}",
                )

    return PathActionCommandProvider


def create_delete_path_command_provider(
    workspace_path: Path,
    post_message_callback: Callable[[Path], Any],
) -> type[Provider]:
    return _create_path_action_command_provider(
        workspace_path, post_message_callback, "Delete"
    )


def create_rename_path_command_provider(
    workspace_path: Path,
    post_message_callback: Callable[[Path], Any],
) -> type[Provider]:
    return _create_path_action_command_provider(
        workspace_path, post_message_callback, "Rename"
    )


def create_move_path_command_provider(
    workspace_path: Path,
    post_message_callback: Callable[[Path], Any],
) -> type[Provider]:
    return _create_path_action_command_provider(
        workspace_path, post_message_callback, "Move"
    )


def _read_workspace_directories(workspace_path: Path) -> list[Path]:
    """Return all directories under workspace_path, including root.

    Includes dot-prefixed directories (e.g. .github/, .vscode/) but
    excludes .git directories and their subtrees at any depth.
    """
    dirs = [workspace_path]
    try:
        for dirpath, dirnames, _ in os.walk(
            workspace_path, onerror=lambda e: logger.debug("os.walk error: %s", e)
        ):
            # Prune .git directories in-place to prevent descent
            dirnames[:] = sorted(d for d in dirnames if d != ".git")
            dirs.extend(Path(dirpath) / d for d in dirnames)
    except OSError:
        logger.debug("OSError during os.walk of %s", workspace_path)
    dirs.sort()
    return dirs


def create_move_destination_command_provider(
    workspace_path: Path,
    source_path: Path,
    post_message_callback: Callable[[Path], Any],
) -> type[Provider]:
    """Create a provider that lists workspace directories as move destinations."""
    passed_workspace_path = workspace_path
    passed_source_path = source_path
    passed_callback = post_message_callback
    is_source_dir = source_path.is_dir()

    class MoveDestinationProvider(Provider):
        async def startup(self) -> None:
            worker = self.app.run_worker(
                partial(_read_workspace_directories, passed_workspace_path),
                thread=True,
            )
            all_dirs = await worker.wait()
            # Filter out source directory and its subtree
            self.dirs: list[Path] = []
            for d in all_dirs:
                if is_source_dir:
                    try:
                        d.relative_to(passed_source_path)
                        continue  # skip source and its children
                    except ValueError:
                        pass
                self.dirs.append(d)

        def _display_path(self, d: Path) -> str:
            if d == passed_workspace_path:
                return "."
            return str(d.relative_to(passed_workspace_path))

        def _help_text(self, d: Path) -> str:
            if d == passed_workspace_path:
                return "(workspace root)"
            return "Move to directory"

        async def discover(self) -> Hits:
            for d in self.dirs:
                display = self._display_path(d)
                yield DiscoveryHit(
                    display,
                    partial(passed_callback, d),
                    help=self._help_text(d),
                )

        async def search(self, query: str) -> Hits:
            matcher = self.matcher(query)
            dirs = self.dirs
            display_path = self._display_path

            def _match() -> list[tuple[float, str, Path]]:
                results: list[tuple[float, str, Path]] = []
                for d in dirs:
                    display = display_path(d)
                    score = matcher.match(display)
                    if score > 0:
                        results.append((score, display, d))
                return heapq.nlargest(_MAX_SEARCH_HITS, results)

            top = await asyncio.to_thread(_match)
            for score, display, d in top:
                yield Hit(
                    score,
                    matcher.highlight(display),
                    partial(passed_callback, d),
                    help=self._help_text(d),
                )

    return MoveDestinationProvider


class BaseCreatePathCommandProvider(Provider):
    """
    Base class for CreatePathCommandProvider
    """

    @property
    def is_dir(self) -> bool:
        raise NotImplementedError

    @property
    def workspace_path(self) -> Path:
        raise NotImplementedError

    @property
    def post_message_callback(self) -> Callable[[Path], Any]:
        raise NotImplementedError

    async def search(self, query: str) -> Hits:
        target_path = (self.workspace_path / query).resolve()

        yield Hit(
            1,
            str(target_path),
            partial(
                self.post_message_callback,
                target_path,
            ),
            help=f"Create this {'directory' if self.is_dir else 'file'}",
        )


def create_create_file_or_dir_command_provider(
    workspace_path: Path,
    is_dir: bool,
    post_message_callback: Callable[[Path], Any],
) -> type[Provider]:
    # rename for clarity
    passed_workspace_path = workspace_path
    passed_is_dir = is_dir
    passed_post_message_callback = post_message_callback

    class CreatePathCommandProvider(BaseCreatePathCommandProvider):
        """A command provider to create a new file or directory."""

        @property
        def is_dir(self) -> bool:
            return passed_is_dir

        @property
        def workspace_path(self) -> Path:
            return passed_workspace_path

        @property
        def post_message_callback(self) -> Callable[[Path], Any]:
            return passed_post_message_callback

    return CreatePathCommandProvider
