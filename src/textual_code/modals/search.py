from __future__ import annotations

import heapq
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.events import Click
from textual.fuzzy import Matcher
from textual.screen import ModalScreen
from textual.widgets import (
    Checkbox,
    Input,
    OptionList,
)
from textual.worker import get_current_worker

_logger = logging.getLogger(__name__)

_MAX_DISCOVERY = 50
"""Maximum number of items shown in discovery (empty query)."""

_MAX_SEARCH_HITS = 20
"""Maximum number of search results returned."""

_RAPIDFUZZ_THRESHOLD = 5000
"""Switch to rapidfuzz scorer when candidate count exceeds this."""


def _adjust_score_for_path(score: float, display: str, query: str) -> float:
    """Apply path-aware adjustments to a rapidfuzz score.

    Bonuses:
    - Filename match: +15 if query is a substring of the filename
    - Short path: up to +10 for shorter relative paths
    - Shallow depth: +5 for root, +3 for depth 1
    """
    # Normalize to forward slashes for consistent scoring on all platforms.
    normalized = display.replace("\\", "/")
    query_lower = query.lower()
    slash_idx = normalized.rfind("/")
    filename = normalized[slash_idx + 1 :] if slash_idx >= 0 else normalized
    if query_lower in filename.lower():
        score += 15
    score += 10 * max(0.0, 1.0 - len(normalized) / 200)
    depth = normalized.count("/")
    if depth == 0:
        score += 5
    elif depth == 1:
        score += 3
    return score


