from __future__ import annotations

import contextlib
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from rich.text import Text
from textual import events, on, work
from textual.app import ComposeResult
from textual.events import Mount
from textual.message import Message
from textual.notifications import Notification, Notify
from textual.reactive import reactive
from textual.widgets import Button, Label, Static, TextArea
from textual.worker import get_current_worker

from textual_code.modals import (
    ChangeEncodingModalResult,
    ChangeEncodingModalScreen,
    ChangeIndentModalResult,
    ChangeIndentModalScreen,
    ChangeLanguageModalResult,
    ChangeLanguageModalScreen,
    ChangeLineEndingModalResult,
    ChangeLineEndingModalScreen,
    DeleteFileModalResult,
    DeleteFileModalScreen,
    DiscardAndReloadModalResult,
    DiscardAndReloadModalScreen,
    GotoLineModalResult,
    GotoLineModalScreen,
    OverwriteConfirmModalResult,
    OverwriteConfirmModalScreen,
    SaveAsModalResult,
    SaveAsModalScreen,
    UnsavedChangeModalResult,
    UnsavedChangeModalScreen,
)
from textual_code.widgets.code_editor_git import (
    _MAX_DIFF_LINES as _MAX_DIFF_LINES,
)

# Re-exports for backward compatibility (used by tests and other modules).
from textual_code.widgets.code_editor_git import (
    LineChangeType as LineChangeType,
)
from textual_code.widgets.code_editor_git import (
    _compute_line_changes as _compute_line_changes,
)
from textual_code.widgets.code_editor_git import (
    _get_git_head_content as _get_git_head_content,
)
from textual_code.widgets.code_editor_grammar import (
    _CUSTOM_GRAMMAR_NAMES as _CUSTOM_GRAMMAR_NAMES,
)
from textual_code.widgets.code_editor_grammar import (
    _CUSTOM_LANGUAGE_QUERIES as _CUSTOM_LANGUAGE_QUERIES,
)
from textual_code.widgets.code_editor_grammar import (
    _CUSTOM_LANGUAGES as _CUSTOM_LANGUAGES,
)
from textual_code.widgets.code_editor_grammar import (
    _GRAMMAR_COMPOSITION as _GRAMMAR_COMPOSITION,
)
from textual_code.widgets.code_editor_grammar import (
    _GRAMMARS_DIR as _GRAMMARS_DIR,
)
from textual_code.widgets.code_editor_grammar import (
    _resolve_highlight_query as _resolve_highlight_query,
)
from textual_code.widgets.code_editor_helpers import (
    _CHARSET_MAP as _CHARSET_MAP,
)
from textual_code.widgets.code_editor_helpers import (
    _ENCODING_DISPLAY as _ENCODING_DISPLAY,
)
from textual_code.widgets.code_editor_helpers import (
    _LINE_ENDING_WARNING as _LINE_ENDING_WARNING,
)
from textual_code.widgets.code_editor_helpers import (
    _convert_indentation as _convert_indentation,
)
from textual_code.widgets.code_editor_helpers import (
    _convert_line_ending as _convert_line_ending,
)
from textual_code.widgets.code_editor_helpers import (
    _detect_encoding as _detect_encoding,
)
from textual_code.widgets.code_editor_helpers import (
    _detect_line_ending as _detect_line_ending,
)
from textual_code.widgets.code_editor_helpers import (
    _editorconfig_glob_to_pattern as _editorconfig_glob_to_pattern,
)
from textual_code.widgets.code_editor_helpers import (
    _find_next as _find_next,
)
from textual_code.widgets.code_editor_helpers import (
    _find_previous as _find_previous,
)
from textual_code.widgets.code_editor_helpers import (
    _get_word_at_location as _get_word_at_location,
)
from textual_code.widgets.code_editor_helpers import (
    _glob_to_regex as _glob_to_regex,
)
from textual_code.widgets.code_editor_helpers import (
    _indent_display as _indent_display,
)
from textual_code.widgets.code_editor_helpers import (
    _insert_final_newline as _insert_final_newline,
)
from textual_code.widgets.code_editor_helpers import (
    _location_to_text_offset as _location_to_text_offset,
)
from textual_code.widgets.code_editor_helpers import (
    _parse_editorconfig_file as _parse_editorconfig_file,
)
from textual_code.widgets.code_editor_helpers import (
    _read_editorconfig as _read_editorconfig,
)
from textual_code.widgets.code_editor_helpers import (
    _remove_final_newline as _remove_final_newline,
)
from textual_code.widgets.code_editor_helpers import (
    _snapshot_editorconfig_mtimes as _snapshot_editorconfig_mtimes,
)
from textual_code.widgets.code_editor_helpers import (
    _text_offset_to_location as _text_offset_to_location,
)
from textual_code.widgets.code_editor_helpers import (
    _trim_trailing_whitespace as _trim_trailing_whitespace,
)
from textual_code.widgets.code_editor_helpers import (
    _word_boundary_pattern as _word_boundary_pattern,
)
from textual_code.widgets.find_replace_bar import FindReplaceBar
from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

log = logging.getLogger(__name__)


@dataclass
class EditorState:
    """Serialized state of a CodeEditor for lazy unmounting."""

    pane_id: str
    path: Path | None
    text: str
    initial_text: str
    language: str | None
    encoding: str
    line_ending: str
    indent_type: str
    indent_size: int
    word_wrap: bool
    cursor_end: tuple[int, int]
    scroll_offset: tuple[int, int]
    file_mtime: float | None
    ec_search_dirs: list[Path]
    ec_mtimes: dict[Path, float | None]
    trim_trailing_whitespace: bool | None
    insert_final_newline: bool | None
    syntax_theme: str
    warn_line_ending: bool
    notified_copy_line_ending: bool
    show_indentation_guides: bool = True
    render_whitespace: str = "none"
    force_no_highlighting: bool = False


class _PathLabel(Label):
    """Label that front-truncates its content to fit the available width."""

    _raw: str = ""

    def show(
        self,
        path: Path | None,
        workspace_path: Path | None = None,
        mode: str = "absolute",
    ) -> None:
        """Set the path and immediately render (uses current region if available)."""
        if path is None:
            self._raw = ""
        elif mode == "relative" and workspace_path is not None:
            try:
                self._raw = path.relative_to(workspace_path).as_posix()
            except ValueError:
                self._raw = str(path)
        else:
            self._raw = str(path)
        self._truncate()

    def _truncate(self) -> None:
        raw = self._raw
        available = self.region.width
        if available > 0 and len(raw) > available:
            theme = self.app.theme_variables
            fg = theme.get("foreground-darken-3", "#a2a2a2")
            bg = theme.get("surface-lighten-2", "#3e3e3e")
            ellipsis_style = f"{fg} on {bg}"
            if available > 3:
                tail = raw[-(available - 3) :]
                text = Text()
                text.append("...", style=ellipsis_style)
                text.append(tail)
                self.update(text)
            else:
                self.update(Text("..."[:available], style=ellipsis_style))
        else:
            self.update(raw)

    def on_resize(self) -> None:
        self._truncate()


