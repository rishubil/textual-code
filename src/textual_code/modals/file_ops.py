from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    Label,
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
    """Modal dialog for saving a file to a specific path.

    Also used for "Save Screenshot" via *title* / *default_path* overrides.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, title: str = "Save As", default_path: str = "") -> None:
        super().__init__()
        self._modal_title = title
        self._default_path = default_path

    def compose(self) -> ComposeResult:
        if self._default_path:
            path_input = Input(value=self._default_path, id="path")
        else:
            path_input = Input(placeholder="Enter the file path", id="path")
        yield Grid(
            Label(self._modal_title, id="title"),
            path_input,
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
    def action_cancel(self) -> None:
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
class RenameModalResult:
    """
    The result of the Rename modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # The new name, or None if the dialog was cancelled.
    new_name: str | None


class RenameModalScreen(ModalScreen[RenameModalResult]):
    """
    Modal dialog for renaming a file or directory.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, current_name: str) -> None:
        super().__init__()
        self.current_name = current_name

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Rename", id="title"),
            Input(value=self.current_name, id="new_name"),
            Button("Rename", variant="primary", id="rename"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    def on_mount(self) -> None:
        from textual.widgets._input import Selection

        inp = self.query_one(Input)
        dot_pos = self.current_name.rfind(".")
        if dot_pos > 0:
            inp.selection = Selection(0, dot_pos)
        else:
            inp.selection = Selection(0, len(self.current_name))

    @on(Input.Submitted, "#new_name")
    @on(Button.Pressed, "#rename")
    def on_rename(self) -> None:
        self.dismiss(
            RenameModalResult(is_cancelled=False, new_name=self.query_one(Input).value)
        )

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(RenameModalResult(is_cancelled=True, new_name=None))


@dataclass
class OverwriteConfirmModalResult:
    """
    The result of the Overwrite Confirm modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # Whether to overwrite the file. None if cancelled.
    should_overwrite: bool | None


class OverwriteConfirmModalScreen(ModalScreen[OverwriteConfirmModalResult]):
    """Confirm overwriting a file that was modified externally."""

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("File changed externally", id="title"),
            Label(
                "The file was modified externally. Overwrite with your changes?",
                id="message",
            ),
            Button("Overwrite", variant="warning", id="overwrite"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Button.Pressed, "#overwrite")
    def on_overwrite(self) -> None:
        self.dismiss(
            OverwriteConfirmModalResult(is_cancelled=False, should_overwrite=True)
        )

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(
            OverwriteConfirmModalResult(is_cancelled=True, should_overwrite=None)
        )


@dataclass
class DiscardAndReloadModalResult:
    """
    The result of the Discard and Reload modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # Whether to reload the file. None if cancelled.
    should_reload: bool | None


class DiscardAndReloadModalScreen(ModalScreen[DiscardAndReloadModalResult]):
    """Confirm discarding unsaved changes and reloading from disk."""

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Unsaved changes", id="title"),
            Label(
                "You have unsaved changes. Discard and reload from disk?",
                id="message",
            ),
            Button("Discard & Reload", variant="warning", id="reload"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Button.Pressed, "#reload")
    def on_reload(self) -> None:
        self.dismiss(
            DiscardAndReloadModalResult(is_cancelled=False, should_reload=True)
        )

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(DiscardAndReloadModalResult(is_cancelled=True, should_reload=None))


def _format_file_size(size: int) -> str:
    """Format a file size in bytes to a human-readable string."""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.1f} GB"


@dataclass
class LargeFileConfirmModalResult:
    """Result of the large file confirmation dialog."""

    action: Literal["open", "open_optimized", "cancel"]


class LargeFileConfirmModalScreen(ModalScreen[LargeFileConfirmModalResult]):
    """Confirmation dialog shown before opening a large or slow file."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(
        self,
        filename: str,
        file_size: int,
        *,
        reason: Literal["large_file", "timeout"] = "large_file",
    ) -> None:
        super().__init__()
        self._filename = filename
        self._file_size = file_size
        self._reason = reason

    def compose(self) -> ComposeResult:
        if self._reason == "timeout":
            title_text = "Slow file"
            msg_text = (
                f"Opening {self._filename} is taking too long. "
                "It may slow down the editor."
            )
        else:
            title_text = "Large file"
            msg_text = (
                f"{self._filename} ({_format_file_size(self._file_size)}) "
                "may slow down the editor."
            )
        yield Grid(
            Label(title_text, id="title"),
            Label(msg_text, id="message"),
            Button("Open Anyway", variant="primary", id="open"),
            Button("Open (plain)", variant="warning", id="open_optimized"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Button.Pressed, "#open")
    def on_open(self) -> None:
        self.dismiss(LargeFileConfirmModalResult(action="open"))

    @on(Button.Pressed, "#open_optimized")
    def on_open_optimized(self) -> None:
        self.dismiss(LargeFileConfirmModalResult(action="open_optimized"))

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(LargeFileConfirmModalResult(action="cancel"))


@dataclass
class LargeDirWarningModalResult:
    """Result of the large directory warning dialog."""

    should_proceed: bool


class LargeDirWarningModalScreen(ModalScreen[LargeDirWarningModalResult]):
    """Warning dialog shown before operating on a large directory."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(
        self,
        dir_name: str,
        total_size: int,
        file_count: int,
        operation: str,
    ) -> None:
        super().__init__()
        self._dir_name = dir_name
        self._total_size = total_size
        self._file_count = file_count
        self._operation = operation

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Large directory", id="title"),
            Label(
                f"{self._operation} '{self._dir_name}' "
                f"({_format_file_size(self._total_size)}, "
                f"{self._file_count:,} files) may take a while.",
                id="message",
            ),
            Button("Continue", variant="warning", id="continue"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Button.Pressed, "#continue")
    def on_continue(self) -> None:
        self.dismiss(LargeDirWarningModalResult(should_proceed=True))

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(LargeDirWarningModalResult(should_proceed=False))
