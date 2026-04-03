from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    ListItem,
    ListView,
)

if TYPE_CHECKING:
    from textual_code.search import FileDiffPreview


@dataclass
class FindModalResult:
    """
    The result of the Find modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # The search query, or None if cancelled.
    query: str | None
    # Whether to use regex matching.
    use_regex: bool = False


class FindModalScreen(ModalScreen[FindModalResult]):
    """
    Modal dialog for finding text in the current file.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Find", id="title"),
            Input(placeholder="Search...", id="query"),
            Checkbox("Use regex", id="use_regex"),
            Button("Find", variant="primary", id="find"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Input.Submitted, "#query")
    @on(Button.Pressed, "#find")
    def on_find(self) -> None:
        self.dismiss(
            FindModalResult(
                is_cancelled=False,
                query=self.query_one(Input).value,
                use_regex=self.query_one("#use_regex", Checkbox).value,
            )
        )

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(FindModalResult(is_cancelled=True, query=None))


@dataclass
class ReplaceModalResult:
    """
    The result of the Replace modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # The action to perform: "replace" or "replace_all", or None if cancelled.
    action: str | None
    # The search query, or None if cancelled.
    find_query: str | None
    # The replacement text, or None if cancelled.
    replace_text: str | None
    # Whether to use regex matching.
    use_regex: bool = False


class ReplaceModalScreen(ModalScreen[ReplaceModalResult]):
    """
    Modal dialog for finding and replacing text in the current file.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Replace", id="title"),
            Input(placeholder="Find...", id="find_query"),
            Input(placeholder="Replace with...", id="replace_text"),
            Checkbox("Use regex", id="use_regex"),
            Button("Replace", variant="primary", id="replace"),
            Button("Replace All", variant="primary", id="replace_all"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Button.Pressed, "#replace")
    def on_replace(self) -> None:
        self.dismiss(
            ReplaceModalResult(
                is_cancelled=False,
                action="replace",
                find_query=self.query_one("#find_query", Input).value,
                replace_text=self.query_one("#replace_text", Input).value,
                use_regex=self.query_one("#use_regex", Checkbox).value,
            )
        )

    @on(Button.Pressed, "#replace_all")
    def on_replace_all(self) -> None:
        self.dismiss(
            ReplaceModalResult(
                is_cancelled=False,
                action="replace_all",
                find_query=self.query_one("#find_query", Input).value,
                replace_text=self.query_one("#replace_text", Input).value,
                use_regex=self.query_one("#use_regex", Checkbox).value,
            )
        )

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(
            ReplaceModalResult(
                is_cancelled=True, action=None, find_query=None, replace_text=None
            )
        )


@dataclass
class ReplacePreviewResult:
    """Result of the Replace Preview screen."""

    is_cancelled: bool
    should_apply: bool


class ReplacePreviewScreen(ModalScreen[ReplacePreviewResult]):
    """Per-file diff preview screen before workspace-wide Replace All."""

    DEFAULT_CSS = """
    ReplacePreviewScreen {
        align: center middle;
    }
    ReplacePreviewScreen #dialog {
        width: 80%;
        height: 80%;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }
    ReplacePreviewScreen #title {
        height: 1;
        width: 1fr;
        text-style: bold;
        content-align: center middle;
        margin-bottom: 1;
    }
    ReplacePreviewScreen #panels {
        height: 1fr;
    }
    ReplacePreviewScreen #file-list {
        width: 30;
        margin-right: 1;
    }
    ReplacePreviewScreen #diff-view {
        width: 1fr;
        overflow-y: auto;
    }
    ReplacePreviewScreen .buttons {
        height: 3;
        layout: horizontal;
    }
    ReplacePreviewScreen .buttons Button {
        width: 1fr;
        margin: 0 1;
    }
    ReplacePreviewScreen #scope-info {
        height: auto;
        width: 1fr;
        color: $text-muted;
        text-style: italic;
        content-align: center middle;
        margin-bottom: 1;
    }
    """

    # No BINDINGS — escape must not dismiss a destructive action screen

    def __init__(
        self,
        previews: list[FileDiffPreview],
    ) -> None:
        super().__init__()
        self._previews = previews
        self._total_occurrences = sum(p.replacement_count for p in previews)

    def compose(self) -> ComposeResult:
        from textual.containers import VerticalScroll
        from textual.widgets import Static

        title = (
            f"Replace Preview \u00b7 {len(self._previews)} file(s)"
            f" \u00b7 {self._total_occurrences} occurrence(s)"
        )

        items = [
            ListItem(
                Label(f"{p.rel_path} ({p.replacement_count})"),
            )
            for p in self._previews
        ]

        with Vertical(id="dialog"):
            yield Label(title, id="title")
            with Horizontal(id="panels"):
                yield ListView(*items, id="file-list")
                with VerticalScroll(id="diff-view"):
                    yield Static("", id="diff-content")
            yield Label(
                "Only the checked matches will be modified. "
                "Unchecked items will not be changed.",
                id="scope-info",
            )
            with Horizontal(classes="buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Apply All", variant="warning", id="apply-all")

    def on_mount(self) -> None:
        if self._previews:
            self._show_diff(0)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        list_view = self.query_one("#file-list", ListView)
        idx = list_view.index
        if idx is not None and 0 <= idx < len(self._previews):
            self._show_diff(idx)

    def _show_diff(self, index: int) -> None:
        from rich.markup import escape
        from textual.widgets import Static

        preview = self._previews[index]
        parts: list[str] = []
        for line in preview.diff_lines:
            escaped = escape(line.rstrip("\n"))
            if line.startswith(("---", "+++", "@@")):
                parts.append(f"[$text-muted]{escaped}[/]")
            elif line.startswith("-"):
                parts.append(f"[$text-error]{escaped}[/]")
            elif line.startswith("+"):
                parts.append(f"[$text-success]{escaped}[/]")
            else:
                parts.append(escaped)

        content = Content.from_markup("\n".join(parts))
        diff_static = self.query_one("#diff-content", Static)
        diff_static.update(content)

    @on(Button.Pressed, "#apply-all")
    def on_apply_all(self) -> None:
        self.dismiss(ReplacePreviewResult(is_cancelled=False, should_apply=True))

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(ReplacePreviewResult(is_cancelled=True, should_apply=False))
