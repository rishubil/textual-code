from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button, Checkbox, Input, Label, ListItem, ListView, Static

from textual_code.search import search_workspace


class WorkspaceSearchPane(Static):
    """Sidebar panel for searching text across all workspace files."""

    @dataclass
    class OpenFileAtLineRequested(Message):
        """Posted when the user selects a search result."""

        file_path: Path
        line_number: int  # 1-based; 0 means open file only

    def compose(self) -> ComposeResult:
        with Horizontal(id="ws-search-bar"):
            yield Input(placeholder="Search workspace...", id="ws-query")
            yield Checkbox(".*", id="ws-regex")
            yield Button("Search", id="ws-search", variant="primary")
        yield ListView(id="ws-results")

    # ── Internal state ─────────────────────────────────────────────────────────

    def _get_result_data(self) -> list[tuple[Path, int]]:
        """Return the (file_path, line_number) pairs stored on each ListItem."""
        return getattr(self, "_result_data", [])

    # ── Search execution ───────────────────────────────────────────────────────

    def _run_search(self) -> None:
        query = self.query_one("#ws-query", Input).value.strip()
        use_regex = bool(self.query_one("#ws-regex", Checkbox).value)
        results_list = self.query_one("#ws-results", ListView)

        results_list.clear()
        self._result_data: list[tuple[Path, int]] = []

        if not query:
            return

        workspace_path = getattr(self.app, "workspace_path", None)
        if workspace_path is None:
            return

        results = search_workspace(workspace_path, query, use_regex)

        if not results:
            results_list.append(ListItem(Label("No results")))
            return

        for result in results:
            try:
                relative = result.file_path.relative_to(workspace_path)
            except ValueError:
                relative = result.file_path
            label_text = f"{relative}:{result.line_number}  {result.line_text.strip()}"
            results_list.append(ListItem(Label(label_text)))
            self._result_data.append((result.file_path, result.line_number))

    # ── Event handlers ─────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ws-search":
            self._run_search()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._run_search()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        index = event.list_view.index
        result_data = self._get_result_data()
        if index is None or index >= len(result_data):
            return
        file_path, line_number = result_data[index]
        self.post_message(
            self.OpenFileAtLineRequested(
                file_path=file_path,
                line_number=line_number,
            )
        )

    # ── Public helpers ─────────────────────────────────────────────────────────

    def focus_query_input(self) -> None:
        """Focus the search query input."""
        self.query_one("#ws-query", Input).focus()
