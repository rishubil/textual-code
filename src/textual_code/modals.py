from dataclasses import dataclass
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    Select,
)


@dataclass
class SaveAsModalResult:
    """
    The result of the Save As modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # The file path to save to, or None if the dialog was cancelled.
    file_path: str | None


class SaveAsModalScreen(ModalScreen[SaveAsModalResult]):
    """
    Modal dialog for saving a file to a specific path.
    """

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Save As", id="title"),
            Input(placeholder="Enter the file path", id="path"),
            Button("Save", variant="primary", id="save"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Input.Submitted, "#path")
    @on(Button.Pressed, "#save")
    def on_save(self) -> None:
        self.dismiss(
            SaveAsModalResult(is_cancelled=False, file_path=self.query_one(Input).value)
        )

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(SaveAsModalResult(is_cancelled=True, file_path=None))


@dataclass
class UnsavedChangeModalResult:
    """
    The result of the Unsaved Change modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # Whether to save the changes. None if the dialog was cancelled.
    should_save: bool | None


class UnsavedChangeModalScreen(ModalScreen[UnsavedChangeModalResult]):
    """
    Modal dialog for handling unsaved changes.
    """

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Do you want to save the changes before closing?", id="title"),
            Label("If you don't save, changes will be lost.", id="message"),
            Button("Save", variant="primary", id="save"),
            Button("Don't save", variant="warning", id="dont_save"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Button.Pressed, "#save")
    def on_save(self) -> None:
        self.dismiss(UnsavedChangeModalResult(is_cancelled=False, should_save=True))

    @on(Button.Pressed, "#dont_save")
    def on_dont_save(self) -> None:
        self.dismiss(UnsavedChangeModalResult(is_cancelled=False, should_save=False))

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(UnsavedChangeModalResult(is_cancelled=True, should_save=None))


@dataclass
class UnsavedChangeQuitModalResult:
    """
    The result of the Unsaved Change Quit modal dialog.
    """

    # Whether to quit without saving.
    should_quit: bool


class UnsavedChangeQuitModalScreen(ModalScreen[UnsavedChangeQuitModalResult]):
    """
    Modal dialog for quitting without saving.
    """

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Do you want to quit without saving?", id="title"),
            Label("If you don't save, changes will be lost.", id="message"),
            Button("Quit", variant="warning", id="quit"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Button.Pressed, "#quit")
    def on_quit(self) -> None:
        self.dismiss(UnsavedChangeQuitModalResult(should_quit=True))

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(UnsavedChangeQuitModalResult(should_quit=False))


@dataclass
class DeleteFileModalResult:
    """
    The result of the Delete File modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # Whether to delete the file. None if the dialog was cancelled
    should_delete: bool


class DeleteFileModalScreen(ModalScreen[DeleteFileModalResult]):
    """
    Modal dialog for deleting a file.
    """

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path

    def compose(self) -> ComposeResult:
        if self.path.is_dir():
            title = "Permanently delete this directory and ALL its contents?"
        else:
            title = "Permanently delete this file?"
        yield Grid(
            Label(title, id="title"),
            Label(str(self.path), id="message"),
            Label("This action cannot be undone.", id="warning"),
            Button("Delete", variant="warning", id="delete"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Button.Pressed, "#delete")
    def on_delete(self) -> None:
        self.dismiss(DeleteFileModalResult(is_cancelled=False, should_delete=True))

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(DeleteFileModalResult(is_cancelled=True, should_delete=False))


@dataclass
class GotoLineModalResult:
    """
    The result of the Goto Line modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # The raw location string ("5" or "3:7"), or None if cancelled.
    value: str | None


class GotoLineModalScreen(ModalScreen[GotoLineModalResult]):
    """
    Modal dialog for jumping to a specific line and column.
    """

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Go to Line", id="title"),
            Input(placeholder="line or line:col (e.g. 5 or 3:7)", id="location"),
            Button("Goto", variant="primary", id="goto"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Input.Submitted, "#location")
    @on(Button.Pressed, "#goto")
    def on_goto(self) -> None:
        self.dismiss(
            GotoLineModalResult(is_cancelled=False, value=self.query_one(Input).value)
        )

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(GotoLineModalResult(is_cancelled=True, value=None))


