from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    Label,
)


@dataclass
class SaveAsModalResult:
    is_cancelled: bool
    file_path: str | None


class SaveAsModalScreen(ModalScreen[SaveAsModalResult]):
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
    def save(self) -> None:
        self.dismiss(
            SaveAsModalResult(is_cancelled=False, file_path=self.query_one(Input).value)
        )

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        self.dismiss(SaveAsModalResult(is_cancelled=True, file_path=None))


@dataclass
class UnsavedChangeModalResult:
    is_cancelled: bool
    should_save: bool | None


class UnsavedChangeModalScreen(ModalScreen[UnsavedChangeModalResult]):
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
    def save(self) -> None:
        self.dismiss(UnsavedChangeModalResult(is_cancelled=False, should_save=True))

    @on(Button.Pressed, "#dont_save")
    def dont_save(self) -> None:
        self.dismiss(UnsavedChangeModalResult(is_cancelled=False, should_save=False))

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        self.dismiss(UnsavedChangeModalResult(is_cancelled=True, should_save=None))


@dataclass
class UnsavedChangeQuitModalResult:
    should_quit: bool


class UnsavedChangeQuitModalScreen(ModalScreen[UnsavedChangeQuitModalResult]):
    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Do you want to quit without saving?", id="title"),
            Label("If you don't save, changes will be lost.", id="message"),
            Button("Yes", variant="primary", id="yes"),
            Button("No", variant="default", id="no"),
            id="dialog",
        )

    @on(Button.Pressed, "#yes")
    def yes(self) -> None:
        self.dismiss(UnsavedChangeQuitModalResult(should_quit=True))

    @on(Button.Pressed, "#no")
    def no(self) -> None:
        self.dismiss(UnsavedChangeQuitModalResult(should_quit=False))


@dataclass
class DeleteFileModalResult:
    is_cancelled: bool
    should_delete: bool


class DeleteFileModalScreen(ModalScreen[DeleteFileModalResult]):
    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Are you sure you want to delete this file?", id="title"),
            Button("Delete", variant="warning", id="delete"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Button.Pressed, "#delete")
    def delete(self) -> None:
        self.dismiss(DeleteFileModalResult(is_cancelled=False, should_delete=True))

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        self.dismiss(DeleteFileModalResult(is_cancelled=True, should_delete=False))
