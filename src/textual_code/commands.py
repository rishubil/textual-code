import heapq
from collections.abc import Generator
from functools import partial
from pathlib import Path

from textual.command import Hit, Hits, Provider


class OpenFileCommandProvider(Provider):
    """A command provider to open a file in the viewer."""

    def read_files(self, workspace_path: Path) -> list[Path]:
        return list(workspace_path.glob("**/*"))

    async def startup(self) -> None:
        from textual_code.app import TextualCode

        assert isinstance(self.app, TextualCode)
        worker = self.app.run_worker(
            partial(self.read_files, self.app.workspace_path), thread=True
        )
        self.file_paths = await worker.wait()

    async def search(self, query: str) -> Hits:
        from textual_code.app import TextualCode

        matcher = self.matcher(query)

        def hits() -> Generator[Hit, None, None]:
            for path in self.file_paths:
                command = f"{str(path)}"
                score = matcher.match(command)
                if score > 0:
                    yield Hit(
                        score,
                        matcher.highlight(command),
                        partial(
                            lambda path: self.app.post_message(
                                TextualCode.OpenFileRequested(path=path)
                            ),
                            path,
                        ),
                        help="Open this file in the viewer",
                    )

        for hit in heapq.nlargest(20, hits(), key=lambda hit: hit.score):
            yield hit


class BaseCreatePathCommandProvider(Provider):
    @property
    def is_dir(self) -> bool:
        raise NotImplementedError

    async def startup(self) -> None:
        from textual_code.app import TextualCode

        assert isinstance(self.app, TextualCode)
        self.workspace_path: Path = self.app.workspace_path

    async def search(self, query: str) -> Hits:
        from textual_code.app import TextualCode

        target_path = (self.workspace_path / query).resolve()

        yield Hit(
            1,
            str(target_path),
            partial(
                lambda path, is_dir: self.app.post_message(
                    TextualCode.CreateFileOrDirRequested(path=path, is_dir=is_dir)
                ),
                target_path,
                self.is_dir,
            ),
            help=f"Create this {'directory' if self.is_dir else 'file'}",
        )


class CreateDirCommandProvider(BaseCreatePathCommandProvider):
    """A command provider to create a new directory."""

    @property
    def is_dir(self) -> bool:
        return True


class CreateFileCommandProvider(BaseCreatePathCommandProvider):
    """A command provider to create a new file."""

    @property
    def is_dir(self) -> bool:
        return False
