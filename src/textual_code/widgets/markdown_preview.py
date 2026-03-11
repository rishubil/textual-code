from pathlib import Path

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Markdown

MARKDOWN_EXTENSIONS = {".md", ".markdown", ".mkd"}
PLACEHOLDER = "*Open a Markdown file in the left panel to see a preview.*"


class MarkdownPreviewPane(Widget):
    """Renders a live Markdown preview of a CodeEditor's content."""

    def compose(self) -> ComposeResult:
        yield Markdown(PLACEHOLDER)

    async def update_for(self, text: str, path: Path | None) -> None:
        md = self.query_one(Markdown)
        if path is None or path.suffix.lower() not in MARKDOWN_EXTENSIONS:
            await md.update(PLACEHOLDER)
        else:
            await md.update(text)
