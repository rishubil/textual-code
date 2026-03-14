import heapq
from collections.abc import Callable, Generator
from functools import partial
from pathlib import Path
from typing import Any

from textual.command import Hit, Hits, Provider


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


def create_delete_path_command_provider(
    workspace_path: Path,
    post_message_callback: Callable[[Path], Any],
) -> type[Provider]:
    passed_workspace_path = workspace_path
    passed_post_message_callback = post_message_callback

    class DeletePathCommandProvider(Provider):
        """A command provider to delete a file or directory."""

        def read_paths(self, workspace_path: Path) -> list[Path]:
            return [
                p
                for p in workspace_path.rglob("*")
                if not any(
                    part.startswith(".") for part in p.relative_to(workspace_path).parts
                )
            ]

        async def startup(self) -> None:
            worker = self.app.run_worker(
                partial(self.read_paths, passed_workspace_path), thread=True
            )
            self.paths = await worker.wait()

        async def search(self, query: str) -> Hits:
            matcher = self.matcher(query)

            def hits() -> Generator[Hit, None, None]:
                for path in self.paths:
                    relative = path.relative_to(passed_workspace_path)
                    score = matcher.match(str(relative))
                    if score > 0:
                        yield Hit(
                            score,
                            matcher.highlight(str(relative)),
                            partial(passed_post_message_callback, path),
                            help="Delete directory" if path.is_dir() else "Delete file",
                        )

            for hit in heapq.nlargest(20, hits(), key=lambda hit: hit.score):
                yield hit

    return DeletePathCommandProvider


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
