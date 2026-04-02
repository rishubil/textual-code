from __future__ import annotations

import heapq
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, cast

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.content import Content
from textual.events import Click, Key
from textual.fuzzy import Matcher
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Input,
    Label,
    ListItem,
    ListView,
    OptionList,
    Select,
)
from textual.worker import get_current_worker

if TYPE_CHECKING:
    from textual_code.app import TextualCode
    from textual_code.config import FooterOrders, ShortcutDisplayEntry
    from textual_code.search import FileDiffPreview


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

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

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
    def action_cancel(self) -> None:
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

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

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
    def action_cancel(self) -> None:
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

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

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
    def action_cancel(self) -> None:
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

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

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
    def action_cancel(self) -> None:
        self.dismiss(ChangeLanguageModalResult(is_cancelled=True, language=None))


@dataclass
class ChangeIndentModalResult:
    """
    The result of the Change Indentation modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # The indentation type: "spaces" or "tabs", or None if cancelled.
    indent_type: str | None
    # The indentation size: 2, 4, or 8, or None if cancelled.
    indent_size: int | None
    # The save level: "user" or "project".
    save_level: str = "user"


class ChangeIndentModalScreen(ModalScreen[ChangeIndentModalResult]):
    """
    Modal dialog for changing indentation style and size.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(
        self,
        current_indent_type: str = "spaces",
        current_indent_size: int = 4,
        show_save_level: bool = True,
    ) -> None:
        super().__init__()
        self._current_indent_type = current_indent_type
        self._current_indent_size = current_indent_size
        self._show_save_level = show_save_level

    def compose(self) -> ComposeResult:
        children: list[Widget] = [
            Label("Change Indentation", id="title"),
            Select(
                options=[("Spaces", "spaces"), ("Tabs", "tabs")],
                value=self._current_indent_type,
                id="indent_type",
            ),
            Input(
                value=str(self._current_indent_size),
                placeholder="e.g. 4",
                id="indent_size",
            ),
        ]
        if self._show_save_level:
            children.append(
                Select(
                    options=[
                        ("User (~/.config)", "user"),
                        ("Project (.textual-code.toml)", "project"),
                    ],
                    value="user",
                    id="save_level",
                )
            )
        children += [
            Button("Apply", variant="primary", id="apply"),
            Button("Cancel", variant="default", id="cancel"),
        ]
        yield Grid(*children, id="dialog")

    def on_mount(self) -> None:
        if not self._show_save_level:
            self.add_class("no-save-level")

    @on(Button.Pressed, "#apply")
    def on_apply(self) -> None:
        raw = self.query_one("#indent_size", Input).value.strip()
        try:
            indent_size = int(raw)
        except ValueError:
            self.notify("Indent size must be a positive integer.", severity="error")
            return
        if indent_size <= 0:
            self.notify("Indent size must be greater than 0.", severity="error")
            return
        indent_type = str(self.query_one("#indent_type", Select).value)
        save_level_widgets = self.query("#save_level")
        save_level = (
            str(save_level_widgets.first(Select).value)
            if save_level_widgets
            else "user"
        )
        self.dismiss(
            ChangeIndentModalResult(
                is_cancelled=False,
                indent_type=indent_type,
                indent_size=indent_size,
                save_level=save_level,
            )
        )

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(
            ChangeIndentModalResult(
                is_cancelled=True, indent_type=None, indent_size=None
            )
        )


