from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from rich.cells import cell_len
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Checkbox, Input, Label, Static
from textual.worker import Worker, WorkerState, get_current_worker

from textual_code.modals import (
    ReplacePreviewResult,
    ReplacePreviewScreen,
)
from textual_code.search import (
    preview_selected_replace,
    preview_workspace_replace,
    search_workspace,
)
from textual_code.widgets.checkbox_tree import CheckboxTree

_log = logging.getLogger(__name__)

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

    def on_unmount(self) -> None:
        self.workers.cancel_group(self, "search")
        self.workers.cancel_group(self, "replace_count")

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
        yield CheckboxTree(id="ws-results")
        yield Label(
            "↑↓ Navigate  ←→ Fold  Space Check  Enter Open",
            id="ws-key-hints",
        )

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

        checkbox_tree = self.query_one("#ws-results", CheckboxTree)
        checkbox_tree.clear()
        checkbox_tree.loading = False

        if not query:
            return

        workspace_path = getattr(self.app, "workspace_path", None)
        if workspace_path is None:
            return

        show_hidden = getattr(self.app, "default_show_hidden_files", True)
        checkbox_tree.loading = True
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
        worker = get_current_worker()
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
        if worker.is_cancelled:
            _log.debug("search worker cancelled, skipping callback")
            return
        try:
            self.app.call_from_thread(
                self._populate_results,
                response.results,
                workspace_path,
                response.inaccessible_paths,
            )
        except RuntimeError as exc:
            if "loop" not in str(exc).lower() and "closed" not in str(exc).lower():
                raise
            _log.debug("call_from_thread suppressed (app exiting): %s", exc)

    def _populate_results(
        self,
        results: list,
        workspace_path: Path,
        inaccessible_paths: list[str] | None = None,
    ) -> None:
        checkbox_tree = self.query_one("#ws-results", CheckboxTree)
        checkbox_tree.loading = False
        checkbox_tree.populate(results, workspace_path)

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
                checkbox_tree = self.query_one("#ws-results", CheckboxTree)
                checkbox_tree.loading = False
                checkbox_tree.clear()
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
        checkbox_tree = self.query_one("#ws-results", CheckboxTree)

        if checkbox_tree.all_selected:
            # Fast path: replace ALL matches (including beyond 500 cap)
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
        else:
            # Selected-only path
            selected = checkbox_tree.selected_results
            if not selected:
                status = self.query_one("#ws-replace-status", Label)
                status.update("No matches selected")
                return
            self._preview_selected_worker(
                workspace_path,
                query,
                replacement,
                use_regex,
                case_sensitive,
                selected,
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
        worker = get_current_worker()
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
        if worker.is_cancelled:
            _log.debug("replace preview worker cancelled, skipping callback")
            return
        try:
            self.app.call_from_thread(
                self._show_replace_preview,
                workspace_path,
                query,
                replacement,
                use_regex,
                respect_gitignore,
                case_sensitive,
                show_hidden_files,
                files_to_include,
                files_to_exclude,
                response,
                None,  # selected_results=None means "all" path
            )
        except RuntimeError as exc:
            if "loop" not in str(exc).lower() and "closed" not in str(exc).lower():
                raise
            _log.debug("call_from_thread suppressed (app exiting): %s", exc)

    @work(thread=True, exclusive=True, group="replace_count", exit_on_error=False)
    def _preview_selected_worker(
        self,
        workspace_path: Path,
        query: str,
        replacement: str,
        use_regex: bool,
        case_sensitive: bool,
        selected_results: list,
    ) -> None:
        worker = get_current_worker()
        response = preview_selected_replace(
            workspace_path,
            selected_results,
            query,
            replacement,
            use_regex,
            case_sensitive=case_sensitive,
        )
        if worker.is_cancelled:
            _log.debug("selected replace worker cancelled, skipping callback")
            return
        try:
            self.app.call_from_thread(
                self._show_replace_preview,
                workspace_path,
                query,
                replacement,
                use_regex,
                False,  # respect_gitignore (unused for selected path)
                case_sensitive,
                True,  # show_hidden_files (unused for selected path)
                "",  # files_to_include (unused)
                "",  # files_to_exclude (unused)
                response,
                selected_results,
            )
        except RuntimeError as exc:
            if "loop" not in str(exc).lower() and "closed" not in str(exc).lower():
                raise
            _log.debug("call_from_thread suppressed (app exiting): %s", exc)

    def _show_replace_preview(
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
        response: object,
        selected_results: list | None,
    ) -> None:
        from textual_code.search import (
            PreviewResponse,
            apply_selected_replace,
            replace_workspace,
        )

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

            if selected_results is None:
                # All-selected fast path: replace ALL matching files
                replace_result = replace_workspace(
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
                n = replace_result.replacements_count
                f = replace_result.files_modified
                status.update(f"Replaced {n} occurrence(s) in {f} file(s)")
            else:
                # Selected-only path
                apply_result = apply_selected_replace(
                    previews,
                    selected_results,
                    query,
                    replacement,
                    use_regex,
                    case_sensitive=case_sensitive,
                )
                n = apply_result.replacements_count
                f = apply_result.files_modified
                total = len(selected_results)
                status.update(
                    f"Replaced {n} of {total} selected occurrence(s) in {f} file(s)"
                )

        self.app.push_screen(modal, on_result)

    # ── Event handlers ─────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ws-search":
            self._run_search()
        elif event.button.id == "ws-replace-all":
            self._run_replace_all()

    @on(Checkbox.Changed, "#ws-regex")
    @on(Checkbox.Changed, "#ws-case-sensitive")
    @on(Checkbox.Changed, "#ws-gitignore")
    def _on_search_option_changed(self) -> None:
        """Clear stale results when search options change."""
        checkbox_tree = self.query_one("#ws-results", CheckboxTree)
        checkbox_tree.clear()

    @on(Input.Submitted, "#ws-query")
    @on(Input.Submitted, "#ws-include")
    @on(Input.Submitted, "#ws-exclude")
    def _on_query_submitted(self) -> None:
        self._run_search()

    @on(Input.Submitted, "#ws-replace")
    def _on_replace_submitted(self) -> None:
        self._run_replace_all()

    def on_checkbox_tree_node_selected(self, event: CheckboxTree.NodeSelected) -> None:
        self.post_message(
            self.OpenFileAtLineRequested(
                file_path=event.file_path,
                line_number=event.line_number,
            )
        )

    # ── Public helpers ─────────────────────────────────────────────────────────

    def focus_query_input(self) -> None:
        """Focus the search query input."""
        self.query_one("#ws-query", Input).focus()
