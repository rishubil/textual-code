import heapq
from collections.abc import Callable, Generator
from functools import partial
from pathlib import Path
from typing import Any

from textual.command import DiscoveryHit, Hit, Hits, Provider


def _read_workspace_files(workspace_path: Path) -> list[Path]:
    """Return relative paths for all non-hidden files under workspace_path."""
    return [
        p.relative_to(workspace_path)
        for p in workspace_path.rglob("*")
        if p.is_file()
        and not any(
            part.startswith(".") for part in p.relative_to(workspace_path).parts
        )
    ]


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

            def hits() -> Generator[Hit, None, None]:
                for path in self.file_paths:
                    command = str(path)  # relative path
                    score = matcher.match(command)
                    if score > 0:
                        yield Hit(
                            score,
                            matcher.highlight(command),
                            partial(
                                post_message_callback,
                                workspace_path / path,  # absolute for callback
                            ),
                            help="Open this file in the viewer",
                        )

            for hit in heapq.nlargest(20, hits(), key=lambda hit: hit.score):
                yield hit

    return OpenFileCommandProvider


def _read_workspace_paths(workspace_path: Path) -> list[Path]:
    """Return all non-hidden files and directories under workspace_path."""
    return [
        p
        for p in workspace_path.rglob("*")
        if not any(part.startswith(".") for part in p.relative_to(workspace_path).parts)
    ]


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

            def hits() -> Generator[Hit, None, None]:
                for path in self.paths:
                    relative = path.relative_to(passed_workspace_path)
                    score = matcher.match(str(relative))
                    if score > 0:
                        kind = "directory" if path.is_dir() else "file"
                        yield Hit(
                            score,
                            matcher.highlight(str(relative)),
                            partial(passed_post_message_callback, path),
                            help=f"{passed_action_verb} {kind}",
                        )

            for hit in heapq.nlargest(20, hits(), key=lambda hit: hit.score):
                yield hit

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
    """Return all non-hidden directories under workspace_path, including root."""
    dirs = [workspace_path]
    dirs.extend(p for p in _read_workspace_paths(workspace_path) if p.is_dir())
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

            def hits() -> Generator[Hit, None, None]:
                for d in self.dirs:
                    display = self._display_path(d)
                    score = matcher.match(display)
                    if score > 0:
                        yield Hit(
                            score,
                            matcher.highlight(display),
                            partial(passed_callback, d),
                            help=self._help_text(d),
                        )

            for hit in heapq.nlargest(20, hits(), key=lambda hit: hit.score):
                yield hit

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
