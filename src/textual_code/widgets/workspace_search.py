from __future__ import annotations

from dataclasses import dataclass
from itertools import groupby
from pathlib import Path

from rich.cells import cell_len
from rich.markup import escape as markup_escape
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Checkbox, Input, Label, Static, Tree
from textual.worker import Worker, WorkerState

from textual_code.modals import (
    ReplacePreviewResult,
    ReplacePreviewScreen,
)
from textual_code.search import (
    apply_workspace_replace,
    preview_workspace_replace,
    search_workspace,
)

_BTN_LABELS = {
    "ws-search": ("🔍 Search", "🔍"),
    "ws-replace-all": ("🔄 Replace All", "🔄"),
}

_BTN_PADDING = 2  # Button left + right padding (1 cell each side)

# Precomputed min-width for each label variant: {btn_id: (full_width, icon_width)}
_BTN_MIN_WIDTHS = {
    btn_id: (cell_len(full) + _BTN_PADDING, cell_len(icon) + _BTN_PADDING)
    for btn_id, (full, icon) in _BTN_LABELS.items()
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
        tree = Tree("Results", id="ws-results")
        tree.show_root = False
        tree.show_guides = False
        yield tree

    # ── Responsive labels ──────────────────────────────────────────────────────

    def update_button_labels(self, *, compact: bool) -> None:
        """Switch button labels between icon+text and icon-only."""
        idx = 1 if compact else 0
        for btn_id, labels in _BTN_LABELS.items():
            btn = self.query_one(f"#{btn_id}", Button)
            btn.label = labels[idx]
            btn.styles.min_width = _BTN_MIN_WIDTHS[btn_id][idx]

    # ── Internal helpers ───────────────────────────────────────────────────────

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

        results_tree = self.query_one("#ws-results", Tree)
        results_tree.clear()
        results_tree.loading = False

        if not query:
            return

        workspace_path = getattr(self.app, "workspace_path", None)
        if workspace_path is None:
            return

        show_hidden = getattr(self.app, "default_show_hidden_files", True)
        results_tree.loading = True
        self._search_worker(
            workspace_path,
            query,
            use_regex,
            respect_gitignore,
            case_sensitive,
            show_hidden,
            files_to_include,
            files_to_exclude,
        )

    @work(thread=True, exclusive=True, group="search", exit_on_error=False)
    def _search_worker(
        self,
        workspace_path: Path,
        query: str,
        use_regex: bool,
        respect_gitignore: bool,
        case_sensitive: bool,
        show_hidden_files: bool,
        files_to_include: str,
        files_to_exclude: str,
    ) -> None:
        response = search_workspace(
            workspace_path,
            query,
            use_regex,
            respect_gitignore=respect_gitignore,
            show_hidden_files=show_hidden_files,
            case_sensitive=case_sensitive,
            files_to_include=files_to_include,
            files_to_exclude=files_to_exclude,
        )
        self.app.call_from_thread(
            self._populate_results,
            response.results,
            workspace_path,
            response.inaccessible_paths,
        )

    def _populate_results(
        self,
        results: list,
        workspace_path: Path,
        inaccessible_paths: list[str] | None = None,
    ) -> None:
        results_tree = self.query_one("#ws-results", Tree)
        results_tree.loading = False
        results_tree.clear()

        if not results:
            results_tree.root.add_leaf("No results")
        else:
            for file_path, file_results in groupby(results, key=lambda r: r.file_path):
                matches = list(file_results)
                count = len(matches)
                try:
                    relative = file_path.relative_to(workspace_path)
                except ValueError:
                    relative = file_path
                suffix = "match" if count == 1 else "matches"
                first_line = matches[0].line_number
                file_node = results_tree.root.add(
                    markup_escape(f"{relative} ({count} {suffix})"),
                    data=(file_path, first_line),
                    expand=True,
                )
                for match in matches:
                    file_node.add_leaf(
                        markup_escape(
                            f"{match.line_number}: {match.line_text.strip()}"
                        ),
                        data=(file_path, match.line_number),
                    )

        if inaccessible_paths:
            count = len(inaccessible_paths)
            preview = ", ".join(inaccessible_paths[:3])
            if count > 3:
                preview += f" (+{count - 3} more)"
            self.app.notify(
                f"Could not search {count} path(s): {preview}",
                severity="warning",
            )

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.group not in ("search", "replace_count"):
            return
        if event.state == WorkerState.ERROR:
            if event.worker.group == "search":
                results_tree = self.query_one("#ws-results", Tree)
                results_tree.loading = False
                results_tree.clear()
                results_tree.root.add_leaf("Search failed")
            elif event.worker.group == "replace_count":
                status = self.query_one("#ws-replace-status", Label)
                status.update("Replace count failed")
            self.app.log.error(
                f"{event.worker.group} worker error: {event.worker.error}"
            )

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

        if not query:
            return

        workspace_path = getattr(self.app, "workspace_path", None)
        if workspace_path is None:
            return

        show_hidden = getattr(self.app, "default_show_hidden_files", True)
        self._preview_replace_worker(
            workspace_path,
            query,
            replacement,
            use_regex,
            respect_gitignore,
            case_sensitive,
            show_hidden,
            files_to_include,
            files_to_exclude,
        )

    @work(thread=True, exclusive=True, group="replace_count", exit_on_error=False)
    def _preview_replace_worker(
        self,
        workspace_path: Path,
        query: str,
        replacement: str,
        use_regex: bool,
        respect_gitignore: bool,
        case_sensitive: bool,
        show_hidden_files: bool,
        files_to_include: str,
        files_to_exclude: str,
    ) -> None:
        response = preview_workspace_replace(
            workspace_path,
            query,
            replacement,
            use_regex,
            respect_gitignore=respect_gitignore,
            show_hidden_files=show_hidden_files,
            files_to_include=files_to_include,
            files_to_exclude=files_to_exclude,
            case_sensitive=case_sensitive,
        )

        self.app.call_from_thread(
            self._show_replace_preview,
            query,
            replacement,
            use_regex,
            case_sensitive,
            response,
        )

    def _show_replace_preview(
        self,
        query: str,
        replacement: str,
        use_regex: bool,
        case_sensitive: bool,
        response: object,
    ) -> None:
        from textual_code.search import PreviewResponse

        assert isinstance(response, PreviewResponse)
        previews = response.previews
        status = self.query_one("#ws-replace-status", Label)

        if not previews:
            status.update("No matches found")
            return

        modal = ReplacePreviewScreen(
            previews=previews,
            is_truncated=response.is_truncated,
        )

        def on_result(result: ReplacePreviewResult | None) -> None:
            if result is None or result.is_cancelled or not result.should_apply:
                return
            apply_result = apply_workspace_replace(
                previews,
                query,
                replacement,
                use_regex,
                case_sensitive=case_sensitive,
            )
            n = apply_result.replacements_count
            f = apply_result.files_modified
            msg = f"Replaced {n} occurrence(s) in {f} file(s)"
            if apply_result.files_skipped > 0:
                skipped = apply_result.files_skipped
                msg += f" ({skipped} skipped)"
                self.app.notify(
                    f"Skipped: {', '.join(apply_result.skipped_files)}",
                    severity="warning",
                )
            if apply_result.failed_files:
                self.app.notify(
                    f"Failed: {', '.join(apply_result.failed_files)}",
                    severity="error",
                )
            status.update(msg)

        self.app.push_screen(modal, on_result)

    # ── Event handlers ─────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ws-search":
            self._run_search()
        elif event.button.id == "ws-replace-all":
            self._run_replace_all()

    @on(Input.Submitted, "#ws-query")
    @on(Input.Submitted, "#ws-include")
    @on(Input.Submitted, "#ws-exclude")
    def _on_query_submitted(self) -> None:
        self._run_search()

    @on(Input.Submitted, "#ws-replace")
    def _on_replace_submitted(self) -> None:
        self._run_replace_all()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        data = event.node.data
        if data is None:
            return
        file_path, line_number = data
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
