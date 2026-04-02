"""Inline find/replace bar widget (VS Code style)."""

from __future__ import annotations

import contextlib

from rich.cells import cell_len
from textual import events, on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, Checkbox, Input

# Full and compact (icon-only) label variants for each button.
# Mirrors the _BTN_LABELS pattern in workspace_search.py.
_BTN_LABELS = {
    "prev_match": ("↑ Prev", "↑"),
    "next_match": ("↓ Next", "↓"),
    "select_all_btn": ("Select All", "All"),
    "replace_btn": ("↪ Replace", "↪"),
    "replace_all_btn": ("🔄 Replace All", "🔄"),
}

_BTN_PADDING = 2  # Button left + right padding (1 cell each side)
_BTN_MIN_ICON_WIDTH = 5  # Minimum width for icon-only buttons

# Precomputed min-width for each label variant: {btn_id: (full_width, icon_width)}
_BTN_MIN_WIDTHS = {
    btn_id: (
        cell_len(full) + _BTN_PADDING,
        max(cell_len(icon) + _BTN_PADDING, _BTN_MIN_ICON_WIDTH),
    )
    for btn_id, (full, icon) in _BTN_LABELS.items()
}

# Only show full labels when the bar is very wide.
_COMPACT_THRESHOLD = 120

_REPLACE_PLACEHOLDER = "Replace with..."
_REPLACE_PLACEHOLDER_REGEX = "Replace with... (\\1 for groups)"

_TOOLTIPS = {
    "prev_match": "Previous Match (Shift+Enter)",
    "next_match": "Next Match (Enter)",
    "select_all_btn": "Select All Matches",
    "replace_btn": "Replace",
    "replace_all_btn": "Replace All",
    "close_btn": "Close (Escape)",
}


