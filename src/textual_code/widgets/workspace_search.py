from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path

from rich.cells import cell_len
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Checkbox, Input, Label, Static, Tree
from textual.worker import Worker, WorkerState

from textual_code.modals import (
    ReplaceAllConfirmModalResult,
    ReplaceAllConfirmModalScreen,
    ReplacePreview,
)
from textual_code.search import (
    WorkspaceSearchResponse,
    replace_workspace,
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


_REPLACE_COUNT_MAX = 500  # Must match search_workspace() default max_results


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

        results_tree.loading = True
        self._search_worker(
            workspace_path,
            query,
            use_regex,
            respect_gitignore,
            case_sensitive,
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
        files_to_include: str,
        files_to_exclude: str,
    ) -> None:
        response = search_workspace(
            workspace_path,
            query,
            use_regex,
            respect_gitignore=respect_gitignore,
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
                    f"{relative} ({count} {suffix})",
                    data=(file_path, first_line),
                    expand=True,
                )
                for match in matches:
                    file_node.add_leaf(
                        f"{match.line_number}: {match.line_text.strip()}",
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

        self._count_for_replace_worker(
            workspace_path,
            query,
            replacement,
            use_regex,
            respect_gitignore,
            case_sensitive,
            files_to_include,
            files_to_exclude,
        )

    @work(thread=True, exclusive=True, group="replace_count", exit_on_error=False)
    def _count_for_replace_worker(
        self,
        workspace_path: Path,
        query: str,
        replacement: str,
        use_regex: bool,
        respect_gitignore: bool,
        case_sensitive: bool,
        files_to_include: str,
        files_to_exclude: str,
    ) -> None:
        response = search_workspace(
            workspace_path,
            query,
            use_regex,
            respect_gitignore=respect_gitignore,
            case_sensitive=case_sensitive,
            files_to_include=files_to_include,
            files_to_exclude=files_to_exclude,
        )

        self.app.call_from_thread(
            self._show_replace_confirm,
            workspace_path,
            query,
            replacement,
            use_regex,
            respect_gitignore,
            case_sensitive,
            files_to_include,
            files_to_exclude,
            response,
        )

    def _show_replace_confirm(
        self,
        workspace_path: Path,
        query: str,
        replacement: str,
        use_regex: bool,
        respect_gitignore: bool,
        case_sensitive: bool,
        files_to_include: str,
        files_to_exclude: str,
        response: WorkspaceSearchResponse,
    ) -> None:
        results = response.results
        status = self.query_one("#ws-replace-status", Label)

        if not results:
            status.update("No matches found")
            return

        files_count = len({r.file_path for r in results})
        occurrences_count = len(results)
        is_truncated = occurrences_count >= _REPLACE_COUNT_MAX

        first = results[0]
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(query if use_regex else re.escape(query), flags)
        except re.error:
            return
        preview_before = first.line_text.strip()
        preview_after = pattern.sub(replacement, preview_before, count=1)

        try:
            preview_file = str(first.file_path.relative_to(workspace_path))
        except ValueError:
            preview_file = str(first.file_path)

        preview = ReplacePreview(
            file=preview_file,
            line_num=first.line_number,
            before=preview_before,
            after=preview_after,
        )

        modal = ReplaceAllConfirmModalScreen(
            files_count=files_count,
            occurrences_count=occurrences_count,
            is_truncated=is_truncated,
            preview=preview,
        )

        def on_result(result: ReplaceAllConfirmModalResult | None) -> None:
            if result is None or result.is_cancelled or not result.should_replace:
                return
            replace_result = replace_workspace(
                workspace_path,
                query,
                replacement,
                use_regex,
                respect_gitignore=respect_gitignore,
                case_sensitive=case_sensitive,
                files_to_include=files_to_include,
                files_to_exclude=files_to_exclude,
            )
            n, f = replace_result.replacements_count, replace_result.files_modified
            status.update(f"Replaced {n} occurrence(s) in {f} file(s)")

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