@dataclass
class FindModalResult:
    """
    The result of the Find modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # The search query, or None if cancelled.
    query: str | None
    # Whether to use regex matching.
    use_regex: bool = False


class FindModalScreen(ModalScreen[FindModalResult]):
    """
    Modal dialog for finding text in the current file.
    """

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Find", id="title"),
            Input(placeholder="Search...", id="query"),
            Checkbox("Use regex", id="use_regex"),
            Button("Find", variant="primary", id="find"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Input.Submitted, "#query")
    @on(Button.Pressed, "#find")
    def on_find(self) -> None:
        self.dismiss(
            FindModalResult(
                is_cancelled=False,
                query=self.query_one(Input).value,
                use_regex=self.query_one("#use_regex", Checkbox).value,
            )
        )

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(FindModalResult(is_cancelled=True, query=None))


@dataclass
class ReplaceModalResult:
    """
    The result of the Replace modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # The action to perform: "replace" or "replace_all", or None if cancelled.
    action: str | None
    # The search query, or None if cancelled.
    find_query: str | None
    # The replacement text, or None if cancelled.
    replace_text: str | None
    # Whether to use regex matching.
    use_regex: bool = False


class ReplaceModalScreen(ModalScreen[ReplaceModalResult]):
    """
    Modal dialog for finding and replacing text in the current file.
    """

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Replace", id="title"),
            Input(placeholder="Find...", id="find_query"),
            Input(placeholder="Replace with...", id="replace_text"),
            Checkbox("Use regex", id="use_regex"),
            Button("Replace", variant="primary", id="replace"),
            Button("Replace All", variant="primary", id="replace_all"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Button.Pressed, "#replace")
    def on_replace(self) -> None:
        self.dismiss(
            ReplaceModalResult(
                is_cancelled=False,
                action="replace",
                find_query=self.query_one("#find_query", Input).value,
                replace_text=self.query_one("#replace_text", Input).value,
                use_regex=self.query_one("#use_regex", Checkbox).value,
            )
        )

    @on(Button.Pressed, "#replace_all")
    def on_replace_all(self) -> None:
        self.dismiss(
            ReplaceModalResult(
                is_cancelled=False,
                action="replace_all",
                find_query=self.query_one("#find_query", Input).value,
                replace_text=self.query_one("#replace_text", Input).value,
                use_regex=self.query_one("#use_regex", Checkbox).value,
            )
        )

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(
            ReplaceModalResult(
                is_cancelled=True, action=None, find_query=None, replace_text=None
            )
        )


@dataclass
class ChangeLanguageModalResult:
    """
    The result of the Change Language modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # The selected language, or None for plain (no syntax highlighting).
    language: str | None


class ChangeLanguageModalScreen(ModalScreen[ChangeLanguageModalResult]):
    """
    Modal dialog for changing the syntax highlighting language.
    """

    def __init__(self, languages: list[str], current_language: str | None) -> None:
        super().__init__()
        self._languages = languages
        self._current_language = current_language

    def compose(self) -> ComposeResult:
        options = [("plain", "plain")] + [(lang, lang) for lang in self._languages]
        initial = self._current_language if self._current_language else "plain"
        yield Grid(
            Label("Change Language", id="title"),
            Select(options=options, value=initial, id="language"),
            Button("Apply", variant="primary", id="apply"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Button.Pressed, "#apply")
    def on_apply(self) -> None:
        value = self.query_one(Select).value
        language = None if value == "plain" or value is Select.BLANK else str(value)
        self.dismiss(ChangeLanguageModalResult(is_cancelled=False, language=language))

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(ChangeLanguageModalResult(is_cancelled=True, language=None))