@dataclass
class ChangeLineEndingModalResult:
    """
    The result of the Change Line Ending modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # The selected line ending: "lf", "crlf", or "cr", or None if cancelled.
    line_ending: str | None
    # The save level: "user" or "project".
    save_level: str = "user"


class ChangeLineEndingModalScreen(ModalScreen[ChangeLineEndingModalResult]):
    """
    Modal dialog for changing the line ending style.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(
        self, current_line_ending: str = "lf", show_save_level: bool = True
    ) -> None:
        super().__init__()
        self._current_line_ending = current_line_ending
        self._show_save_level = show_save_level

    def compose(self) -> ComposeResult:
        children: list[Widget] = [
            Label("Change Line Ending", id="title"),
            Select(
                options=[
                    ("LF (Unix/macOS)", "lf"),
                    ("CRLF (Windows)", "crlf"),
                    ("CR (Classic Mac)", "cr"),
                ],
                value=self._current_line_ending,
                id="line_ending",
            ),
        ]
        if self._show_save_level:
            children.append(
                Select(
                    options=[
                        ("User (~/.config)", "user"),
                        ("Project (.textual-code.toml)", "project"),
                    ],
                    value="user",
                    id="save_level",
                )
            )
        children += [
            Button("Apply", variant="primary", id="apply"),
            Button("Cancel", variant="default", id="cancel"),
        ]
        yield Grid(*children, id="dialog")

    def on_mount(self) -> None:
        if not self._show_save_level:
            self.add_class("no-save-level")

    @on(Button.Pressed, "#apply")
    def on_apply(self) -> None:
        value = str(self.query_one("#line_ending", Select).value)
        save_level_widgets = self.query("#save_level")
        save_level = (
            str(save_level_widgets.first(Select).value)
            if save_level_widgets
            else "user"
        )
        self.dismiss(
            ChangeLineEndingModalResult(
                is_cancelled=False, line_ending=value, save_level=save_level
            )
        )

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(ChangeLineEndingModalResult(is_cancelled=True, line_ending=None))


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


@dataclass
class SidebarResizeModalResult:
    """
    The result of the Sidebar Resize modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # The raw user input string, or None if cancelled.
    value: str | None


class SidebarResizeModalScreen(ModalScreen[SidebarResizeModalResult]):
    """
    Modal dialog for resizing the sidebar.
    Accepts: absolute ("30"), relative ("+5" or "-3"), or percentage ("30%").
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Resize Sidebar", id="title"),
            Input(placeholder="e.g. 30  or  +5  or  30%", id="value"),
            Button("Resize", variant="primary", id="submit"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Input.Submitted, "#value")
    @on(Button.Pressed, "#submit")
    def on_submit(self) -> None:
        self.dismiss(
            SidebarResizeModalResult(
                is_cancelled=False, value=self.query_one(Input).value
            )
        )

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(SidebarResizeModalResult(is_cancelled=True, value=None))


@dataclass
class SplitResizeModalResult:
    """
    The result of the Split Resize modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # The raw user input string, or None if cancelled.
    value: str | None


class SplitResizeModalScreen(ModalScreen[SplitResizeModalResult]):
    """
    Modal dialog for resizing the split view left panel.
    Accepts: absolute ("50"), relative ("+10" or "-5"), or percentage ("40%").
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Resize Split", id="title"),
            Input(placeholder="e.g. 50  or  +10  or  40%", id="value"),
            Button("Resize", variant="primary", id="submit"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Input.Submitted, "#value")
    @on(Button.Pressed, "#submit")
    def on_submit(self) -> None:
        self.dismiss(
            SplitResizeModalResult(
                is_cancelled=False, value=self.query_one(Input).value
            )
        )

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(SplitResizeModalResult(is_cancelled=True, value=None))


@dataclass
class ChangeEncodingModalResult:
    """
    The result of the Change Encoding modal dialog.
    """

    # Whether the dialog was cancelled.
    is_cancelled: bool
    # The selected encoding, or None if cancelled.
    encoding: str | None
    # The save level: "user" or "project".
    save_level: str = "user"


