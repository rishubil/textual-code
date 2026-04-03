from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Label,
    Select,
)

AVAILABLE_SYNTAX_THEMES = ["monokai", "dracula", "github_light", "vscode_dark", "css"]


@dataclass
class ChangeSyntaxThemeModalResult:
    """
    The result of the Change Syntax Theme modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # The selected theme, or None if cancelled.
    theme: str | None
    # The save level: "user" or "project".
    save_level: str = "user"


class ChangeSyntaxThemeModalScreen(ModalScreen[ChangeSyntaxThemeModalResult]):
    """
    Modal dialog for selecting the syntax highlighting theme.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, current_theme: str = "monokai") -> None:
        super().__init__()
        self._current_theme = current_theme

    def compose(self) -> ComposeResult:
        options = [(t, t) for t in AVAILABLE_SYNTAX_THEMES]
        yield Grid(
            Label("Syntax Highlighting Theme", id="title"),
            Select(options=options, value=self._current_theme, id="theme"),
            Select(
                options=[
                    ("User (~/.config)", "user"),
                    ("Project (.textual-code.toml)", "project"),
                ],
                value="user",
                id="save_level",
            ),
            Button("Apply", variant="primary", id="apply"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Select.Changed, "#theme")
    def _on_theme_changed(self, event: Select.Changed) -> None:
        """Live-preview the selected syntax theme on all open editors."""
        if event.value is Select.BLANK or str(event.value) == self._current_theme:
            return
        from textual_code.widgets.code_editor import CodeEditor

        for editor in self.app.query(CodeEditor):
            editor.syntax_theme = str(event.value)

    @on(Button.Pressed, "#apply")
    def on_apply(self) -> None:
        value = self.query_one("#theme", Select).value
        theme = str(value) if value is not Select.BLANK else self._current_theme
        save_level = str(self.query_one("#save_level", Select).value)
        self.dismiss(
            ChangeSyntaxThemeModalResult(
                is_cancelled=False, theme=theme, save_level=save_level
            )
        )

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        from textual_code.widgets.code_editor import CodeEditor

        for editor in self.app.query(CodeEditor):
            editor.syntax_theme = self._current_theme
        self.dismiss(ChangeSyntaxThemeModalResult(is_cancelled=True, theme=None))


@dataclass
class ChangeWordWrapModalResult:
    """
    The result of the Change Word Wrap modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # The selected word wrap value, or None if cancelled.
    word_wrap: bool | None
    # The save level: "user" or "project".
    save_level: str = "user"


class ChangeWordWrapModalScreen(ModalScreen[ChangeWordWrapModalResult]):
    """
    Modal dialog for setting the default word wrap setting.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, current_word_wrap: bool = True) -> None:
        super().__init__()
        self._current_word_wrap = current_word_wrap

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Default Word Wrap", id="title"),
            Select(
                options=[("On", "on"), ("Off", "off")],
                value="on" if self._current_word_wrap else "off",
                id="word_wrap",
            ),
            Select(
                options=[
                    ("User (~/.config)", "user"),
                    ("Project (.textual-code.toml)", "project"),
                ],
                value="user",
                id="save_level",
            ),
            Button("Apply", variant="primary", id="apply"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Button.Pressed, "#apply")
    def on_apply(self) -> None:
        value = self.query_one("#word_wrap", Select).value
        word_wrap = value != "off"
        save_level = str(self.query_one("#save_level", Select).value)
        self.dismiss(
            ChangeWordWrapModalResult(
                is_cancelled=False, word_wrap=word_wrap, save_level=save_level
            )
        )

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(ChangeWordWrapModalResult(is_cancelled=True, word_wrap=None))


@dataclass
class ChangeUIThemeModalResult:
    """
    The result of the Change UI Theme modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # The selected theme, or None if cancelled.
    theme: str | None
    # The save level: "user" or "project".
    save_level: str = "user"


class ChangeUIThemeModalScreen(ModalScreen[ChangeUIThemeModalResult]):
    """
    Modal dialog for selecting the UI theme.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, current_theme: str = "textual-dark") -> None:
        super().__init__()
        self._current_theme = current_theme

    def compose(self) -> ComposeResult:
        options = [(t, t) for t in sorted(self.app.available_themes.keys())]
        yield Grid(
            Label("UI Theme", id="title"),
            Select(options=options, value=self._current_theme, id="theme"),
            Select(
                options=[
                    ("User (~/.config)", "user"),
                    ("Project (.textual-code.toml)", "project"),
                ],
                value="user",
                id="save_level",
            ),
            Button("Apply", variant="primary", id="apply"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Select.Changed, "#theme")
    def _on_theme_changed(self, event: Select.Changed) -> None:
        """Live-preview the selected UI theme."""
        if event.value is Select.BLANK or str(event.value) == self._current_theme:
            return
        self.app.theme = str(event.value)

    @on(Button.Pressed, "#apply")
    def on_apply(self) -> None:
        value = self.query_one("#theme", Select).value
        theme = str(value) if value is not Select.BLANK else self._current_theme
        save_level = str(self.query_one("#save_level", Select).value)
        self.dismiss(
            ChangeUIThemeModalResult(
                is_cancelled=False, theme=theme, save_level=save_level
            )
        )

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.app.theme = self._current_theme
        self.dismiss(ChangeUIThemeModalResult(is_cancelled=True, theme=None))
