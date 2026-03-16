from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Checkbox, Input, Label, ListItem, ListView, Static
from textual.worker import Worker, WorkerState

from textual_code.search import replace_workspace, search_workspace

_BTN_LABELS = {
    "ws-search": ("🔍 Search", "🔍"),
    "ws-replace-all": ("🔄 Replace All", "🔄"),
}


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
            yield Button(_BTN_LABELS["ws-search"][0], id="ws-search", variant="primary")
        with Horizontal(id="ws-search-options"):
            yield Checkbox(".*", id="ws-regex")
            yield Checkbox("Aa", id="ws-case-sensitive", value=True)
            yield Checkbox("Gitignore", id="ws-gitignore", value=True)
        with Vertical(id="ws-filter-bar"):
            yield Input(placeholder="Include files (src/**)", id="ws-include")
            yield Input(placeholder="Exclude files (dist/**)", id="ws-exclude")
        with Horizontal(id="ws-replace-bar"):
            yield Input(placeholder="Replace with...", id="ws-replace")
            yield Button(
                _BTN_LABELS["ws-replace-all"][0], id="ws-replace-all", variant="warning"
            )
        yield Label("", id="ws-replace-status")
        yield ListView(id="ws-results")

    # ── Responsive labels ──────────────────────────────────────────────────────

    def update_button_labels(self, *, compact: bool) -> None:
        """Switch button labels between icon+text and icon-only."""
        idx = 1 if compact else 0
        for btn_id, labels in _BTN_LABELS.items():
            self.query_one(f"#{btn_id}", Button).label = labels[idx]

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _get_result_data(self) -> list[tuple[Path, int]]:
        """Return the (file_path, line_number) pairs stored on each ListItem."""
        return getattr(self, "_result_data", [])

    def _read_search_inputs(self) -> tuple[str, bool, bool, bool, str, str]:
        """Read and return shared search inputs from the UI widgets."""
        return (
            self.query_one("#ws-query", Input).value.strip(),
            bool(self.query_one("#ws-regex", Checkbox).value),
            bool(self.query_one("#ws-gitignore", Checkbox).value),
            bool(self.query_one("#ws-case-sensitive", Checkbox).value),
            self.query_one("#ws-include", Input).value,
            self.query_one("#ws-exclude", Input).value,
        )

    # ── Search execution ───────────────────────────────────────────────────────

    def _run_search(self) -> None:
        """Read UI state and kick off a background search worker."""
        (
            query,
            use_regex,
            respect_gitignore,
            case_sensitive,
            files_to_include,
            files_to_exclude,
        ) = self._read_search_inputs()

        results_list = self.query_one("#ws-results", ListView)
        results_list.clear()
        self._result_data: list[tuple[Path, int]] = []

        if not query:
            return

        workspace_path = getattr(self.app, "workspace_path", None)
        if workspace_path is None:
            return

        self._search_worker(
            workspace_path,
            query,
            use_regex,
            respect_gitignore,
            case_sensitive,
            files_to_include,
            files_to_exclude,
        )

    @work(thread=True, exclusive=True)
    def _search_worker(
        self,
        workspace_path: Path,
        query: str,
        use_regex: bool,
        respect_gitignore: bool,
        case_sensitive: bool,
        files_to_include: str,
        files_to_exclude: str,
    ) -> None:
        results = search_workspace(
            workspace_path,
            query,
            use_regex,
            respect_gitignore=respect_gitignore,
            case_sensitive=case_sensitive,
            files_to_include=files_to_include,
            files_to_exclude=files_to_exclude,
        )
        self.app.call_from_thread(self._populate_results, results, workspace_path)

    def _populate_results(self, results: list, workspace_path: Path) -> None:
        results_list = self.query_one("#ws-results", ListView)
        results_list.clear()
        self._result_data = []

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

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.ERROR:
            results_list = self.query_one("#ws-results", ListView)
            results_list.append(ListItem(Label("Search failed")))
            self.app.log.error(f"Search worker error: {event.worker.error}")

    # ── Replace execution ──────────────────────────────────────────────────────

    def _run_replace_all(self) -> None:
        (
            query,
            use_regex,
            respect_gitignore,
            case_sensitive,
            files_to_include,
            files_to_exclude,
        ) = self._read_search_inputs()
        replacement = self.query_one("#ws-replace", Input).value
        status = self.query_one("#ws-replace-status", Label)

        if not query:
            return

        workspace_path = getattr(self.app, "workspace_path", None)
        if workspace_path is None:
            return

        result = replace_workspace(
            workspace_path,
            query,
            replacement,
            use_regex,
            respect_gitignore=respect_gitignore,
            case_sensitive=case_sensitive,
            files_to_include=files_to_include,
            files_to_exclude=files_to_exclude,
        )
        n, f = result.replacements_count, result.files_modified
        status.update(f"Replaced {n} occurrence(s) in {f} file(s)")

    # ── Event handlers ─────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ws-search":
            self._run_search()
        elif event.button.id == "ws-replace-all":
            self._run_replace_all()

    @on(Input.Submitted, "#ws-query")
    def _on_query_submitted(self) -> None:
        self._run_search()

    @on(Input.Submitted, "#ws-replace")
    def _on_replace_submitted(self) -> None:
        self._run_replace_all()

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