class ChangeEncodingModalScreen(ModalScreen[ChangeEncodingModalResult]):
    """
    Modal dialog for changing the file encoding.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(
        self, current_encoding: str = "utf-8", show_save_level: bool = True
    ) -> None:
        super().__init__()
        self._current_encoding = current_encoding
        self._show_save_level = show_save_level

    def compose(self) -> ComposeResult:
        children: list[Widget] = [
            Label("Change Encoding", id="title"),
            Select(
                options=[
                    # Unicode
                    ("UTF-8", "utf-8"),
                    ("UTF-8 BOM", "utf-8-sig"),
                    ("UTF-16", "utf-16"),
                    ("UTF-16 LE", "utf-16-le"),
                    ("UTF-16 BE", "utf-16-be"),
                    ("UTF-32", "utf-32"),
                    ("UTF-32 LE", "utf-32-le"),
                    ("UTF-32 BE", "utf-32-be"),
                    # Western European
                    ("Latin-1 (ISO-8859-1)", "latin-1"),
                    ("Windows-1252 (Western)", "cp1252"),
                    ("ISO-8859-15 (Western)", "iso-8859-15"),
                    # Central/Eastern European
                    ("Windows-1250 (Central European)", "cp1250"),
                    ("ISO-8859-2 (Central European)", "iso-8859-2"),
                    ("Windows-1257 (Baltic)", "cp1257"),
                    ("ISO-8859-13 (Baltic)", "iso-8859-13"),
                    # Cyrillic
                    ("Windows-1251 (Cyrillic)", "cp1251"),
                    ("ISO-8859-5 (Cyrillic)", "iso-8859-5"),
                    ("KOI8-R (Russian)", "koi8-r"),
                    ("KOI8-U (Ukrainian)", "koi8-u"),
                    # Greek
                    ("Windows-1253 (Greek)", "cp1253"),
                    ("ISO-8859-7 (Greek)", "iso-8859-7"),
                    # Turkish
                    ("Windows-1254 (Turkish)", "cp1254"),
                    ("ISO-8859-9 (Turkish)", "iso-8859-9"),
                    # Hebrew
                    ("Windows-1255 (Hebrew)", "cp1255"),
                    # Arabic
                    ("Windows-1256 (Arabic)", "cp1256"),
                    # Vietnamese
                    ("Windows-1258 (Vietnamese)", "cp1258"),
                    # Japanese
                    ("Shift-JIS (Japanese)", "shift_jis"),
                    ("EUC-JP (Japanese)", "euc_jp"),
                    # Chinese Simplified
                    ("GBK (Chinese Simplified)", "gbk"),
                    ("GB18030 (Chinese Simplified)", "gb18030"),
                    # Chinese Traditional
                    ("Big5 (Chinese Traditional)", "big5"),
                    # Korean
                    ("EUC-KR (Korean)", "euc_kr"),
                    # ASCII
                    ("ASCII", "ascii"),
                ],
                value=self._current_encoding,
                id="encoding",
            ),
        ]
        if self._show_save_level:
            children.append(
                Select(
                    options=[
                        ("User (~/.config)", "user"),
                        ("Project (.textual-code.toml)", "project"),
                    ],
                    value="user",
                    id="save_level",
                )
            )
        children += [
            Button("Apply", variant="primary", id="apply"),
            Button("Cancel", variant="default", id="cancel"),
        ]
        yield Grid(*children, id="dialog")

    def on_mount(self) -> None:
        if not self._show_save_level:
            self.add_class("no-save-level")

    @on(Button.Pressed, "#apply")
    def on_apply(self) -> None:
        value = str(self.query_one("#encoding", Select).value)
        save_level_widgets = self.query("#save_level")
        save_level = (
            str(save_level_widgets.first(Select).value)
            if save_level_widgets
            else "user"
        )
        self.dismiss(
            ChangeEncodingModalResult(
                is_cancelled=False, encoding=value, save_level=save_level
            )
        )

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(ChangeEncodingModalResult(is_cancelled=True, encoding=None))


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


# ---------------------------------------------------------------------------
# Keyboard shortcuts customization
# ---------------------------------------------------------------------------


@dataclass
class RebindResult:
    """Result returned by RebindKeyScreen."""

    is_cancelled: bool
    action_name: str | None
    new_key: str | None


class RebindKeyScreen(ModalScreen[RebindResult]):
    """Modal that captures a single key press as a new binding for an action."""

    DEFAULT_CSS = """
    RebindKeyScreen {
        align: center middle;
    }
    RebindKeyScreen #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1 1 1 3;
        padding: 0 1;
        width: 60;
        height: 14;
        border: thick $background 80%;
        background: $surface;
    }
    RebindKeyScreen #title {
        column-span: 2;
        height: 1fr;
        width: 1fr;
        content-align: center middle;
        text-style: bold;
    }
    RebindKeyScreen #current_row {
        column-span: 2;
        height: 1fr;
    }
    RebindKeyScreen #captured_key {
        column-span: 2;
        height: 1fr;
        content-align: center middle;
        text-style: bold;
    }
    """

    # Keys that are not capturable (reserved for UI control)
    _SKIP_KEYS = frozenset({"escape", "enter", "tab", "shift+tab"})

    def __init__(self, action_name: str, description: str, current_key: str) -> None:
        super().__init__()
        self._action = action_name
        self._description = description
        self._current_key = current_key
        self._captured: str | None = None

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(f"Rebind: {self._description}", id="title"),
            Label(f"Current key: {self._current_key}", id="current_row"),
            Label("Press new key combination...", id="captured_key"),
            Button("Apply", variant="primary", id="apply", disabled=True),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            self.dismiss(
                RebindResult(is_cancelled=True, action_name=None, new_key=None)
            )
            event.stop()
            return
        if event.key in self._SKIP_KEYS:
            return
        self._captured = event.key
        self.query_one("#captured_key", Label).update(event.key)
        self.query_one("#apply", Button).disabled = False
        event.stop()

    @on(Button.Pressed, "#apply")
    def on_apply(self) -> None:
        if self._captured:
            self.dismiss(
                RebindResult(
                    is_cancelled=False,
                    action_name=self._action,
                    new_key=self._captured,
                )
            )

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(RebindResult(is_cancelled=True, action_name=None, new_key=None))


@dataclass
class ShortcutSettingsResult:
    """Result from the ShortcutSettingsScreen dialog."""

    is_cancelled: bool
    action_name: str | None = None
    new_key: str | None = None
    palette_visible: bool | None = None


class ShortcutSettingsScreen(ModalScreen[ShortcutSettingsResult]):
    """Modal for configuring a single shortcut's display preferences."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    ShortcutSettingsScreen {
        align: center middle;
    }
    ShortcutSettingsScreen #dialog {
        padding: 1 2;
        width: 60;
        height: auto;
        max-height: 20;
        border: thick $background 80%;
        background: $surface;
    }
    ShortcutSettingsScreen #title {
        height: 1;
        width: 1fr;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }
    ShortcutSettingsScreen #current_key_label {
        height: 1;
        margin-bottom: 1;
    }
    ShortcutSettingsScreen #change_key {
        margin-bottom: 0;
        width: 100%;
    }
    ShortcutSettingsScreen #unbind {
        margin-bottom: 1;
        width: 100%;
    }
    ShortcutSettingsScreen .buttons {
        height: 3;
        margin-top: 1;
        layout: horizontal;
    }
    ShortcutSettingsScreen .buttons Button {
        width: 1fr;
        margin: 0 1;
    }
    """

    def __init__(
        self,
        action_name: str,
        description: str,
        current_key: str,
        palette_visible: bool = True,
    ) -> None:
        super().__init__()
        self._action = action_name
        self._description = description
        self._current_key = current_key
        self._palette_visible = palette_visible
        self._new_key: str | None = None

    def compose(self) -> ComposeResult:
        is_unbound = not self._current_key or self._current_key == "(none)"
        yield Vertical(
            Label(f"Shortcut Settings: {self._description}", id="title"),
            Label(f"Current key: {self._current_key}", id="current_key_label"),
            Button("Change Key...", variant="default", id="change_key"),
            Button(
                "Unbind",
                variant="warning",
                id="unbind",
                disabled=is_unbound,
            ),
            Checkbox(
                "Show in command palette", self._palette_visible, id="palette_visible"
            ),
            Horizontal(
                Button("Save", variant="primary", id="save"),
                Button("Cancel", variant="default", id="cancel"),
                classes="buttons",
            ),
            id="dialog",
        )

    @on(Button.Pressed, "#change_key")
    def on_change_key(self) -> None:
        self.app.push_screen(
            RebindKeyScreen(self._action, self._description, self._current_key),
            self._on_rebind,
        )

    def _on_rebind(self, result: RebindResult | None) -> None:
        if result and not result.is_cancelled and result.new_key:
            self._new_key = result.new_key
            self._current_key = result.new_key
            self.query_one("#current_key_label", Label).update(
                f"Current key: {result.new_key}"
            )

    @on(Button.Pressed, "#unbind")
    def on_unbind(self) -> None:
        self._new_key = ""
        self._current_key = "(none)"
        self.query_one("#current_key_label", Label).update("Current key: (none)")
        self.query_one("#unbind", Button).disabled = True

    @on(Button.Pressed, "#save")
    def on_save(self) -> None:
        palette_cb = self.query_one("#palette_visible", Checkbox)
        self.dismiss(
            ShortcutSettingsResult(
                is_cancelled=False,
                action_name=self._action,
                new_key=self._new_key,
                palette_visible=palette_cb.value,
            )
        )

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(ShortcutSettingsResult(is_cancelled=True))


@dataclass
class FooterConfigResult:
    """Result from the FooterConfigScreen dialog."""

    is_cancelled: bool
    order: list[str] | None = None
    area: str = "editor"


class FooterConfigScreen(ModalScreen[FooterConfigResult]):
    """Modal for configuring which shortcuts appear in the footer and their order."""

    DEFAULT_CSS = """
    FooterConfigScreen {
        align: center middle;
    }
    FooterConfigScreen #dialog {
        padding: 1 2;
        width: 70;
        height: 36;
        border: thick $background 80%;
        background: $surface;
    }
    FooterConfigScreen #title {
        height: 1;
        width: 1fr;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }
    FooterConfigScreen #hint {
        height: 1;
        color: $text-muted;
        margin-bottom: 1;
    }
    FooterConfigScreen #area_select {
        height: 3;
        margin-bottom: 1;
    }
    FooterConfigScreen #footer_list {
        height: 1fr;
    }
    FooterConfigScreen .action-buttons {
        height: 3;
        margin-top: 1;
        layout: horizontal;
    }
    FooterConfigScreen .action-buttons Button {
        width: 1fr;
        margin: 0 1;
    }
    FooterConfigScreen .confirm-buttons {
        height: 3;
        layout: horizontal;
    }
    FooterConfigScreen .confirm-buttons Button {
        width: 1fr;
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("space", "toggle_item", "Toggle", show=False),
        Binding("ctrl+up", "move_up", "Move up", show=False),
        Binding("ctrl+down", "move_down", "Move down", show=False),
    ]

    _AREA_LABELS: dict[str, str] = {
        "editor": "Editor",
        "explorer": "Explorer",
        "search": "Search",
        "image_preview": "Image Preview",
        "markdown_preview": "Markdown Preview",
    }

    def __init__(
        self,
        all_area_actions: dict[str, list[tuple[str, str, str, bool]]],
        footer_orders: FooterOrders,
        *,
        initial_area: str = "editor",
    ) -> None:
        super().__init__()
        self._all_area_actions = all_area_actions
        self._footer_orders = footer_orders
        self._current_area = initial_area
        # Per-area action lookup: area → {action_name: (name, desc, key)}
        self._area_action_info: dict[str, dict[str, tuple[str, str, str]]] = {}
        for area, actions in all_area_actions.items():
            self._area_action_info[area] = {a[0]: (a[0], a[1], a[2]) for a in actions}
        # Per-area items state cache
        self._area_items: dict[str, list[tuple[str, bool]]] = {}
        for area, actions in all_area_actions.items():
            self._area_items[area] = self._build_items(area, actions)
        self._items = self._area_items.get(initial_area, [])

    def _build_items(
        self,
        area: str,
        actions: list[tuple[str, str, str, bool]],
    ) -> list[tuple[str, bool]]:
        """Build the ordered (action_name, visible) list for an area."""
        current_order = self._footer_orders.for_area(area)
        if current_order is not None:
            action_set = {a[0] for a in actions}
            visible = set(current_order)
            items: list[tuple[str, bool]] = [
                (a, True) for a in current_order if a in action_set
            ]
            for action_name, _desc, _key, _show in actions:
                if action_name not in visible:
                    items.append((action_name, False))
            return items
        return [(a[0], a[3]) for a in actions]

    @property
    def _actions(self) -> dict[str, tuple[str, str, str]]:
        """Return action info for the current area."""
        return self._area_action_info.get(self._current_area, {})

    def _format_item_text(self, action_name: str, visible: bool) -> str:
        """Format the display text for a footer config list item."""
        info = self._actions.get(action_name)
        if info is None:
            return f" {'✓' if visible else '✗'}  {action_name}"
        _name, desc, key = info
        marker = "\u2713" if visible else "\u2717"
        return f" {marker}  {desc} ({key})"

    def compose(self) -> ComposeResult:
        from textual.widgets import Select

        area_options = [
            (label, area)
            for area, label in self._AREA_LABELS.items()
            if area in self._all_area_actions
        ]
        items = [
            ListItem(Label(self._format_item_text(a, v)), name=a)
            for a, v in self._items
        ]
        yield Vertical(
            Label("Configure Footer Shortcuts", id="title"),
            Select(area_options, value=self._current_area, id="area_select"),
            Label("Space: toggle, Ctrl+Up/Down: reorder", id="hint"),
            ListView(*items, id="footer_list"),
            Horizontal(
                Button("Move Up", variant="default", id="move_up"),
                Button("Move Down", variant="default", id="move_down"),
                Button("Toggle", variant="default", id="toggle"),
                classes="action-buttons",
            ),
            Horizontal(
                Button("Save", variant="primary", id="save"),
                Button("Cancel", variant="default", id="cancel"),
                classes="confirm-buttons",
            ),
            id="dialog",
        )

    @on(Select.Changed, "#area_select")
    def on_area_changed(self, event: Select.Changed) -> None:
        """Switch to a different area, preserving current state."""
        new_area = str(event.value)
        if new_area == self._current_area:
            return
        # Save current area state
        self._area_items[self._current_area] = list(self._items)
        self._current_area = new_area
        self._items = list(self._area_items.get(new_area, []))
        # Rebuild the list view
        list_view = self.query_one("#footer_list", ListView)
        list_view.clear()
        for action_name, visible in self._items:
            text = self._format_item_text(action_name, visible)
            list_view.append(ListItem(Label(text), name=action_name))

    def _update_item_label(self, idx: int) -> None:
        """Update the label of a single list item at the given index."""
        list_view = self.query_one("#footer_list", ListView)
        action_name, visible = self._items[idx]
        item = list_view.children[idx]
        item.query_one(Label).update(self._format_item_text(action_name, visible))

    def action_toggle_item(self) -> None:
        list_view = self.query_one("#footer_list", ListView)
        idx = list_view.index
        if idx is not None and 0 <= idx < len(self._items):
            action_name, visible = self._items[idx]
            self._items[idx] = (action_name, not visible)
            self._update_item_label(idx)

    def action_move_up(self) -> None:
        list_view = self.query_one("#footer_list", ListView)
        idx = list_view.index
        if idx is not None and idx > 0:
            self._items[idx], self._items[idx - 1] = (
                self._items[idx - 1],
                self._items[idx],
            )
            self._update_item_label(idx)
            self._update_item_label(idx - 1)
            list_view.index = idx - 1

    def action_move_down(self) -> None:
        list_view = self.query_one("#footer_list", ListView)
        idx = list_view.index
        if idx is not None and idx < len(self._items) - 1:
            self._items[idx], self._items[idx + 1] = (
                self._items[idx + 1],
                self._items[idx],
            )
            self._update_item_label(idx)
            self._update_item_label(idx + 1)
            list_view.index = idx + 1

    @on(Button.Pressed, "#move_up")
    def on_move_up_btn(self) -> None:
        self.action_move_up()

    @on(Button.Pressed, "#move_down")
    def on_move_down_btn(self) -> None:
        self.action_move_down()

    @on(Button.Pressed, "#toggle")
    def on_toggle_btn(self) -> None:
        self.action_toggle_item()

    @on(Button.Pressed, "#save")
    def on_save(self) -> None:
        # Save current area state first
        self._area_items[self._current_area] = list(self._items)
        order = [name for name, visible in self._items if visible]
        self.dismiss(
            FooterConfigResult(is_cancelled=False, order=order, area=self._current_area)
        )

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(FooterConfigResult(is_cancelled=True))


