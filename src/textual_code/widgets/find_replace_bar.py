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

        def __init__(self, query: str, use_regex: bool) -> None:
            super().__init__()
            self.query = query
            self.use_regex = use_regex

    class ReplaceCurrent(Message):
        """Emitted when the user requests a single replacement."""

        def __init__(self, query: str, replacement: str, use_regex: bool) -> None:
            super().__init__()
            self.query = query
            self.replacement = replacement
            self.use_regex = use_regex

    class ReplaceAll(Message):
        """Emitted when the user requests replace-all."""

        def __init__(self, query: str, replacement: str, use_regex: bool) -> None:
            super().__init__()
            self.query = query
            self.replacement = replacement
            self.use_regex = use_regex

    class Closed(Message):
        """Emitted when the bar is closed."""

    def compose(self) -> ComposeResult:
        with Horizontal(id="find_row"):
            yield Input(placeholder="Find...", id="find_input")
            yield Checkbox(".*", id="use_regex", value=False)
            yield Button("↓ Next", id="next_match")
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

    @on(Input.Submitted, "#find_input")
    @on(Button.Pressed, "#next_match")
    def _on_find_next(self) -> None:
        self.post_message(
            FindReplaceBar.FindNext(self._get_query(), self._get_use_regex())
        )
        # Return focus to input so the button can be clicked again
        self.query_one("#find_input", Input).focus()

    @on(Button.Pressed, "#replace_btn")
    def _on_replace_current(self) -> None:
        self.post_message(
            FindReplaceBar.ReplaceCurrent(
                self._get_query(), self._get_replacement(), self._get_use_regex()
            )
        )

    @on(Button.Pressed, "#replace_all_btn")
    def _on_replace_all(self) -> None:
        self.post_message(
            FindReplaceBar.ReplaceAll(
                self._get_query(), self._get_replacement(), self._get_use_regex()
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
