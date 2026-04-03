from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Button,
    Input,
    Label,
    Select,
)


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
