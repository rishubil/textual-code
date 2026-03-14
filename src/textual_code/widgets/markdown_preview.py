from pathlib import Path

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Markdown

MARKDOWN_EXTENSIONS = {".md", ".markdown", ".mkd"}
PLACEHOLDER = "*Open a Markdown file in an editor tab to see a preview.*"


class MarkdownPreviewPane(VerticalScroll):
    """Renders a live Markdown preview of a CodeEditor's content."""

    DEFAULT_CSS = """
    MarkdownPreviewPane {
        height: 1fr;
        border: tall transparent;
    }
    MarkdownPreviewPane:focus {
        border: tall $accent;
    }
    """

    def __init__(self, source_path: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.source_path = source_path

    def compose(self) -> ComposeResult:
        yield Markdown(PLACEHOLDER)

    async def update_for(self, text: str, path: Path | None) -> None:
        md = self.query_one(Markdown)
        if path is None or path.suffix.lower() not in MARKDOWN_EXTENSIONS:
            await md.update(PLACEHOLDER)
        else:
            await md.update(text)
