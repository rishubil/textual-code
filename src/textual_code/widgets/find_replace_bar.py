"""Inline find/replace bar widget (VS Code style)."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, Checkbox, Input


class FindReplaceBar(Horizontal):
    """Inline find/replace bar docked to the top of the CodeEditor."""

    replace_mode: reactive[bool] = reactive(False, init=False)

    class FindNext(Message):
        """Emitted when the user requests the next match."""

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
            yield Button("↓ Next", id="next_match")
            yield Button("Select All", id="select_all_btn")
            yield Button("✕", id="close_btn")
        with Horizontal(id="replace_row"):
            yield Input(placeholder="Replace with...", id="replace_input")
            yield Button("Replace", id="replace_btn")
            yield Button("Replace All", id="replace_all_btn")

    def watch_replace_mode(self, value: bool) -> None:
        self.query_one("#replace_row").display = value

    def show_find(self) -> None:
        """Show the bar in find mode and focus the find input."""
        self.replace_mode = False
        self.display = True
        self.query_one("#find_input", Input).focus()

    def show_replace(self) -> None:
        """Show the bar in replace mode (replace row visible) and focus find input."""
        self.replace_mode = True
        self.display = True
        self.query_one("#find_input", Input).focus()

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

    @on(Input.Submitted, "#find_input")
    @on(Button.Pressed, "#next_match")
    def _on_find_next(self) -> None:
        self.post_message(
            FindReplaceBar.FindNext(
                self._get_query(), self._get_use_regex(), self._get_case_sensitive()
            )
        )
        # Return focus to input so the button can be clicked again
        self.query_one("#find_input", Input).focus()

    @on(Button.Pressed, "#select_all_btn")
    def _on_select_all(self) -> None:
        self.post_message(
            FindReplaceBar.SelectAll(
                self._get_query(), self._get_use_regex(), self._get_case_sensitive()
            )
        )

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
        if event.key == "escape":
            event.stop()
            self.display = False
            self.post_message(FindReplaceBar.Closed())
