from pathlib import Path

from markdown_it import MarkdownIt
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Markdown

MARKDOWN_EXTENSIONS = {".md", ".markdown", ".mkd"}
PLACEHOLDER = "*Open a Markdown file in an editor tab to see a preview.*"

# Token types that close an inline span (bold, italic, strikethrough, link).
_INLINE_CLOSE = frozenset({"strong_close", "em_close", "s_close", "link_close"})


def _make_parser() -> MarkdownIt:
    """Return a markdown-it parser with a core rule that moves leading spaces.

    When Rich renders bold→normal text transitions to SVG, a leading non-breaking
    space at the start of the normal span is not rendered by rsvg-convert.
    This rule moves that leading space to the trailing position of the preceding
    inline span, where it renders correctly.
    """
    md = MarkdownIt("gfm-like")

    def _move_trailing_spaces(state) -> None:
        for token in state.tokens:
            if token.type != "inline" or not token.children:
                continue
            children = token.children
            for i in range(len(children) - 1):
                if children[i].type not in _INLINE_CLOSE:
                    continue
                if children[i + 1].type != "text":
                    continue
                next_text = children[i + 1].content
                if not next_text.startswith(" "):
                    continue
                # Search backward for a text token to attach the space to.
                # Abort if we hit an open token (avoids moving space into nested span).
                for j in range(i - 1, -1, -1):
                    if children[j].type.endswith("_open"):
                        break
                    if children[j].type == "text" and children[j].content:
                        children[j].content += " "
                        children[i + 1].content = next_text[1:]
                        break

    md.core.ruler.push("move_trailing_spaces", _move_trailing_spaces)
    return md


class MarkdownPreviewPane(Widget):
    """Renders a live Markdown preview of a CodeEditor's content."""

    DEFAULT_CSS = """
    MarkdownPreviewPane {
        height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(self, source_path: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.source_path = source_path

    def compose(self) -> ComposeResult:
        yield Markdown(PLACEHOLDER, parser_factory=_make_parser)

    async def update_for(self, text: str, path: Path | None) -> None:
        md = self.query_one(Markdown)
        if path is None or path.suffix.lower() not in MARKDOWN_EXTENSIONS:
            await md.update(PLACEHOLDER)
        else:
            await md.update(text)
