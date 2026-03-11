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


class ChangeIndentModalScreen(ModalScreen[ChangeIndentModalResult]):
    """
    Modal dialog for changing indentation style and size.
    """

    def __init__(
        self,
        current_indent_type: str = "spaces",
        current_indent_size: int = 4,
    ) -> None:
        super().__init__()
        self._current_indent_type = current_indent_type
        self._current_indent_size = current_indent_size

    def compose(self) -> ComposeResult:
        yield Grid(
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
            Button("Apply", variant="primary", id="apply"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

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
        self.dismiss(
            ChangeIndentModalResult(
                is_cancelled=False,
                indent_type=indent_type,
                indent_size=indent_size,
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


class ChangeLineEndingModalScreen(ModalScreen[ChangeLineEndingModalResult]):
    """
    Modal dialog for changing the line ending style.
    """

    def __init__(self, current_line_ending: str = "lf") -> None:
        super().__init__()
        self._current_line_ending = current_line_ending

    def compose(self) -> ComposeResult:
        yield Grid(
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
            Button("Apply", variant="primary", id="apply"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Button.Pressed, "#apply")
    def on_apply(self) -> None:
        value = str(self.query_one(Select).value)
        self.dismiss(ChangeLineEndingModalResult(is_cancelled=False, line_ending=value))

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


class ChangeEncodingModalScreen(ModalScreen[ChangeEncodingModalResult]):
    """
    Modal dialog for changing the file encoding.
    """

    def __init__(self, current_encoding: str = "utf-8") -> None:
        super().__init__()
        self._current_encoding = current_encoding

    def compose(self) -> ComposeResult:
        yield Grid(
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
            Button("Apply", variant="primary", id="apply"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Button.Pressed, "#apply")
    def on_apply(self) -> None:
        value = str(self.query_one(Select).value)
        self.dismiss(ChangeEncodingModalResult(is_cancelled=False, encoding=value))

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
            Button("Apply", variant="primary", id="apply"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    @on(Button.Pressed, "#apply")
    def on_apply(self) -> None:
        value = self.query_one(Select).value
        theme = str(value) if value is not Select.BLANK else self._current_theme
        self.dismiss(ChangeSyntaxThemeModalResult(is_cancelled=False, theme=theme))

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(ChangeSyntaxThemeModalResult(is_cancelled=True, theme=None))