class ShowShortcutsScreen(ModalScreen[None]):
    """Modal that lists all keyboard shortcuts and allows rebinding."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    ShowShortcutsScreen {
        align: center middle;
    }
    ShowShortcutsScreen #dialog {
        padding: 0 1;
        width: 80;
        height: 30;
        border: thick $background 80%;
        background: $surface;
    }
    ShowShortcutsScreen #title {
        height: 1;
        width: 1fr;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }
    ShowShortcutsScreen #shortcuts_table {
        height: 1fr;
    }
    ShowShortcutsScreen #close {
        margin-top: 1;
        width: 100%;
    }
    """

    def __init__(
        self,
        rows: list[tuple[str, str, str, str]],
        display_config: dict[str, ShortcutDisplayEntry] | None = None,
    ) -> None:
        super().__init__()
        # rows: (key, description, context, action_name)
        self._rows = rows
        self._display_config = display_config or {}

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Keyboard Shortcuts", id="title"),
            DataTable(id="shortcuts_table", cursor_type="row"),
            Button("Close", variant="default", id="close"),
            id="dialog",
        )

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Key", "Description", "Context")
        for key, desc, ctx, action in self._rows:
            table.add_row(key, desc, ctx, key=action)

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        action_name = str(event.row_key.value)
        row = next(r for r in self._rows if r[3] == action_name)
        current_key, desc, _ctx, _action = row
        display_entry = self._display_config.get(action_name)
        palette_visible = (
            display_entry.palette
            if display_entry and display_entry.palette is not None
            else True
        )
        self.app.push_screen(
            ShortcutSettingsScreen(
                action_name=action_name,
                description=desc,
                current_key=current_key,
                palette_visible=palette_visible,
            ),
            self._on_settings_result,
        )

    def _on_settings_result(self, result: ShortcutSettingsResult | None) -> None:
        if result is None or result.is_cancelled:
            return
        app = cast("TextualCode", self.app)
        if result.new_key is not None and result.action_name:
            app.set_keybinding(result.action_name, result.new_key)
        if result.action_name:
            from textual_code.config import ShortcutDisplayEntry

            entry = ShortcutDisplayEntry(palette=result.palette_visible)
            app.set_shortcut_display(result.action_name, entry)
            self._display_config[result.action_name] = entry

    @on(Button.Pressed, "#close")
    def on_close(self) -> None:
        self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(None)


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
        self.app.call_from_thread(self._set_spinner_visible, True)
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
        self.app.call_from_thread(self._set_spinner_visible, True)
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


