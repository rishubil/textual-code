import heapq
from collections.abc import Generator
from functools import partial
from pathlib import Path

from textual.command import Hit, Hits, Provider


class OpenFileCommandProvider(Provider):
    """A command provider to open a file in the viewer."""

    def read_files(self, workspace_path: Path) -> list[Path]:
        """Get a list of files in the workspace."""
        return list(workspace_path.glob("**/*"))

    async def startup(self) -> None:
        """Called once when the command palette is opened, prior to searching."""
        from textual_code.app import TextualCode

        assert isinstance(self.app, TextualCode)
        worker = self.app.run_worker(
            partial(self.read_files, self.app.workspace_path), thread=True
        )
        self.file_paths = await worker.wait()

    async def search(self, query: str) -> Hits:
        """Search for files."""
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
                                TextualCode.OpneFileRequested(path=path)
                            ),
                            path,
                        ),
                        help="Open this file in the viewer",
                    )

        for hit in heapq.nlargest(20, hits(), key=lambda hit: hit.score):
            yield hit