class FindReplaceBar(Horizontal):
    """Inline find/replace bar docked to the top of the CodeEditor."""

    replace_mode: reactive[bool] = reactive(False, init=False)
    _compact: bool | None = None

    class FindNext(Message):
        """Emitted when the user requests the next match."""

        def __init__(self, query: str, use_regex: bool, case_sensitive: bool) -> None:
            super().__init__()
            self.query = query
            self.use_regex = use_regex
            self.case_sensitive = case_sensitive

    class FindPrevious(Message):
        """Emitted when the user requests the previous match."""

        def __init__(self, query: str, use_regex: bool, case_sensitive: bool) -> None:
            super().__init__()
            self.query = query
            self.use_regex = use_regex
            self.case_sensitive = case_sensitive

    class ReplaceCurrent(Message):
        """Emitted when the user requests a single replacement."""

        def __init__(
            self, query: str, replacement: str, use_regex: bool, case_sensitive: bool
        ) -> None:
            super().__init__()
            self.query = query
            self.replacement = replacement
            self.use_regex = use_regex
            self.case_sensitive = case_sensitive

    class ReplaceAll(Message):
        """Emitted when the user requests replace-all."""

        def __init__(
            self, query: str, replacement: str, use_regex: bool, case_sensitive: bool
        ) -> None:
            super().__init__()
            self.query = query
            self.replacement = replacement
            self.use_regex = use_regex
            self.case_sensitive = case_sensitive

    class SelectAll(Message):
        """Emitted when the user requests select-all-matches."""

        def __init__(self, query: str, use_regex: bool, case_sensitive: bool) -> None:
            super().__init__()
            self.query = query
            self.use_regex = use_regex
            self.case_sensitive = case_sensitive

    class Closed(Message):
        """Emitted when the bar is closed."""

    def compose(self) -> ComposeResult:
        with Horizontal(id="find_row"):
            yield Input(placeholder="Find...", id="find_input")
            yield Checkbox(".*", id="use_regex", value=False)
            yield Checkbox("Aa", id="case_sensitive", value=True)
            yield Button(_BTN_LABELS["prev_match"][0], id="prev_match")
            yield Button(_BTN_LABELS["next_match"][0], id="next_match")
            yield Button(
                _BTN_LABELS["select_all_btn"][0],
                id="select_all_btn",
                variant="primary",
            )
            yield Button("✕", id="close_btn")
        with Horizontal(id="replace_row"):
            yield Input(placeholder=_REPLACE_PLACEHOLDER, id="replace_input")
            yield Button(
                _BTN_LABELS["replace_btn"][0], id="replace_btn", variant="primary"
            )
            yield Button(
                _BTN_LABELS["replace_all_btn"][0],
                id="replace_all_btn",
                variant="warning",
            )

    def on_mount(self) -> None:
        for btn_id, tooltip in _TOOLTIPS.items():
            with contextlib.suppress(NoMatches):
                self.query_one(f"#{btn_id}", Button).tooltip = tooltip

    def watch_replace_mode(self, value: bool) -> None:
        self.query_one("#replace_row").display = value

    # ── Responsive labels ──────────────────────────────────────────────────────

    def update_button_labels(self, *, compact: bool) -> None:
        """Switch button labels between icon+text and icon-only."""
        idx = 1 if compact else 0
        for btn_id, labels in _BTN_LABELS.items():
            try:
                btn = self.query_one(f"#{btn_id}", Button)
                btn.label = labels[idx]
                btn.styles.min_width = _BTN_MIN_WIDTHS[btn_id][idx]
            except NoMatches:
                pass  # replace row buttons may not be mounted yet

    def _refresh_labels(self) -> None:
        """Apply compact/full labels based on current width."""
        if self.size.width > 0:
            compact = self.size.width < _COMPACT_THRESHOLD
            self._compact = compact
            self.update_button_labels(compact=compact)

    def on_resize(self, event: events.Resize) -> None:
        """Update button labels based on bar width."""
        compact = event.size.width < _COMPACT_THRESHOLD
        if compact != self._compact:
            self._compact = compact
            self.update_button_labels(compact=compact)

    def show_find(self) -> None:
        """Show the bar in find mode and focus the find input."""
        self.replace_mode = False
        self.display = True
        self.query_one("#find_input", Input).focus()
        self.call_after_refresh(self._refresh_labels)

    def show_replace(self) -> None:
        """Show the bar in replace mode (replace row visible) and focus find input."""
        self.replace_mode = True
        self.display = True
        self.query_one("#find_input", Input).focus()
        self.call_after_refresh(self._refresh_labels)

    def _get_query(self) -> str:
        return self.query_one("#find_input", Input).value

    def _get_replacement(self) -> str:
        return self.query_one("#replace_input", Input).value

    def _get_use_regex(self) -> bool:
        return bool(self.query_one("#use_regex", Checkbox).value)

    def _get_case_sensitive(self) -> bool:
        """Return effective case_sensitive value.

        When regex is on, the user controls case via the pattern itself (e.g. (?i)),
        so we always return True in that case to avoid double-applying IGNORECASE.
        """
        if self._get_use_regex():
            return True
        return bool(self.query_one("#case_sensitive", Checkbox).value)

    @on(Checkbox.Changed, "#use_regex")
    def _on_regex_changed(self, event: Checkbox.Changed) -> None:
        """Disable case_sensitive checkbox when regex is on."""
        self.query_one("#case_sensitive", Checkbox).disabled = event.value
        self.query_one("#replace_input", Input).placeholder = (
            _REPLACE_PLACEHOLDER_REGEX if event.value else _REPLACE_PLACEHOLDER
        )

    @on(Button.Pressed, "#next_match")
    def _on_find_next(self) -> None:
        self.post_message(
            FindReplaceBar.FindNext(
                self._get_query(), self._get_use_regex(), self._get_case_sensitive()
            )
        )
        # Return focus to input so the button can be clicked again
        self.query_one("#find_input", Input).focus()

    @on(Button.Pressed, "#prev_match")
    def _on_find_previous(self) -> None:
        self.post_message(
            FindReplaceBar.FindPrevious(
                self._get_query(), self._get_use_regex(), self._get_case_sensitive()
            )
        )
        self.query_one("#find_input", Input).focus()

    @on(Input.Submitted, "#find_input")
    def _on_find_input_submitted(self) -> None:
        """Enter in find input → find next."""
        self._on_find_next()

    @on(Button.Pressed, "#select_all_btn")
    def _on_select_all(self) -> None:
        self.post_message(
            FindReplaceBar.SelectAll(
                self._get_query(), self._get_use_regex(), self._get_case_sensitive()
            )
        )

    @on(Input.Submitted, "#replace_input")
    @on(Button.Pressed, "#replace_btn")
    def _on_replace_current(self) -> None:
        self.post_message(
            FindReplaceBar.ReplaceCurrent(
                self._get_query(),
                self._get_replacement(),
                self._get_use_regex(),
                self._get_case_sensitive(),
            )
        )

    @on(Button.Pressed, "#replace_all_btn")
    def _on_replace_all(self) -> None:
        self.post_message(
            FindReplaceBar.ReplaceAll(
                self._get_query(),
                self._get_replacement(),
                self._get_use_regex(),
                self._get_case_sensitive(),
            )
        )

    @on(Button.Pressed, "#close_btn")
    def _on_close(self) -> None:
        self.display = False
        self.post_message(FindReplaceBar.Closed())

    def on_key(self, event) -> None:
        if event.key == "shift+enter":
            event.stop()
            event.prevent_default()
            self._on_find_previous()
        elif event.key == "escape":
            event.stop()
            self.display = False
            self.post_message(FindReplaceBar.Closed())