class PathSearchModal(ModalScreen[Path | None]):
    """fzf-like modal for searching and selecting paths.

    Supports streaming scan with chunked delivery, fuzzy matching in a
    background thread, and class-level cache for instant results on re-open.
    """

    # Class-level cache: maps (workspace_path, cache_key) -> tuple of paths.
    _cache: ClassVar[dict[tuple[Path, str], tuple[Path, ...]]] = {}
    _cache_dirty: ClassVar[set[tuple[Path, str]]] = set()

    DEFAULT_CSS = """
    PathSearchModal {
        background: $background 60%;
        align-horizontal: center;
    }
    #path-search-container {
        margin-top: 3;
        height: 100%;
        visibility: hidden;
        background: $surface;
        &:dark { background: $panel-darken-1; }
    }
    #path-search-input-bar {
        height: auto;
        visibility: visible;
        border: hkey black 50%;
    }
    #path-search-input-bar.--has-results {
        border-bottom: none;
    }
    #path-search-icon {
        margin-left: 1;
        margin-top: 1;
        width: 2;
    }
    #path-search-spinner {
        width: auto;
        margin-right: 1;
        margin-top: 1;
        visibility: hidden;
    }
    #path-search-spinner.--visible {
        visibility: visible;
    }
    #path-search-gitignore {
        width: auto;
        border: none;
        padding: 0;
        height: 1;
        margin-top: 1;
        margin-right: 1;
    }
    #path-search-input, #path-search-input:focus {
        border: blank;
        width: 1fr;
        padding-left: 0;
        background: transparent;
        background-tint: 0%;
    }
    #path-search-results-area {
        overlay: screen;
        height: auto;
    }
    #path-search-results {
        visibility: hidden;
        border-top: blank;
        border-bottom: hkey black;
        border-left: none;
        border-right: none;
        height: auto;
        max-height: 70vh;
        background: transparent;
        padding: 0;
    }
    #path-search-results.--visible {
        visibility: visible;
    }
    #path-search-results > .option-list--option {
        padding: 0 2;
    }
    #path-search-results > .option-list--option-highlighted {
        color: $block-cursor-blurred-foreground;
        background: $block-cursor-blurred-background;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close"),
        Binding("down", "cursor_down", "Next", show=False),
        Binding("up", "cursor_up", "Previous", show=False),
        Binding("pagedown", "page_down", "Page down", show=False),
        Binding("pageup", "page_up", "Page up", show=False),
    ]

    def __init__(
        self,
        workspace_path: Path,
        *,
        scan_func: Callable[[Path], list[Path]],
        cache_key: str = "",
        placeholder: str = "Search...",
        path_filter: Callable[[Path], bool] | None = None,
        show_gitignore_toggle: bool = False,
        unfiltered_scan_func: Callable[[Path], list[Path]] | None = None,
        unfiltered_cache_key: str = "",
    ) -> None:
        super().__init__()
        self._workspace_path = workspace_path
        self._scan_func = scan_func
        self._path_filter = path_filter
        self._placeholder = placeholder
        self._cache_key_str = cache_key
        self._all_paths: list[Path] = []
        # Pre-computed display strings (parallel to _all_paths).
        self._display_strings: list[str] = []
        # Maps current OptionList indices to Path objects.
        self._result_paths: list[Path] = []
        # Generation counter to discard stale search results (main-thread only).
        self._search_generation: int = 0
        # Generation counter to discard stale scan results (main-thread only).
        self._scan_generation: int = 0
        # Gitignore toggle support
        self._show_gitignore_toggle = show_gitignore_toggle
        self._filtered_scan_func = scan_func
        self._filtered_cache_key = cache_key
        self._unfiltered_scan_func = unfiltered_scan_func
        self._unfiltered_cache_key = unfiltered_cache_key

    @classmethod
    def invalidate_cache(cls, workspace_path: Path | None = None) -> None:
        """Mark cached scan results as dirty (or clear all)."""
        if workspace_path is None:
            cls._cache.clear()
            cls._cache_dirty.clear()
        else:
            for key in list(cls._cache):
                if key[0] == workspace_path:
                    cls._cache_dirty.add(key)

    def compose(self) -> ComposeResult:
        from textual.widgets import Static

        with Vertical(id="path-search-container"):
            with Horizontal(id="path-search-input-bar"):
                yield Static("\U0001f50e", id="path-search-icon")
                yield Input(placeholder=self._placeholder, id="path-search-input")
                if self._show_gitignore_toggle:
                    yield Checkbox("Gitignore", id="path-search-gitignore", value=True)
                yield Static("\u23f3", id="path-search-spinner")
            with Vertical(id="path-search-results-area"):
                yield OptionList(id="path-search-results")

    def on_mount(self) -> None:
        self.query_one("#path-search-input", Input).focus()
        self._load_or_scan()

    def _load_or_scan(self) -> None:
        """Load paths from cache or start a fresh scan."""
        self._scan_generation += 1
        self._search_generation += 1
        self._all_paths = []
        self._display_strings = []
        self._result_paths = []
        self.query_one("#path-search-results", OptionList).clear_options()
        self._update_results_visibility()
        self._set_spinner_visible(False)
        ck = (
            (self._workspace_path, self._cache_key_str) if self._cache_key_str else None
        )
        if ck and ck in PathSearchModal._cache:
            is_dirty = ck in PathSearchModal._cache_dirty
            _logger.debug(
                "PathSearchModal: cache hit (%s), dirty=%s",
                ck[1],
                is_dirty,
            )
            if is_dirty:
                self._start_scan()
            else:
                self._load_paths(list(PathSearchModal._cache[ck]))
                self._refresh_display()
        else:
            _logger.debug("PathSearchModal: cache miss, starting scan")
            self._start_scan()

    def _load_paths(self, paths: list[Path]) -> None:
        """Load paths into display state, applying filter if set."""
        if self._path_filter:
            paths = [p for p in paths if self._path_filter(p)]
        self._all_paths = paths
        self._display_strings = [self._display_path(p) for p in self._all_paths]
        self._show_discovery()

    def _set_spinner_visible(self, visible: bool) -> None:
        """Toggle the scanning spinner indicator."""
        import contextlib

        from textual.css.query import NoMatches

        with contextlib.suppress(NoMatches):
            self.query_one("#path-search-spinner").set_class(visible, "--visible")

    @work(thread=True, exclusive=True)
    def _start_scan(self) -> None:
        """Scan workspace in a background thread."""
        worker = get_current_worker()
        generation = self._scan_generation
        cache_key = self._cache_key_str
        try:
            self.app.call_from_thread(self._set_spinner_visible, True)
        except RuntimeError as exc:
            if "loop" not in str(exc).lower() and "closed" not in str(exc).lower():
                raise
            _logger.debug("call_from_thread suppressed (app exiting): %s", exc)
            return
        t0 = time.monotonic()
        _logger.debug("PathSearchModal: scan started (gen %d)", generation)
        try:
            results = self._scan_func(self._workspace_path)
            if worker.is_cancelled:
                _logger.debug("scan worker cancelled (gen %d)", generation)
                return
            if self._path_filter:
                results = [p for p in results if self._path_filter(p)]
            try:
                self.app.call_from_thread(
                    self._on_scan_results, results, generation, cache_key
                )
            except RuntimeError as exc:
                if "loop" not in str(exc).lower() and "closed" not in str(exc).lower():
                    raise
                _logger.debug("call_from_thread suppressed (app exiting): %s", exc)
        finally:
            elapsed = time.monotonic() - t0
            _logger.debug(
                "PathSearchModal: scan finished in %.2fs (gen %d)",
                elapsed,
                generation,
            )
            if not worker.is_cancelled:
                try:
                    self.app.call_from_thread(self._on_scan_complete, generation)
                except RuntimeError as exc:
                    if (
                        "loop" not in str(exc).lower()
                        and "closed" not in str(exc).lower()
                    ):
                        raise
                    _logger.debug("call_from_thread suppressed (app exiting): %s", exc)

    def _on_scan_results(
        self, results: list[Path], generation: int, cache_key: str
    ) -> None:
        """Load scan results into display state (main thread)."""
        if generation != self._scan_generation:
            _logger.debug(
                "PathSearchModal: discarding stale scan (gen %d != %d)",
                generation,
                self._scan_generation,
            )
            return
        self._load_paths(results)
        # Update cache using the key captured at scan start.
        if cache_key:
            ck = (self._workspace_path, cache_key)
            PathSearchModal._cache[ck] = tuple(self._all_paths)
            PathSearchModal._cache_dirty.discard(ck)
            _logger.debug(
                "PathSearchModal: cache updated (%s), %d paths",
                cache_key,
                len(self._all_paths),
            )

    def _on_scan_complete(self, generation: int) -> None:
        """Handle scan completion: hide spinner and refresh display."""
        if generation != self._scan_generation:
            return
        self._set_spinner_visible(False)
        self._refresh_display()

    @on(Checkbox.Changed, "#path-search-gitignore")
    def _on_gitignore_toggled(self, event: Checkbox.Changed) -> None:
        """Switch between filtered/unfiltered scan func on gitignore toggle."""
        if event.value:
            self._scan_func = self._filtered_scan_func
            self._cache_key_str = self._filtered_cache_key
        elif self._unfiltered_scan_func is not None:
            self._scan_func = self._unfiltered_scan_func
            self._cache_key_str = self._unfiltered_cache_key
        else:
            return
        self._load_or_scan()

    def _refresh_display(self) -> None:
        """Update the option list based on the current query."""
        from textual.css.query import NoMatches

        try:
            query = self.query_one("#path-search-input", Input).value
        except NoMatches:
            return
        if not query:
            self._show_discovery()
        else:
            self._trigger_search(query)

    def _display_path(self, path: Path) -> str:
        """Display path relative to workspace if possible."""
        try:
            return str(path.relative_to(self._workspace_path))
        except ValueError:
            return str(path)

    def _show_discovery(self) -> None:
        """Show all paths (up to limit) when query is empty."""
        self._search_generation += 1
        option_list = self.query_one("#path-search-results", OptionList)
        n = min(_MAX_DISCOVERY, len(self._all_paths))
        self._result_paths = self._all_paths[:n]
        option_list.set_options(self._display_strings[:n])
        self._update_results_visibility()

    def _trigger_search(self, query: str) -> None:
        """Increment generation and dispatch search (main thread only)."""
        self._search_generation += 1
        self._do_search(query, self._search_generation)

    @on(Input.Changed, "#path-search-input")
    def _on_input_changed(self, event: Input.Changed) -> None:
        if not event.value:
            self._show_discovery()
        else:
            self._trigger_search(event.value)

    @on(Input.Submitted, "#path-search-input")
    def _on_input_submitted(self, event: Input.Submitted) -> None:
        """Select the highlighted (or first) result when Enter is pressed."""
        ol = self.query_one("#path-search-results", OptionList)
        idx = ol.highlighted
        if idx is None:
            idx = 0
        if idx < len(self._result_paths):
            self.dismiss(self._result_paths[idx])

    @work(thread=True, exclusive=True, group="path_search_match")
    def _do_search(self, query: str, generation: int) -> None:
        """Run fuzzy matching in a background thread."""
        # Snapshot references for thread safety.
        paths = self._all_paths
        displays = self._display_strings

        if len(paths) > _RAPIDFUZZ_THRESHOLD:
            self._do_search_rapidfuzz(query, generation, paths, displays)
        else:
            self._do_search_textual(query, generation, paths, displays)

    def _do_search_textual(
        self,
        query: str,
        generation: int,
        paths: list[Path],
        displays: list[str],
    ) -> None:
        """Fuzzy search using Textual Matcher (for small candidate lists)."""
        worker = get_current_worker()
        matcher = Matcher(query)
        scored: list[tuple[float, str, Path]] = []
        for i, path in enumerate(paths):
            display = displays[i] if i < len(displays) else str(path)
            score = matcher.match(display)
            if score > 0:
                scored.append((score, display, path))
        top = heapq.nlargest(_MAX_SEARCH_HITS, scored)
        highlighted = [
            (matcher.highlight(display), path) for _score, display, path in top
        ]
        if worker.is_cancelled:
            _logger.debug("textual search worker cancelled, skipping callback")
            return
        try:
            self.app.call_from_thread(
                self._apply_results, query, generation, highlighted
            )
        except RuntimeError as exc:
            if "loop" not in str(exc).lower() and "closed" not in str(exc).lower():
                raise
            _logger.debug("call_from_thread suppressed (app exiting): %s", exc)

    def _do_search_rapidfuzz(
        self,
        query: str,
        generation: int,
        paths: list[Path],
        displays: list[str],
    ) -> None:
        """Fuzzy search using rapidfuzz (for large candidate lists >5000)."""
        from rapidfuzz import fuzz, process

        worker = get_current_worker()
        try:
            self.app.call_from_thread(self._set_spinner_visible, True)
        except RuntimeError as exc:
            if "loop" not in str(exc).lower() and "closed" not in str(exc).lower():
                raise
            _logger.debug("call_from_thread suppressed (app exiting): %s", exc)
            return
        try:
            results = process.extract(
                query,
                displays,
                scorer=fuzz.partial_ratio,
                limit=_MAX_SEARCH_HITS * 5,
                score_cutoff=50,
            )
            adjusted: list[tuple[float, str, Path]] = [
                (_adjust_score_for_path(score, choice, query), choice, paths[idx])
                for choice, score, idx in results
            ]
            adjusted.sort(key=lambda t: t[0], reverse=True)
            top = adjusted[:_MAX_SEARCH_HITS]
            # Highlight only the final results using Textual Matcher.
            matcher = Matcher(query)
            highlighted = [
                (matcher.highlight(display), path) for _score, display, path in top
            ]
        finally:
            # Only hide spinner if this search is still current; a newer
            # scan may have started and re-shown the spinner.
            if not worker.is_cancelled and generation == self._search_generation:
                try:
                    self.app.call_from_thread(self._set_spinner_visible, False)
                except RuntimeError as exc:
                    if (
                        "loop" not in str(exc).lower()
                        and "closed" not in str(exc).lower()
                    ):
                        raise
                    _logger.debug("call_from_thread suppressed (app exiting): %s", exc)
        if worker.is_cancelled:
            _logger.debug("rapidfuzz search worker cancelled, skipping callback")
            return
        try:
            self.app.call_from_thread(
                self._apply_results, query, generation, highlighted
            )
        except RuntimeError as exc:
            if "loop" not in str(exc).lower() and "closed" not in str(exc).lower():
                raise
            _logger.debug("call_from_thread suppressed (app exiting): %s", exc)

    def _apply_results(
        self,
        query: str,
        generation: int,
        results: list[tuple[str | Content, Path]],
    ) -> None:
        """Apply search results on the main thread. Discards stale results."""
        from textual.css.query import NoMatches

        if generation != self._search_generation:
            _logger.debug(
                "PathSearchModal: discarding stale results (gen %d != %d)",
                generation,
                self._search_generation,
            )
            return
        try:
            current = self.query_one("#path-search-input", Input).value
        except NoMatches:
            return
        if current != query:
            return
        option_list = self.query_one("#path-search-results", OptionList)
        self._result_paths = [path for _, path in results]
        option_list.set_options([highlighted for highlighted, _ in results])
        self._update_results_visibility()

    @on(OptionList.OptionSelected, "#path-search-results")
    def _on_selected(self, event: OptionList.OptionSelected) -> None:
        idx = event.option_list.highlighted
        if idx is not None and idx < len(self._result_paths):
            self.dismiss(self._result_paths[idx])

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def _proxy_option_list_action(self, action: str) -> None:
        """Forward a navigation action to the results OptionList."""
        ol = self.query_one("#path-search-results", OptionList)
        if ol.option_count > 0:
            self._ensure_results_visible()
            getattr(ol, f"action_{action}")()

    def action_cursor_down(self) -> None:
        self._proxy_option_list_action("cursor_down")

    def action_cursor_up(self) -> None:
        self._proxy_option_list_action("cursor_up")

    def action_page_down(self) -> None:
        self._proxy_option_list_action("page_down")

    def action_page_up(self) -> None:
        self._proxy_option_list_action("page_up")

    def _ensure_results_visible(self) -> None:
        """Show results list and adjust input bar border."""
        ol = self.query_one("#path-search-results", OptionList)
        if not ol.has_class("--visible"):
            ol.add_class("--visible")
            self.query_one("#path-search-input-bar").add_class("--has-results")

    def _update_results_visibility(self) -> None:
        """Toggle results list visibility based on option count."""
        ol = self.query_one("#path-search-results", OptionList)
        has_items = ol.option_count > 0
        ol.set_class(has_items, "--visible")
        self.query_one("#path-search-input-bar").set_class(has_items, "--has-results")

    async def _on_click(self, event: Click) -> None:
        """Dismiss when clicking the background overlay."""
        if self.get_widget_at(event.screen_x, event.screen_y)[0] is self:
            self.dismiss(None)