class CodeEditorFooter(Static):
    """
    Footer for the CodeEditor widget.

    It displays the information about the current file being edited.
    """

    DEFAULT_CSS = """
    CodeEditorFooter {
        dock: bottom;
        height: 1;
        layout: horizontal;
    }
    CodeEditorFooter Button {
        height: 1;
        border: none;
        min-width: 0;
    }
    """

    # the path of the file
    path: reactive[Path | None] = reactive(None, init=False)
    # the language of the file
    language: reactive[str | None] = reactive(None, init=False)
    # the cursor location (row, col) — zero-based internally, displayed 1-based
    cursor_location: reactive[tuple[int, int]] = reactive((0, 0), init=False)
    # total cursor count (1 = single cursor, >1 = multi-cursor active)
    cursor_count: reactive[int] = reactive(1, init=False)
    # the line ending style
    line_ending: reactive[str] = reactive("lf", init=False)
    # the file encoding
    encoding: reactive[str] = reactive("utf-8", init=False)
    # the indentation type ("spaces" or "tabs")
    indent_type: reactive[str] = reactive("spaces", init=False)
    # the indentation size (2, 4, or 8)
    indent_size: reactive[int] = reactive(4, init=False)
    # path display mode ("absolute" or "relative")
    path_display_mode: reactive[str] = reactive("absolute", init=False)

    def __init__(
        self,
        path: Path | None = None,
        language: str | None = None,
        line_ending: str = "lf",
        encoding: str = "utf-8",
        indent_type: str = "spaces",
        indent_size: int = 4,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.set_reactive(CodeEditorFooter.path, path)
        self.set_reactive(CodeEditorFooter.language, language)
        self.set_reactive(CodeEditorFooter.line_ending, line_ending)
        self.set_reactive(CodeEditorFooter.encoding, encoding)
        self.set_reactive(CodeEditorFooter.indent_type, indent_type)
        self.set_reactive(CodeEditorFooter.indent_size, indent_size)

    def reset(self) -> None:
        """Reset footer to empty/default state (no active editor).

        path_display_mode intentionally excluded — global setting, not per-editor state.
        """
        self.path = None
        self.language = None
        self.cursor_location = (0, 0)
        self.cursor_count = 1
        self.line_ending = "lf"
        self.encoding = "utf-8"
        self.indent_type = "spaces"
        self.indent_size = 4

    def compose(self) -> ComposeResult:
        yield _PathLabel(
            str(self.path) if self.path else "",
            id="path",
        )
        yield Button(
            "Ln 1, Col 1",
            variant="default",
            id="cursor_btn",
        )
        yield Button(
            self.line_ending.upper(),
            variant="default",
            id="line_ending_btn",
        )
        yield Button(
            _ENCODING_DISPLAY.get(self.encoding, self.encoding),
            variant="default",
            id="encoding_btn",
        )
        yield Button(
            _indent_display(self.indent_type, self.indent_size),
            variant="default",
            id="indent_btn",
        )
        yield Button(
            self.language or "plain",
            variant="default",
            id="language",
        )

    def _refresh_path_display(self) -> None:
        ws = getattr(self.app, "workspace_path", None)
        self.path_view.show(self.path, ws, self.path_display_mode)

    def watch_path(self, path: Path | None) -> None:
        self._refresh_path_display()

    def watch_path_display_mode(self, mode: str) -> None:
        self._refresh_path_display()

    def watch_language(self, language: str | None) -> None:
        self.language_button.label = language or "plain"
        self.language_button.refresh(layout=True)
        self.refresh(layout=True)

    def watch_cursor_location(self, location: tuple[int, int]) -> None:
        self._update_cursor_button()

    def watch_cursor_count(self, count: int) -> None:
        self._update_cursor_button()

    def _update_cursor_button_label(self) -> None:
        """Update cursor button label only (no refresh)."""
        row, col = self.cursor_location
        label = f"Ln {row + 1}, Col {col + 1}"
        if self.cursor_count > 1:
            label += f" [{self.cursor_count}]"
        self.cursor_button.label = label

    def _update_cursor_button(self) -> None:
        self._update_cursor_button_label()
        self.cursor_button.refresh(layout=True)
        self.refresh(layout=True)

    def refresh_all_buttons(self) -> None:
        """Update all button labels from current reactive values and refresh once."""
        self._refresh_path_display()
        self._update_cursor_button_label()
        self.cursor_button.refresh(layout=True)
        self.line_ending_button.label = self.line_ending.upper()
        self.line_ending_button.refresh(layout=True)
        self.encoding_button.label = _ENCODING_DISPLAY.get(self.encoding, self.encoding)
        self.encoding_button.refresh(layout=True)
        self.indent_button.label = _indent_display(self.indent_type, self.indent_size)
        self.indent_button.refresh(layout=True)
        self.language_button.label = self.language or "plain"
        self.language_button.refresh(layout=True)
        self.refresh(layout=True)

    def watch_line_ending(self, line_ending: str) -> None:
        self.line_ending_button.label = line_ending.upper()
        self.line_ending_button.refresh(layout=True)
        self.refresh(layout=True)

    def watch_encoding(self, encoding: str) -> None:
        self.encoding_button.label = _ENCODING_DISPLAY.get(encoding, encoding)
        self.encoding_button.refresh(layout=True)
        self.refresh(layout=True)

    def watch_indent_type(self, indent_type: str) -> None:
        self.indent_button.label = _indent_display(indent_type, self.indent_size)
        self.indent_button.refresh(layout=True)
        self.refresh(layout=True)

    def watch_indent_size(self, indent_size: int) -> None:
        self.indent_button.label = _indent_display(self.indent_type, indent_size)
        self.indent_button.refresh(layout=True)
        self.refresh(layout=True)

    @property
    def path_view(self) -> _PathLabel:
        return self.query_one("#path", _PathLabel)

    @property
    def cursor_button(self) -> Button:
        return self.query_one("#cursor_btn", Button)

    @property
    def line_ending_button(self) -> Button:
        return self.query_one("#line_ending_btn", Button)

    @property
    def encoding_button(self) -> Button:
        return self.query_one("#encoding_btn", Button)

    @property
    def indent_button(self) -> Button:
        return self.query_one("#indent_btn", Button)

    @property
    def language_button(self) -> Button:
        return self.query_one("#language", Button)


class CodeEditor(Static):
    """
    Code editor widget.

    It allows the user to edit code in a text area, with syntax highlighting.
    """

    # the unique ID of the pane.
    # this is used to identify the pane in the MainView.
    pane_id: reactive[str] = reactive("", init=False)
    # the path of the file
    path: reactive[Path | None] = reactive(None, init=False)
    # the initial text of the editor.
    # this is the text that was loaded from the file.
    # if the text is change from the initial text, the editor is considered to have
    # unsaved changes.
    initial_text: reactive[str] = reactive("", init=False)
    # the current text of the editor
    text: reactive[str] = reactive("", init=False)
    # the title of the editor.
    # it will be displayed in the tab of the pane.
    title: reactive[str] = reactive("...", init=False)
    # the language of the file
    language: reactive[str | None] = reactive(None, init=False)
    # the line ending style of the file
    line_ending: reactive[str] = reactive("lf", init=False)
    # the file encoding
    encoding: reactive[str] = reactive("utf-8", init=False)
    # the indentation type ("spaces" or "tabs")
    indent_type: reactive[str] = reactive("spaces", init=False)
    # the indentation size (2, 4, or 8)
    indent_size: reactive[int] = reactive(4, init=False)
    # whether word wrap is enabled
    word_wrap: reactive[bool] = reactive(False, init=False)
    show_indentation_guides: reactive[bool] = reactive(True, init=False)
    render_whitespace: reactive[str] = reactive("none", init=False)

    # mapping of file extensions to language names
    LANGUAGE_EXTENSIONS = {
        "py": "python",
        "json": "json",
        "md": "markdown",
        "markdown": "markdown",
        "yaml": "yaml",
        "yml": "yaml",
        "toml": "toml",
        "rs": "rust",
        "html": "html",
        "htm": "html",
        "css": "css",
        "xml": "xml",
        "regex": "regex",
        "sql": "sql",
        "js": "javascript",
        "mjs": "javascript",
        "cjs": "javascript",
        "java": "java",
        "sh": "bash",
        "bash": "bash",
        "go": "go",
        "svg": "xml",
        "xhtml": "xml",
        # custom languages via tree-sitter-language-pack
        "dockerfile": "dockerfile",
        "ts": "typescript",
        "tsx": "tsx",
        "c": "c",
        "h": "c",
        "cpp": "cpp",
        "cc": "cpp",
        "cxx": "cpp",
        "hpp": "cpp",
        "rb": "ruby",
        "kt": "kotlin",
        "kts": "kotlin",
        "lua": "lua",
        "php": "php",
        "mk": "make",
    }

    # mapping of exact file names to language names (checked before extension)
    LANGUAGE_FILENAMES = {
        ".bashrc": "bash",
        ".bash_profile": "bash",
        ".bash_logout": "bash",
        # custom languages via tree-sitter-language-pack
        "Dockerfile": "dockerfile",
        "Makefile": "make",
        "makefile": "make",
        "GNUmakefile": "make",
    }

    @dataclass
    class TitleChanged(Message):
        """
        Message to notify that the title of the editor has changed.
        """

        code_editor: CodeEditor

        @property
        def control(self) -> CodeEditor:
            return self.code_editor

    @dataclass
    class Saved(Message):
        """
        Message to notify that the file has been saved.
        """

        code_editor: CodeEditor

        @property
        def control(self) -> CodeEditor:
            return self.code_editor

    @dataclass
    class SavedAs(Message):
        """
        Message to notify that the file has been saved as a new file.
        """

        code_editor: CodeEditor

        @property
        def control(self) -> CodeEditor:
            return self.code_editor

    @dataclass
    class Closed(Message):
        """
        Message to notify that the editor has been closed.
        """

        code_editor: CodeEditor

        @property
        def control(self) -> CodeEditor:
            return self.code_editor

    @dataclass
    class Deleted(Message):
        """
        Message to notify that the file has been deleted.
        """

        code_editor: CodeEditor

        @property
        def control(self) -> CodeEditor:
            return self.code_editor

    @dataclass
    class TextChanged(Message):
        """Posted when the editor's text content changes."""

        code_editor: CodeEditor

        @property
        def control(self) -> CodeEditor:
            return self.code_editor

    @dataclass
    class FooterStateChanged(Message):
        """Posted when this editor's footer-relevant state changes."""

        code_editor: CodeEditor

        @property
        def control(self) -> CodeEditor:
            return self.code_editor

    @classmethod
    def generate_pane_id(cls) -> str:
        """
        Generate a unique pane ID.
        """
        return f"pane-code-editor-{uuid4().hex}"

    def __init__(
        self,
        pane_id: str,
        path: Path | None,
        *args,
        default_indent_type: str = "spaces",
        default_indent_size: int = 4,
        default_line_ending: str = "lf",
        default_encoding: str = "utf-8",
        default_syntax_theme: str = "monokai",
        default_word_wrap: bool = False,
        default_show_indentation_guides: bool = True,
        default_render_whitespace: str = "none",
        default_warn_line_ending: bool = True,
        _from_state: EditorState | None = None,
        _force_no_highlighting: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.set_reactive(CodeEditor.pane_id, pane_id)
        self.set_reactive(CodeEditor.path, path)
        self._file_mtime: float | None = None
        self._external_change_notification: Notification | None = None
        self._force_no_highlighting = _force_no_highlighting
        self._syntax_theme: str = default_syntax_theme
        self._warn_line_ending: bool = default_warn_line_ending
        self._notified_copy_line_ending: bool = False
        # tracks the end offset of the last successful find for sequential search
        self._find_offset: int | None = None
        # Ctrl+D word-boundary mode: non-empty when initiated from collapsed cursor
        self._ctrl_d_query: str = ""
        # EditorConfig save-time transformations (None = not set)
        self._trim_trailing_whitespace: bool | None = None
        self._insert_final_newline: bool | None = None
        # EditorConfig watch state
        self._ec_search_dirs: list[Path] = []
        self._ec_mtimes: dict[Path, float | None] = {}
        # cursor/scroll positions to restore after mount (lazy remount)
        self._restore_cursor: tuple[int, int] | None = None
        self._restore_scroll: tuple[int, int] | None = None
        self._is_restoring: bool = False
        # Git diff gutter: cached HEAD lines for diff computation
        self._git_head_lines: list[str] | None = None

        if _from_state is not None:
            # Restore from captured state — skip file I/O
            self.set_reactive(CodeEditor.pane_id, _from_state.pane_id)
            self.set_reactive(CodeEditor.path, _from_state.path)
            self.set_reactive(CodeEditor.initial_text, _from_state.initial_text)
            self.set_reactive(CodeEditor.text, _from_state.text)
            self.set_reactive(CodeEditor.language, _from_state.language)
            self.set_reactive(CodeEditor.encoding, _from_state.encoding)
            self.set_reactive(CodeEditor.line_ending, _from_state.line_ending)
            self.set_reactive(CodeEditor.indent_type, _from_state.indent_type)
            self.set_reactive(CodeEditor.indent_size, _from_state.indent_size)
            self.set_reactive(CodeEditor.word_wrap, _from_state.word_wrap)
            self.set_reactive(
                CodeEditor.show_indentation_guides,
                _from_state.show_indentation_guides,
            )
            self.set_reactive(
                CodeEditor.render_whitespace,
                _from_state.render_whitespace,
            )
            self._file_mtime = _from_state.file_mtime
            self._ec_search_dirs = list(_from_state.ec_search_dirs)
            self._ec_mtimes = dict(_from_state.ec_mtimes)
            self._trim_trailing_whitespace = _from_state.trim_trailing_whitespace
            self._insert_final_newline = _from_state.insert_final_newline
            self._syntax_theme = _from_state.syntax_theme
            self._warn_line_ending = _from_state.warn_line_ending
            self._notified_copy_line_ending = _from_state.notified_copy_line_ending
            self._force_no_highlighting = _from_state.force_no_highlighting
            self._restore_cursor = _from_state.cursor_end
            self._restore_scroll = _from_state.scroll_offset
            self._is_restoring = True
            return

        # if a path is provided, load the file content
        if path is not None:
            try:
                raw_bytes = path.read_bytes()
            except Exception as e:
                raw_bytes = b""
                self.notify(f"Error reading file: {e}", severity="error")
            detected_encoding = _detect_encoding(raw_bytes)
            self.set_reactive(CodeEditor.encoding, detected_encoding)
            try:
                raw_text = raw_bytes.decode(detected_encoding)
            except Exception:
                raw_text = raw_bytes.decode("latin-1", errors="replace")
            detected = _detect_line_ending(raw_text)
            self.set_reactive(CodeEditor.line_ending, detected)
            # normalize to \n for the editor
            text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
            # remove BOM char if present (utf-8-sig decodes it, but guard defensively)
            if text.startswith("\ufeff"):
                text = text[1:]
            self.set_reactive(CodeEditor.initial_text, text)
            self.set_reactive(CodeEditor.text, text)
            with contextlib.suppress(OSError):
                self._file_mtime = path.stat().st_mtime

            # Apply EditorConfig overrides (after auto-detect)
            ec, self._ec_search_dirs = _read_editorconfig(path)
            self._ec_mtimes = _snapshot_editorconfig_mtimes(self._ec_search_dirs)
            self._apply_editorconfig(ec, init_all=True)

            self.set_reactive(CodeEditor.word_wrap, default_word_wrap)
            self.set_reactive(
                CodeEditor.show_indentation_guides,
                default_show_indentation_guides,
            )
            self.set_reactive(
                CodeEditor.render_whitespace,
                default_render_whitespace,
            )
        else:
            # Apply app-level defaults for new untitled files
            self.set_reactive(CodeEditor.indent_type, default_indent_type)
            self.set_reactive(CodeEditor.indent_size, default_indent_size)
            self.set_reactive(CodeEditor.line_ending, default_line_ending)
            self.set_reactive(CodeEditor.encoding, default_encoding)
            self.set_reactive(CodeEditor.word_wrap, default_word_wrap)
            self.set_reactive(
                CodeEditor.show_indentation_guides,
                default_show_indentation_guides,
            )
            self.set_reactive(
                CodeEditor.render_whitespace,
                default_render_whitespace,
            )

    def _apply_editorconfig(
        self, ec: dict[str, str], *, init_all: bool = False
    ) -> None:
        """Apply editorconfig properties to editor state.

        When init_all=True (first open), uses set_reactive (widget not mounted
        yet, watchers cannot fire). Also applies charset and end_of_line.
        When init_all=False (reload), uses direct assignment so that watchers
        fire and the TextArea widget + footer are updated.
        """
        ec_indent_style = ec.get("indent_style")
        if init_all:
            if ec_indent_style == "space":
                self.set_reactive(CodeEditor.indent_type, "spaces")
            elif ec_indent_style == "tab":
                self.set_reactive(CodeEditor.indent_type, "tabs")
        else:
            if ec_indent_style == "space":
                self.indent_type = "spaces"
            elif ec_indent_style == "tab":
                self.indent_type = "tabs"

        ec_indent = ec.get("indent_size")
        if ec_indent == "tab":
            ec_indent = ec.get("tab_width")
        if not ec_indent and ec_indent_style == "tab":
            ec_indent = ec.get("tab_width")
        if ec_indent and ec_indent != "unset":
            with contextlib.suppress(ValueError):
                size = int(ec_indent)
                if size in (2, 4, 8):
                    if init_all:
                        self.set_reactive(CodeEditor.indent_size, size)
                    else:
                        self.indent_size = size

        if init_all:
            ec_charset = ec.get("charset")
            if ec_charset and ec_charset != "unset":
                enc = _CHARSET_MAP.get(ec_charset)
                if enc:
                    self.set_reactive(CodeEditor.encoding, enc)

            ec_eol = ec.get("end_of_line")
            if ec_eol and ec_eol != "unset" and ec_eol in ("lf", "crlf", "cr"):
                self.set_reactive(CodeEditor.line_ending, ec_eol)

        ec_trim = ec.get("trim_trailing_whitespace")
        if ec_trim == "true":
            self._trim_trailing_whitespace = True
        elif ec_trim == "false":
            self._trim_trailing_whitespace = False
        elif not init_all:
            self._trim_trailing_whitespace = None

        ec_final_newline = ec.get("insert_final_newline")
        if ec_final_newline == "true":
            self._insert_final_newline = True
        elif ec_final_newline == "false":
            self._insert_final_newline = False
        elif not init_all:
            self._insert_final_newline = None

    def compose(self) -> ComposeResult:
        yield FindReplaceBar()
        # Custom languages require register_language() before use;
        # pass None and let watch_language() handle registration.
        lang = None if self.language in _CUSTOM_LANGUAGES else self.language
        yield MultiCursorTextArea.code_editor(
            text=self.text,
            language=lang,
            tab_behavior="focus",
        )

    def _notify_footer(self) -> None:
        """Post FooterStateChanged so MainView can update the global footer."""
        self.post_message(self.FooterStateChanged(self))

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        if event.widget is self.editor:
            self._notify_footer()

    @on(Mount)
    def on_mount(self, event: Mount) -> None:
        # update the title of the editor
        self.update_title()
        # apply syntax highlighting theme
        self.editor.theme = self._syntax_theme
        # apply word wrap (reactive init=False, so set manually)
        self.editor.soft_wrap = self.word_wrap
        # apply indentation guides (reactive init=False, so set manually)
        self.editor._show_indentation_guides = self.show_indentation_guides
        # apply render whitespace (reactive init=False, so set manually)
        self.editor._render_whitespace = self.render_whitespace
        # apply indent settings (reactive init=False, so set manually)
        self.editor.indent_width = self.indent_size
        self.editor.indent_type = self.indent_type
        if self._is_restoring:
            # Language was set via set_reactive; apply it to the editor widget
            self.watch_language(self.language)
            if self._restore_cursor is not None:
                self.editor.cursor_location = self._restore_cursor
                self._restore_cursor = None
            if self._restore_scroll is not None:
                x, y = self._restore_scroll
                self.editor.scroll_to(x, y, animate=False)
                self._restore_scroll = None
            self._is_restoring = False
        else:
            # update the language of the editor (triggers lazy language registration)
            if not self._force_no_highlighting:
                self.load_language_from_path(self.path)
        # Start background git diff computation
        self._refresh_git_diff()

    # ── git diff gutter ──────────────────────────────────────────────────────

    @work(thread=True, exclusive=True, group="git_diff")
    def _refresh_git_diff(self) -> None:
        """Fetch HEAD content in a background thread and compute line diff."""
        worker = get_current_worker()
        head_lines = self._fetch_head_lines()
        if worker.is_cancelled:
            log.debug("git_diff worker cancelled, skipping callback")
            return
        try:
            self.app.call_from_thread(self._apply_git_diff, head_lines)
        except RuntimeError as exc:
            if "loop" not in str(exc).lower() and "closed" not in str(exc).lower():
                raise
            log.debug("call_from_thread suppressed (app exiting): %s", exc)

    def _fetch_head_lines(self) -> list[str] | None:
        """Return HEAD lines for the current file, or None to clear indicators."""
        if self.path is None:
            return None
        app = self.app
        if hasattr(app, "default_show_git_status") and not app.default_show_git_status:
            return None
        head_content = _get_git_head_content(self.path, encoding=self.encoding)
        if head_content is None:
            return None
        return head_content.splitlines()

    def _apply_git_diff(self, head_lines: list[str] | None) -> None:
        """Apply git diff results on the main thread."""
        if not self.is_mounted:
            return
        self._git_head_lines = head_lines
        self._recompute_git_diff()

    def _recompute_git_diff(self) -> None:
        """Recompute line changes using cached HEAD lines and current text."""
        from textual.css.query import NoMatches

        try:
            ta = self.editor
        except NoMatches:
            # MultiCursorTextArea not yet mounted (race on Windows)
            return
        if self._git_head_lines is None:
            if ta._line_changes:
                ta.set_line_changes({})
            return
        current_lines = ta.text.splitlines()
        changes = _compute_line_changes(self._git_head_lines, current_lines)
        log.debug("git diff: %d changes for %s", len(changes), self.path)
        ta.set_line_changes(changes)

    def update_title(self) -> None:
        """
        Update the title of the editor.

        The title is the name of the file, with an asterisk (*) if there are unsaved.
        If the file path is not set, the title is "<Untitled>".
        """
        is_changed = False
        if self.text != self.initial_text:
            is_changed = True
        name = "<Untitled>"
        if self.path is not None:
            name = self.path.name
        self.title = f"{name}{'*' if is_changed else ''}"

    def load_language_from_path(self, path: Path | None) -> None:
        """
        Update the language of the editor based on the file name or extension.
        """
        if path is None:
            self.language = None
            return
        # Check full filename first (for files like .bashrc with no extension)
        filename = path.name
        if filename in self.LANGUAGE_FILENAMES:
            self.language = self.LANGUAGE_FILENAMES[filename]
            return
        # Fall back to extension
        extension = path.suffix.lstrip(".")
        self.language = self.LANGUAGE_EXTENSIONS.get(extension, None)

    def replace_editor_text(self, text: str) -> None:
        """
        Replace the text in the editor with the new text.
        """

        self.editor.replace(
            text,
            self.editor.document.start,
            self.editor.document.end,
        )

    def sync_text(self, text: str) -> None:
        """Sync text from another editor editing the same file. Preserves cursor."""
        if self.editor.text == text:
            return
        selection = self.editor.selection
        self.replace_editor_text(text)
        self.editor.selection = selection

    def watch_title(self, title: str) -> None:
        # notify that the title has changed
        # this will update the tab title in the MainView
        self.post_message(
            self.TitleChanged(
                code_editor=self,
            )
        )

    def watch_text(self, text: str) -> None:
        # update the title, as the text has changed
        self.update_title()
        self.post_message(self.TextChanged(self))

    def watch_initial_text(self, initial_text: str) -> None:
        # update the title, as the initial text has changed
        self.update_title()
        # replace the text in the editor with the new initial text
        self.replace_editor_text(initial_text)

    def watch_path(self, path: Path | None) -> None:
        # update the title, as the path has changed
        self.update_title()

        # update the language based on the new path
        self.load_language_from_path(path)

        self._notify_footer()

    def watch_language(self, language: str | None):
        # lazily register custom tree-sitter language if needed
        if (
            language
            and language in _CUSTOM_LANGUAGES
            and language not in self.editor.available_languages
        ):
            query = _CUSTOM_LANGUAGE_QUERIES.get(language, "")
            try:
                self.editor.register_language(
                    language, _CUSTOM_LANGUAGES[language], query
                )
            except Exception as e:
                log.warning("Failed to register language %s: %s", language, e)
        # update the language in the editor
        self.editor.language = language
        self._notify_footer()

    def watch_line_ending(self, line_ending: str) -> None:
        self._notified_copy_line_ending = False
        self._notify_footer()

    def watch_encoding(self, encoding: str) -> None:
        self._notify_footer()

    def watch_indent_type(self, indent_type: str) -> None:
        self.editor.indent_type = indent_type
        self._notify_footer()

    def watch_indent_size(self, indent_size: int) -> None:
        self.editor.indent_width = indent_size
        self._notify_footer()

    def watch_word_wrap(self, value: bool) -> None:
        self.editor.soft_wrap = value

    def action_toggle_word_wrap(self) -> None:
        """Toggle word wrap for the current file."""
        self.word_wrap = not self.word_wrap

    def watch_show_indentation_guides(self, value: bool) -> None:
        self.editor._show_indentation_guides = value
        # Private API dependency: clear Textual's internal line cache so
        # the rendering update takes effect immediately.
        self.editor._line_cache.clear()
        self.editor.refresh()

    def action_toggle_indentation_guides(self) -> None:
        """Toggle indentation guides for the current file."""
        self.show_indentation_guides = not self.show_indentation_guides

    def watch_render_whitespace(self, value: str) -> None:
        self.editor._render_whitespace = value
        self.editor._line_cache.clear()
        self.editor.refresh()

    _RENDER_WHITESPACE_MODES = ("none", "all", "boundary", "trailing")

    def action_cycle_render_whitespace(self) -> None:
        """Cycle through whitespace rendering modes."""
        modes = self._RENDER_WHITESPACE_MODES
        try:
            idx = modes.index(self.render_whitespace)
        except ValueError:
            idx = -1
        new_mode = modes[(idx + 1) % len(modes)]
        self.render_whitespace = new_mode
        self.notify(f"Render whitespace: {new_mode}")

    def _notify_non_lf_if_needed(self, *, from_clipboard: bool = False) -> None:
        if not self._warn_line_ending:
            return
        if self.line_ending == "lf":
            return
        if from_clipboard and self._notified_copy_line_ending:
            return
        self.notify(
            _LINE_ENDING_WARNING.format(ending=self.line_ending.upper()),
            severity="warning",
        )
        if from_clipboard:
            self._notified_copy_line_ending = True

    def _poll_file_change(self) -> None:
        """Check if file was modified externally; auto-reload if no unsaved changes."""
        if self.path is None or self._file_mtime is None:
            return
        try:
            current_mtime = self.path.stat().st_mtime
        except OSError:
            return
        if current_mtime == self._file_mtime:
            return
        if self.text != self.initial_text:
            if self._external_change_notification is None:
                notification = Notification(
                    "File changed externally. Reload to apply changes.",
                    severity="warning",
                    timeout=float("inf"),
                )
                self._external_change_notification = notification
                self.app.post_message(Notify(notification))
        else:
            self._reload_file()

    def _poll_editorconfig_change(self) -> None:
        """Check if any .editorconfig in the chain has changed; re-apply if so."""
        if self.path is None or not self._ec_search_dirs:
            return
        current = _snapshot_editorconfig_mtimes(self._ec_search_dirs)
        if current != self._ec_mtimes:
            self._apply_editorconfig_changes()

    def _apply_editorconfig_changes(self) -> None:
        """Re-read and re-apply editorconfig properties (safe-to-change only)."""
        if self.path is None:
            return
        ec, self._ec_search_dirs = _read_editorconfig(self.path)
        self._ec_mtimes = _snapshot_editorconfig_mtimes(self._ec_search_dirs)
        self._apply_editorconfig(ec, init_all=False)
        self.notify("EditorConfig updated.", severity="information")

    def _dismiss_external_change_notification(self) -> None:
        """Dismiss the external-change toast if one is currently displayed."""
        if self._external_change_notification is not None:
            self.app._unnotify(self._external_change_notification)
            self._external_change_notification = None

    def _reload_file(self) -> None:
        """Reload file content from disk, resetting unsaved state."""
        self._dismiss_external_change_notification()
        if self.path is None:
            return
        try:
            raw_bytes = self.path.read_bytes()
        except OSError as e:
            self.notify(f"Error reloading file: {e}", severity="error")
            return
        detected_encoding = _detect_encoding(raw_bytes)
        try:
            raw_text = raw_bytes.decode(detected_encoding)
        except Exception:
            raw_text = raw_bytes.decode("latin-1", errors="replace")
        detected = _detect_line_ending(raw_text)
        text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        if text.startswith("\ufeff"):
            text = text[1:]
        self.encoding = detected_encoding
        self.line_ending = detected
        self.initial_text = text  # triggers watch_initial_text → replace_editor_text
        self.text = text  # sync reactive so text == initial_text immediately
        with contextlib.suppress(OSError):
            self._file_mtime = self.path.stat().st_mtime
        self.notify("File reloaded.", severity="information")

    def action_revert_file(self) -> None:
        """Manually reload the current file from disk."""
        if self.path is None:
            self.notify("No file to reload.", severity="error")
            return
        if self.text != self.initial_text:

            def do_reload(result: DiscardAndReloadModalResult | None) -> None:
                if result is None or result.is_cancelled or not result.should_reload:
                    return
                self._reload_file()

            self.app.push_screen(DiscardAndReloadModalScreen(), do_reload)
            return
        self._reload_file()

    def _apply_save_transformations(self, text: str) -> str:
        """Apply EditorConfig save-time transformations to text.

        Order: trim_trailing_whitespace first, then insert_final_newline.
        Operates on LF-normalized text (before line ending conversion).
        """
        if self._trim_trailing_whitespace is True:
            text = _trim_trailing_whitespace(text)
        if self._insert_final_newline is True:
            text = _insert_final_newline(text)
        elif self._insert_final_newline is False:
            text = _remove_final_newline(text)
        return text

    def _write_to_disk(self) -> None:
        """Write current text to disk and update mtime. Requires self.path is set."""
        assert self.path is not None
        self._dismiss_external_change_notification()
        try:
            saved_text = self._apply_save_transformations(self.text)
            content = _convert_line_ending(saved_text, self.line_ending)
            self.path.write_bytes(content.encode(self.encoding))
            if saved_text != self.text:
                self.text = saved_text
                self.replace_editor_text(saved_text)
            self.initial_text = self.text
            with contextlib.suppress(OSError):
                self._file_mtime = self.path.stat().st_mtime
            self.notify("File saved", severity="information")
            self.post_message(self.Saved(code_editor=self))
        except Exception as e:
            self.notify(f"Error saving file: {e}", severity="error")

    def action_save(self) -> None:
        """
        Save the current text to the file.
        """
        if self.path is None:
            self.action_save_as()
            return
        # Check for external changes before saving
        try:
            current_mtime = self.path.stat().st_mtime
        except OSError:
            current_mtime = None
        if (
            current_mtime is not None
            and self._file_mtime is not None
            and current_mtime != self._file_mtime
        ):

            def do_overwrite(result: OverwriteConfirmModalResult | None) -> None:
                if result is None or result.is_cancelled or not result.should_overwrite:
                    return
                self._write_to_disk()

            self.app.push_screen(OverwriteConfirmModalScreen(), do_overwrite)
            return
        self._write_to_disk()

    def action_save_as(self, *, on_complete: Callable | None = None) -> None:
        """
        Save the current text to a new file.
        """

        def do_save_as(result: SaveAsModalResult | None) -> None:
            if result is None or result.is_cancelled:
                if on_complete:
                    on_complete()
                return

            if result.file_path is None:
                self.notify("File path cannot be empty", severity="error")
                if on_complete:
                    on_complete()
                return

            new_path = Path(result.file_path).resolve()
            if new_path.exists():
                self.notify("File already exists", severity="error")
                if on_complete:
                    on_complete()
                return

            try:
                saved_text = self._apply_save_transformations(self.text)
                content = _convert_line_ending(saved_text, self.line_ending)
                new_path.write_bytes(content.encode(self.encoding))
                if saved_text != self.text:
                    self.text = saved_text
                    self.replace_editor_text(saved_text)
                self.initial_text = self.text
                self.path = new_path
                with contextlib.suppress(OSError):
                    self._file_mtime = new_path.stat().st_mtime
                self.post_message(
                    self.SavedAs(
                        code_editor=self,
                    )
                )
                self.notify(f"File saved: {self.path}", severity="information")
            except Exception as e:
                self.notify(f"Error saving file: {e}", severity="error")
                if on_complete:
                    on_complete()
                return

            if on_complete:
                on_complete()

        self.app.push_screen(SaveAsModalScreen(), do_save_as)
        return

    def action_close(
        self, *, on_complete: Callable[[bool], None] | None = None
    ) -> None:
        """
        Close the editor.
        """

        def do_unsaved_changes(result: UnsavedChangeModalResult | None) -> None:
            if result is None or result.is_cancelled:
                if on_complete:
                    on_complete(False)
                return

            if result.should_save is None:
                self.notify("Please select an option", severity="error")
                if on_complete:
                    on_complete(False)
                return

            if result.should_save:
                if self.path is None:
                    self.notify(
                        "Cannot save: no file path. Use 'Save As' first.",
                        severity="error",
                    )
                    if on_complete:
                        on_complete(False)
                    return
                self.action_save()
                if self.text == self.initial_text:
                    self.post_message(self.Closed(code_editor=self))
                    if on_complete:
                        on_complete(True)
                    return
                else:
                    if on_complete:
                        on_complete(False)
                    return
            else:
                self.post_message(self.Closed(code_editor=self))
                if on_complete:
                    on_complete(True)
                return

        if self.text != self.initial_text:
            self.app.push_screen(UnsavedChangeModalScreen(), do_unsaved_changes)
            return

        self.post_message(self.Closed(code_editor=self))
        if on_complete:
            on_complete(True)

    def action_delete(self) -> None:
        """
        Delete the file.
        """
        if not self.path:
            self.notify(
                "No file to delete. Please save the file first.", severity="error"
            )
            return

        def do_delete(result: DeleteFileModalResult | None) -> None:
            if not result or result.is_cancelled:
                return
            if not self.path:
                self.notify(
                    "No file to delete. Please save the file first.", severity="error"
                )
                return
            if result.should_delete:
                try:
                    self.path.unlink()
                    self.notify(f"File deleted: {self.path}", severity="information")
                    self.post_message(
                        self.Deleted(
                            code_editor=self,
                        )
                    )
                except Exception as e:
                    self.notify(f"Error deleting file: {e}", severity="error")

        assert self.path is not None
        self.app.push_screen(DeleteFileModalScreen(self.path), do_delete)

    def action_goto_line(self) -> None:
        """
        Open the Goto Line modal and move the cursor to the specified location.
        """

        def do_goto(result: GotoLineModalResult | None) -> None:
            if not result or result.is_cancelled or not result.value:
                return
            try:
                parts = result.value.split(":")
                row = int(parts[0]) - 1
                col = int(parts[1]) - 1 if len(parts) > 1 else 0
            except ValueError:
                self.notify(
                    "Invalid location format. Use 'line' or 'line:col'.",
                    severity="error",
                )
                return
            line_count = len(self.editor.document.lines)
            if row < 0 or row >= line_count:
                self.notify(
                    f"Line {row + 1} is out of range (1–{line_count}).",
                    severity="error",
                )
                return
            col = max(0, col)
            self.editor.cursor_location = (row, col)

        self.app.push_screen(GotoLineModalScreen(), do_goto)

    def action_find(self) -> None:
        """Show the inline find bar in find mode."""
        self._find_offset = None
        self.query_one(FindReplaceBar).show_find()

    def action_replace(self) -> None:
        """Show the inline find/replace bar in replace mode."""
        self._find_offset = None
        self.query_one(FindReplaceBar).show_replace()

    def on_find_replace_bar_find_next(self, event: FindReplaceBar.FindNext) -> None:
        if not event.query:
            return

        from textual.widgets.text_area import Selection

        query = event.query
        text = self.text

        # Use tracked offset for sequential finds; fall back to cursor position
        if self._find_offset is not None:
            cursor_offset = self._find_offset
        else:
            cursor_row, cursor_col = self.editor.cursor_location
            lines = text.split("\n")
            cursor_offset = (
                sum(len(lines[i]) + 1 for i in range(cursor_row)) + cursor_col
            )

        try:
            start_idx, end_idx = _find_next(
                text, query, cursor_offset, event.use_regex, event.case_sensitive
            )
        except re.error as e:
            self.notify(f"Invalid regex: {e}", severity="error")
            return

        if start_idx == -1:
            self._find_offset = None
            self.notify(f"'{query}' not found", severity="warning")
            return

        self._find_offset = end_idx
        self.editor.selection = Selection(
            start=_text_offset_to_location(text, start_idx),
            end=_text_offset_to_location(text, end_idx),
        )

    def on_find_replace_bar_find_previous(
        self, event: FindReplaceBar.FindPrevious
    ) -> None:
        if not event.query:
            return

        from textual.widgets.text_area import Selection

        query = event.query
        text = self.text

        # Use tracked offset for sequential finds; fall back to cursor position
        if self._find_offset is not None:
            cursor_offset = self._find_offset
        else:
            cursor_row, cursor_col = self.editor.cursor_location
            lines = text.split("\n")
            cursor_offset = (
                sum(len(lines[i]) + 1 for i in range(cursor_row)) + cursor_col
            )

        try:
            start_idx, end_idx = _find_previous(
                text, query, cursor_offset, event.use_regex, event.case_sensitive
            )
        except re.error as e:
            self.notify(f"Invalid regex: {e}", severity="error")
            return

        if start_idx == -1:
            self._find_offset = None
            self.notify(f"'{query}' not found", severity="warning")
            return

        self._find_offset = start_idx
        self.editor.selection = Selection(
            start=_text_offset_to_location(text, start_idx),
            end=_text_offset_to_location(text, end_idx),
        )

    def on_find_replace_bar_replace_all(self, event: FindReplaceBar.ReplaceAll) -> None:
        if not event.query:
            return

        find_query = event.query
        replacement = event.replacement
        use_regex = event.use_regex
        case_sensitive = event.case_sensitive
        flags = 0 if case_sensitive else re.IGNORECASE
        if use_regex:
            flags |= re.MULTILINE
        try:
            pattern = re.compile(
                find_query if use_regex else re.escape(find_query), flags
            )
            count = len(pattern.findall(self.text))
            if count == 0:
                self.notify(f"'{find_query}' not found", severity="warning")
                return
            # Replacement uses Python re.sub() syntax (\1, \2), not VSCode $1.
            new_text = pattern.sub(replacement, self.text)
        except re.error as e:
            self.notify(f"Invalid regex: {e}", severity="error")
            return
        self.replace_editor_text(new_text)
        self.notify(f"Replaced {count} occurrence(s)", severity="information")

    def on_find_replace_bar_replace_current(
        self, event: FindReplaceBar.ReplaceCurrent
    ) -> None:
        if not event.query:
            return

        from textual.widgets.text_area import Selection

        find_query = event.query
        replacement = event.replacement
        use_regex = event.use_regex
        case_sensitive = event.case_sensitive
        flags = 0 if case_sensitive else re.IGNORECASE
        if use_regex:
            flags |= re.MULTILINE

        sel = self.editor.selection
        text = self.text
        lines = text.split("\n")
        start_offset = (
            sum(len(lines[i]) + 1 for i in range(sel.start[0])) + sel.start[1]
        )
        end_offset = sum(len(lines[i]) + 1 for i in range(sel.end[0])) + sel.end[1]

        try:
            # Match against full text so lookaheads/lookbehinds can see context
            pattern = re.compile(
                find_query if use_regex else re.escape(find_query), flags
            )
            m = pattern.match(text, start_offset)
        except re.error as e:
            self.notify(f"Invalid regex: {e}", severity="error")
            return

        if m is not None and m.end() == end_offset:
            try:
                # Use match.expand() to process backreferences with full
                # text context — re.sub on isolated selected_text would
                # break lookaheads/lookbehinds that need surrounding text.
                rep = m.expand(replacement)
            except (re.error, IndexError):
                rep = replacement
            new_text = text[:start_offset] + rep + text[end_offset:]
            search_from = start_offset + len(rep)
            try:
                start_idx, end_idx = _find_next(
                    new_text, find_query, search_from, use_regex, case_sensitive
                )
            except re.error:
                start_idx = -1
                end_idx = -1
            self.replace_editor_text(new_text)
            if start_idx != -1:
                self.editor.selection = Selection(
                    start=_text_offset_to_location(new_text, start_idx),
                    end=_text_offset_to_location(new_text, end_idx),
                )
        else:
            cursor_row, cursor_col = self.editor.cursor_location
            lines = text.split("\n")
            cursor_offset = (
                sum(len(lines[i]) + 1 for i in range(cursor_row)) + cursor_col
            )
            try:
                start_idx, end_idx = _find_next(
                    text, find_query, cursor_offset, use_regex, case_sensitive
                )
            except re.error as e:
                self.notify(f"Invalid regex: {e}", severity="error")
                return
            if start_idx == -1:
                self.notify(f"'{find_query}' not found", severity="warning")
                return
            self.editor.selection = Selection(
                start=_text_offset_to_location(text, start_idx),
                end=_text_offset_to_location(text, end_idx),
            )

    def on_find_replace_bar_closed(self, event: FindReplaceBar.Closed) -> None:
        self._find_offset = None
        self.editor.focus()

    def on_find_replace_bar_select_all(self, event: FindReplaceBar.SelectAll) -> None:
        if not event.query:
            return

        text = self.text
        flags = 0 if event.case_sensitive else re.IGNORECASE
        if event.use_regex:
            flags |= re.MULTILINE
        try:
            pattern = re.compile(
                event.query if event.use_regex else re.escape(event.query), flags
            )
        except re.error as e:
            self.notify(f"Invalid regex: {e}", severity="error")
            return

        matches = list(pattern.finditer(text))
        count = self._apply_matches_as_cursors(matches, text)

        self._find_offset = None
        self.editor.focus()

        if count == 0:
            self.notify(f"'{event.query}' not found", severity="warning")
        elif count >= 2:
            self.notify(f"{count} occurrences selected")

    def action_change_language(self) -> None:
        """
        Open the Change Language modal and update the syntax highlighting language.
        """
        languages = sorted(
            set(self.LANGUAGE_EXTENSIONS.values())
            | set(self.LANGUAGE_FILENAMES.values())
        )

        def do_change(result: ChangeLanguageModalResult | None) -> None:
            if result is None or result.is_cancelled:
                return
            self.language = result.language

        self.app.push_screen(
            ChangeLanguageModalScreen(
                languages=languages,
                current_language=self.language,
            ),
            do_change,
        )

    def action_change_indent(self) -> None:
        """
        Open the Change Indentation modal and convert the file's indentation.
        """

        def do_change(result: ChangeIndentModalResult | None) -> None:
            if result is None or result.is_cancelled:
                return
            if result.indent_type is None or result.indent_size is None:
                return
            new_text = _convert_indentation(
                self.text, result.indent_type, result.indent_size
            )
            self.replace_editor_text(new_text)
            self.indent_type = result.indent_type
            self.indent_size = result.indent_size

        self.app.push_screen(
            ChangeIndentModalScreen(
                self.indent_type, self.indent_size, show_save_level=False
            ),
            do_change,
        )

    def action_change_line_ending(self) -> None:
        """
        Open the Change Line Ending modal and update the line ending style.
        """

        def do_change(result: ChangeLineEndingModalResult | None) -> None:
            if result is None or result.is_cancelled:
                return
            if result.line_ending is None:
                return
            self.line_ending = result.line_ending
            self._notify_non_lf_if_needed()

        self.app.push_screen(
            ChangeLineEndingModalScreen(
                current_line_ending=self.line_ending, show_save_level=False
            ),
            do_change,
        )

    def action_change_encoding(self) -> None:
        """
        Open the Change Encoding modal and update the file encoding.
        """

        def do_change(result: ChangeEncodingModalResult | None) -> None:
            if result is None or result.is_cancelled:
                return
            if result.encoding is None:
                return
            self.encoding = result.encoding

        self.app.push_screen(
            ChangeEncodingModalScreen(
                current_encoding=self.encoding, show_save_level=False
            ),
            do_change,
        )

    def action_focus(self) -> None:
        """
        Focus the editor.
        """
        self.editor.focus()

    @on(TextArea.Changed)
    def on_text_changed(self, event: TextArea.Changed):
        event.stop()

        # update the text when editor's text changes
        self.text = event.control.text
        # Recompute git diff using cached HEAD (no subprocess)
        self._recompute_git_diff()

    @on(TextArea.SelectionChanged)
    def on_selection_changed(self, event: TextArea.SelectionChanged):
        event.stop()
        self._notify_footer()

    @on(MultiCursorTextArea.CursorsChanged)
    def on_cursors_changed(self, event: MultiCursorTextArea.CursorsChanged):
        event.stop()
        self._notify_footer()
        # Reset Ctrl+D word mode when extra cursors are cleared (e.g. Escape)
        if not self.editor.extra_cursors:
            self._ctrl_d_query = ""

    @on(MultiCursorTextArea.ClipboardAction)
    def on_clipboard_action(self, event: MultiCursorTextArea.ClipboardAction) -> None:
        event.stop()
        self._notify_non_lf_if_needed(from_clipboard=True)

    def action_add_cursor_below(self) -> None:
        """Add an extra cursor one line below the primary cursor."""
        row, col = self.editor.cursor_location
        if row < self.editor.document.line_count - 1:
            self.editor.add_cursor((row + 1, col))

    def action_add_cursor_above(self) -> None:
        """Add an extra cursor one line above the primary cursor."""
        row, col = self.editor.cursor_location
        if row > 0:
            self.editor.add_cursor((row - 1, col))

    def _get_query_text(self) -> str:
        """Return selected text, or word under cursor if no selection."""
        sel = self.editor.selection
        if sel.start != sel.end:
            return self.editor.selected_text
        row, col = self.editor.cursor_location
        return _get_word_at_location(self.text, row, col)

    def _apply_matches_as_cursors(self, matches: list[re.Match], text: str) -> int:
        """Set primary selection to first match, add extra cursors for the rest.

        Zero-length matches are silently skipped.
        Returns the number of matches applied.
        """
        from textual.widgets.text_area import Selection

        self.editor.clear_extra_cursors()

        matches = [m for m in matches if m.start() < m.end()]
        if not matches:
            return 0

        first = matches[0]
        self.editor.selection = Selection(
            start=_text_offset_to_location(text, first.start()),
            end=_text_offset_to_location(text, first.end()),
        )

        for m in matches[1:]:
            self.editor.add_cursor(
                _text_offset_to_location(text, m.end()),
                anchor=_text_offset_to_location(text, m.start()),
            )

        return len(matches)

    def action_select_all_occurrences(self) -> None:
        """Select all occurrences of the current selection or word under cursor.

        Matching VSCode behavior:
        - From collapsed cursor: whole-word, case-sensitive matching.
        - From existing selection: substring, case-insensitive matching.
        """
        sel = self.editor.selection
        from_collapsed = sel.start == sel.end

        query = self._get_query_text()
        if not query:
            return

        text = self.text
        if from_collapsed:
            pattern = re.compile(_word_boundary_pattern(query))
        else:
            pattern = re.compile(re.escape(query), re.IGNORECASE)
        matches = list(pattern.finditer(text))
        count = self._apply_matches_as_cursors(matches, text)
        self._find_offset = None

        if count == 0:
            self.notify(f"'{query}' not found", severity="warning")
        elif count >= 2:
            self.notify(f"{count} occurrences selected")

    def action_select_next_occurrence(self) -> None:
        """Add a cursor at the next occurrence (VS Code Ctrl+D style).

        Two modes, matching VSCode behavior:
        - **Word mode** (from collapsed cursor): case-sensitive, whole-word
          boundary matching. Activated when Ctrl+D first selects a word.
        - **Substring mode** (from existing selection): case-insensitive,
          plain substring matching. Used when user has text selected.
        """
        from textual.widgets.text_area import Selection

        text = self.text
        query = self._get_query_text()
        if not query:
            return

        sel = self.editor.selection

        # Case 1: No selection — select word under cursor (word-boundary mode)
        if sel.start == sel.end:
            self._ctrl_d_query = query
            row, col = self.editor.cursor_location
            line_offset = _location_to_text_offset(text, (row, 0))
            for m in re.finditer(_word_boundary_pattern(query), text):
                if m.start() <= line_offset + col < m.end():
                    self.editor.selection = Selection(
                        start=_text_offset_to_location(text, m.start()),
                        end=_text_offset_to_location(text, m.end()),
                    )
                    return
            return

        # Case 2: Selection exists — find next occurrence
        # Reset word mode if the selected text changed (user selected manually)
        if self._ctrl_d_query and self.editor.selected_text != self._ctrl_d_query:
            self._ctrl_d_query = ""

        if self.editor.extra_cursors:
            last_cursor = self.editor.extra_cursors[-1]
            last_anchor = self.editor.extra_anchors[-1]
            search_from = _location_to_text_offset(text, max(last_cursor, last_anchor))
        else:
            search_from = _location_to_text_offset(text, max(sel.start, sel.end))

        if self._ctrl_d_query:
            start, end = _find_next(
                text,
                _word_boundary_pattern(query),
                search_from,
                use_regex=True,
                case_sensitive=True,
            )
        else:
            start, end = _find_next(text, query, search_from, case_sensitive=False)

        if start == -1:
            return

        match_start = _text_offset_to_location(text, start)
        match_end = _text_offset_to_location(text, end)

        # Check if match is already selected (primary or any extra cursor)
        primary_start = min(sel.start, sel.end)
        primary_end = max(sel.start, sel.end)
        if match_start == primary_start and match_end == primary_end:
            self.notify(
                "All occurrences already selected",
                severity="information",
            )
            return
        for ec, ea in zip(
            self.editor.extra_cursors,
            self.editor.extra_anchors,
            strict=True,
        ):
            if min(ec, ea) == match_start and max(ec, ea) == match_end:
                self.notify(
                    "All occurrences already selected",
                    severity="information",
                )
                return

        # Match extra cursor direction to primary selection
        cursor, anchor = (
            (match_start, match_end)
            if sel.start > sel.end
            else (match_end, match_start)
        )
        self.editor.add_cursor(cursor, anchor=anchor)
        self._scroll_to_location(cursor)

    def _scroll_to_location(self, location: tuple[int, int]) -> None:
        """Scroll the editor viewport to make *location* visible."""
        from textual.geometry import Region, Spacing

        x, y = self.editor.wrapped_document.location_to_offset(location)
        self.editor.scroll_to_region(
            Region(x, y, width=3, height=1),
            spacing=Spacing(right=self.editor.gutter_width),
            animate=False,
            force=True,
        )

    @property
    def editor(self) -> MultiCursorTextArea:
        return self.query_one(MultiCursorTextArea)

    @property
    def syntax_theme(self) -> str:
        """Return the current syntax highlighting theme."""
        return self._syntax_theme

    @syntax_theme.setter
    def syntax_theme(self, theme: str) -> None:
        """Set the syntax highlighting theme and update the editor."""
        self._syntax_theme = theme
        self.editor.theme = theme

    def capture_state(self) -> EditorState:
        """Serialize current editor state for lazy unmounting."""
        try:
            scroll = (int(self.editor.scroll_x), int(self.editor.scroll_y))
            cursor = self.editor.selection.end
        except Exception:
            scroll = (0, 0)
            cursor = (0, 0)
        state = EditorState(
            pane_id=self.pane_id,
            path=self.path,
            text=self.text,
            initial_text=self.initial_text,
            language=self.language,
            encoding=self.encoding,
            line_ending=self.line_ending,
            indent_type=self.indent_type,
            indent_size=self.indent_size,
            word_wrap=self.word_wrap,
            show_indentation_guides=self.show_indentation_guides,
            render_whitespace=self.render_whitespace,
            cursor_end=cursor,
            scroll_offset=scroll,
            file_mtime=self._file_mtime,
            ec_search_dirs=list(self._ec_search_dirs),
            ec_mtimes=dict(self._ec_mtimes),
            trim_trailing_whitespace=self._trim_trailing_whitespace,
            insert_final_newline=self._insert_final_newline,
            syntax_theme=self._syntax_theme,
            warn_line_ending=self._warn_line_ending,
            notified_copy_line_ending=self._notified_copy_line_ending,
            force_no_highlighting=self._force_no_highlighting,
        )
        log.debug("capture_state: pane=%s path=%s", state.pane_id, state.path)
        return state

    @classmethod
    def from_state(cls, state: EditorState) -> CodeEditor:
        """Create a CodeEditor from a captured EditorState (no file I/O)."""
        log.debug("from_state: pane=%s path=%s", state.pane_id, state.path)
        return cls(
            pane_id=state.pane_id,
            path=state.path,
            _from_state=state,
        )

    @staticmethod
    def save_from_state(state: EditorState) -> None:
        """Save an unmounted editor's state to disk.

        Applies save-time transformations and updates state.initial_text
        and state.file_mtime in place.
        """
        if state.path is None:
            return
        try:
            text = state.text
            if state.trim_trailing_whitespace is True:
                text = _trim_trailing_whitespace(text)
            if state.insert_final_newline is True:
                text = _insert_final_newline(text)
            elif state.insert_final_newline is False:
                text = _remove_final_newline(text)
            content = _convert_line_ending(text, state.line_ending)
            state.path.write_bytes(content.encode(state.encoding))
            if text != state.text:
                state.text = text
            state.initial_text = state.text
            with contextlib.suppress(OSError):
                state.file_mtime = state.path.stat().st_mtime
            log.debug("save_from_state: saved %s", state.path)
        except Exception as e:
            log.error("save_from_state: error saving %s: %s", state.path, e)