@dataclass
class ReplacePreviewResult:
    """Result of the Replace Preview screen."""

    is_cancelled: bool
    should_apply: bool


class ReplacePreviewScreen(ModalScreen[ReplacePreviewResult]):
    """Per-file diff preview screen before workspace-wide Replace All."""

    DEFAULT_CSS = """
    ReplacePreviewScreen {
        align: center middle;
    }
    ReplacePreviewScreen #dialog {
        width: 80%;
        height: 80%;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }
    ReplacePreviewScreen #title {
        height: 1;
        width: 1fr;
        text-style: bold;
        content-align: center middle;
        margin-bottom: 1;
    }
    ReplacePreviewScreen #panels {
        height: 1fr;
    }
    ReplacePreviewScreen #file-list {
        width: 30;
        margin-right: 1;
    }
    ReplacePreviewScreen #diff-view {
        width: 1fr;
        overflow-y: auto;
    }
    ReplacePreviewScreen .buttons {
        height: 3;
        layout: horizontal;
    }
    ReplacePreviewScreen .buttons Button {
        width: 1fr;
        margin: 0 1;
    }
    ReplacePreviewScreen #truncation-warning {
        height: 1;
        width: 1fr;
        color: $text-warning;
        text-style: bold;
        content-align: center middle;
    }
    """

    # No BINDINGS — escape must not dismiss a destructive action screen

    def __init__(
        self,
        previews: list[FileDiffPreview],
        is_truncated: bool = False,
    ) -> None:
        super().__init__()
        self._previews = previews
        self._total_occurrences = sum(p.replacement_count for p in previews)
        self._is_truncated = is_truncated

    def compose(self) -> ComposeResult:
        from textual.containers import VerticalScroll
        from textual.widgets import Static

        files_label = (
            f"{len(self._previews)}+"
            if self._is_truncated
            else str(len(self._previews))
        )
        occ_label = (
            f"{self._total_occurrences}+"
            if self._is_truncated
            else str(self._total_occurrences)
        )
        title = (
            f"Replace Preview \u00b7 {files_label} file(s)"
            f" \u00b7 {occ_label} occurrence(s)"
        )

        items = [
            ListItem(
                Label(f"{p.rel_path} ({p.replacement_count})"),
            )
            for p in self._previews
        ]

        with Vertical(id="dialog"):
            yield Label(title, id="title")
            with Horizontal(id="panels"):
                yield ListView(*items, id="file-list")
                with VerticalScroll(id="diff-view"):
                    yield Static("", id="diff-content")
            if self._is_truncated:
                yield Label(
                    "⚠ More files will be modified than shown in this preview.",
                    id="truncation-warning",
                )
            with Horizontal(classes="buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Apply All", variant="warning", id="apply-all")

    def on_mount(self) -> None:
        if self._previews:
            self._show_diff(0)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        list_view = self.query_one("#file-list", ListView)
        idx = list_view.index
        if idx is not None and 0 <= idx < len(self._previews):
            self._show_diff(idx)

    def _show_diff(self, index: int) -> None:
        from rich.markup import escape
        from textual.widgets import Static

        preview = self._previews[index]
        parts: list[str] = []
        for line in preview.diff_lines:
            escaped = escape(line.rstrip("\n"))
            if line.startswith(("---", "+++", "@@")):
                parts.append(f"[$text-muted]{escaped}[/]")
            elif line.startswith("-"):
                parts.append(f"[$text-error]{escaped}[/]")
            elif line.startswith("+"):
                parts.append(f"[$text-success]{escaped}[/]")
            else:
                parts.append(escaped)

        content = Content.from_markup("\n".join(parts))
        diff_static = self.query_one("#diff-content", Static)
        diff_static.update(content)

    @on(Button.Pressed, "#apply-all")
    def on_apply_all(self) -> None:
        self.dismiss(ReplacePreviewResult(is_cancelled=False, should_apply=True))

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(ReplacePreviewResult(is_cancelled=True, should_apply=False))
