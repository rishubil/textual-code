from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.events import Key
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
    Select,
)

if TYPE_CHECKING:
    from textual_code.app import TextualCode
    from textual_code.config import ShortcutDisplayEntry


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
    def on_cancel(self) -> None:
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
    def on_cancel(self) -> None:
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
    def on_cancel(self) -> None:
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
    def on_cancel(self) -> None:
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
    def on_cancel(self) -> None:
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
    def on_cancel(self) -> None:
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
    def on_cancel(self) -> None:
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
    def on_cancel(self) -> None:
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
    def on_cancel(self) -> None:
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
        yield Vertical(
            Label(f"Shortcut Settings: {self._description}", id="title"),
            Label(f"Current key: {self._current_key}", id="current_key_label"),
            Button("Change Key...", variant="default", id="change_key"),
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
    def on_cancel(self) -> None:
        self.dismiss(ShortcutSettingsResult(is_cancelled=True))


@dataclass
class FooterConfigResult:
    """Result from the FooterConfigScreen dialog."""

    is_cancelled: bool
    order: list[str] | None = None


class FooterConfigScreen(ModalScreen[FooterConfigResult]):
    """Modal for configuring which shortcuts appear in the footer and their order."""

    DEFAULT_CSS = """
    FooterConfigScreen {
        align: center middle;
    }
    FooterConfigScreen #dialog {
        padding: 1 2;
        width: 70;
        height: 34;
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
        Binding("space", "toggle_item", "Toggle", show=False),
        Binding("ctrl+up", "move_up", "Move up", show=False),
        Binding("ctrl+down", "move_down", "Move down", show=False),
    ]

    def __init__(
        self,
        actions: list[tuple[str, str, str, bool]],
        current_order: list[str] | None = None,
    ) -> None:
        super().__init__()
        # actions: (action_name, description, key, default_show)
        self._actions = {a[0]: (a[0], a[1], a[2]) for a in actions}
        # Build ordered list: visible items first (in order), then hidden items
        if current_order is not None:
            visible = set(current_order)
            self._items: list[tuple[str, bool]] = [
                (a, True) for a in current_order if a in self._actions
            ]
            for action_name, _desc, _key, _show in actions:
                if action_name not in visible:
                    self._items.append((action_name, False))
        else:
            # Default: use binding's show attribute
            self._items = [(a[0], a[3]) for a in actions]

    def _format_item_text(self, action_name: str, visible: bool) -> str:
        """Format the display text for a footer config list item."""
        _name, desc, key = self._actions[action_name]
        marker = "\u2713" if visible else "\u2717"
        return f" {marker}  {desc} ({key})"

    def compose(self) -> ComposeResult:
        items = [
            ListItem(Label(self._format_item_text(a, v)), name=a)
            for a, v in self._items
        ]
        yield Vertical(
            Label("Configure Footer Shortcuts", id="title"),
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
        order = [name for name, visible in self._items if visible]
        self.dismiss(FooterConfigResult(is_cancelled=False, order=order))

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(FooterConfigResult(is_cancelled=True))


class ShowShortcutsScreen(ModalScreen[None]):
    """Modal that lists all keyboard shortcuts and allows rebinding."""

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
        if result.new_key and result.action_name:
            app.set_keybinding(result.action_name, result.new_key)
        if result.action_name:
            from textual_code.config import ShortcutDisplayEntry

            entry = ShortcutDisplayEntry(palette=result.palette_visible)
            app.set_shortcut_display(result.action_name, entry)
            self._display_config[result.action_name] = entry

    @on(Button.Pressed, "#close")
    def on_close(self) -> None:
        self.dismiss(None)
