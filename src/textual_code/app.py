import time
from collections.abc import Iterable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Literal

from textual import events, on
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding, BindingType
from textual.command import (
    CommandInput,
    CommandPalette,
    DiscoveryHit,
    Hit,
    Hits,
    Provider,
)
from textual.css.query import NoMatches
from textual.events import Ready
from textual.message import Message
from textual.screen import Screen

from textual_code.command_registry import bindings_for_context as _bindings_for_context
from textual_code.commands import (
    _read_workspace_directories,
    _read_workspace_files,
    _read_workspace_paths,
    create_create_file_or_dir_command_provider,
)
from textual_code.config import (
    DEFAULT_EDITOR_SETTINGS,
    FooterOrders,
    ShortcutDisplayEntry,
    get_keybindings_path,
    get_project_config_path,
    get_user_config_path,
    load_editor_settings,
    load_footer_orders,
    load_keybindings,
    load_shortcut_display,
    save_keybindings_file,
    save_project_editor_settings,
    save_user_editor_settings,
)
from textual_code.modals import (
    ChangeEncodingModalResult,
    ChangeEncodingModalScreen,
    ChangeIndentModalResult,
    ChangeIndentModalScreen,
    ChangeLineEndingModalResult,
    ChangeLineEndingModalScreen,
    ChangeSyntaxThemeModalResult,
    ChangeSyntaxThemeModalScreen,
    ChangeUIThemeModalResult,
    ChangeUIThemeModalScreen,
    ChangeWordWrapModalResult,
    ChangeWordWrapModalScreen,
    DeleteFileModalResult,
    DeleteFileModalScreen,
    ShowShortcutsScreen,
    SidebarResizeModalResult,
    SidebarResizeModalScreen,
    SplitResizeModalResult,
    SplitResizeModalScreen,
    UnsavedChangeQuitModalResult,
    UnsavedChangeQuitModalScreen,
)
from textual_code.widgets.code_editor import CodeEditor
from textual_code.widgets.explorer import Explorer
from textual_code.widgets.main_view import MainView
from textual_code.widgets.ordered_footer import OrderedFooter
from textual_code.widgets.sidebar import SIDEBAR_MIN_WIDTH, Sidebar
from textual_code.widgets.workspace_search import WorkspaceSearchPane

_KEY_DISPLAY_NAMES: dict[str, str] = {
    "backslash": "\\",
    "pageup": "PageUp",
    "pagedown": "PageDown",
}


def _pretty_key(key: str) -> str:
    """Format a Textual key string for display (e.g. ``ctrl+s`` → ``Ctrl+S``)."""
    parts = []
    for part in key.split("+"):
        if part in _KEY_DISPLAY_NAMES:
            parts.append(_KEY_DISPLAY_NAMES[part])
        elif part.islower():
            parts.append(part.capitalize())
        else:
            parts.append(part)
    return "+".join(parts)


def _validate_sidebar_width_setting(value: int | float | str) -> int | str | None:
    """Validate a sidebar_width setting value (no runtime context needed).

    Returns:
      int   - absolute cell width (>= SIDEBAR_MIN_WIDTH)
      str   - percentage string like "30%" (1% - 90%)
      None  - invalid value
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        n = int(value)
        return n if n >= SIDEBAR_MIN_WIDTH else None
    if isinstance(value, str):
        if value.endswith("%"):
            try:
                pct = int(value[:-1])
            except ValueError:
                return None
            return value if 1 <= pct <= 90 else None
        try:
            n = int(value)
        except ValueError:
            return None
        return n if n >= SIDEBAR_MIN_WIDTH else None
    return None


_MAX_COPY_SUFFIX = 1000


def _resolve_paste_name(target_dir: Path, name: str) -> Path:
    """Return a non-conflicting path in *target_dir* for *name*.

    If ``target_dir/name`` does not exist, returns it directly.
    Otherwise appends " copy", " copy 2", " copy 3", etc.
    For files with extensions the suffix is inserted before the extension:
      "file.py" → "file copy.py" → "file copy 2.py"
    """
    candidate = target_dir / name
    if not candidate.exists():
        return candidate

    stem = Path(name).stem
    suffix = Path(name).suffix  # e.g. ".py", or "" for dirs

    copy_name = f"{stem} copy{suffix}"
    candidate = target_dir / copy_name
    if not candidate.exists():
        return candidate

    for counter in range(2, _MAX_COPY_SUFFIX + 1):
        copy_name = f"{stem} copy {counter}{suffix}"
        candidate = target_dir / copy_name
        if not candidate.exists():
            return candidate

    raise RuntimeError(
        f"Could not find a free name for '{name}' in '{target_dir}' "
        f"after {_MAX_COPY_SUFFIX} attempts"
    )


def _parse_sidebar_resize(
    value: str, current_width: int, max_width: int
) -> int | str | None:
    """
    Parse a sidebar resize expression.

    Formats:
      "30"   → absolute 30 cells
      "+5"   → current + 5
      "-3"   → current - 3
      "30%"  → percentage string "30%"

    Returns:
      int   → absolute cell width (5 ≤ result ≤ max_width)
      str   → percentage string like "30%" (1% – 90%)
      None  → invalid or out-of-range input
    """
    value = value.strip()
    if not value:
        return None

    # Percentage
    if value.endswith("%"):
        try:
            pct = int(value[:-1])
        except ValueError:
            return None
        if pct < 1 or pct > 90:
            return None
        return f"{pct}%"

    # Relative
    if value.startswith(("+", "-")):
        try:
            delta = int(value)
        except ValueError:
            return None
        result = current_width + delta
        if result < SIDEBAR_MIN_WIDTH or result > max_width:
            return None
        return result

    # Absolute
    try:
        result = int(value)
    except ValueError:
        return None
    if result < SIDEBAR_MIN_WIDTH or result > max_width:
        return None
    return result


def _parse_split_resize(
    value: str, current_width: int, total_width: int
) -> int | str | None:
    """
    Parse a split view resize expression for the left panel.

    Formats:
      "50"   → absolute 50 cells
      "+10"  → current + 10
      "-5"   → current - 5
      "40%"  → percentage string "40%"

    Returns:
      int   → absolute cell width (10 ≤ result ≤ total_width - 10)
      str   → percentage string like "40%" (10% – 90%)
      None  → invalid or out-of-range input
    """
    value = value.strip()
    if not value:
        return None

    # Percentage
    if value.endswith("%"):
        try:
            pct = int(value[:-1])
        except ValueError:
            return None
        if pct < 10 or pct > 90:
            return None
        return f"{pct}%"

    # Relative
    if value.startswith(("+", "-")):
        try:
            delta = int(value)
        except ValueError:
            return None
        result = current_width + delta
        min_width = 10
        max_width = total_width - 10
        if result < min_width or result > max_width:
            return None
        return result

    # Absolute
    try:
        result = int(value)
    except ValueError:
        return None
    min_width = 10
    max_width = total_width - 10
    if result < min_width or result > max_width:
        return None
    return result


class TextualCode(App):
    """
    Textual Code app
    """

    @dataclass
    class ReloadExplorerRequested(Message):
        """
        Message to request reloading the explorer.
        """

    @dataclass
    class OpenFileRequested(Message):
        """
        Message to request opening a file in the code editor.
        """

        # the path to the file to open.
        path: Path

    @dataclass
    class CreateFileOrDirRequested(Message):
        """
        Message to request creating a new file or directory.
        """

        # the path to the file or directory to create.
        path: Path
        # if the path is a directory.
        is_dir: bool

    @dataclass
    class DeletePathWithPaletteRequested(Message):
        """
        Message to request deleting a file or directory via command palette.
        """

        # the path to the file or directory to delete.
        path: Path

    @dataclass
    class RenamePathWithPaletteRequested(Message):
        """
        Message to request renaming a file or directory via command palette.
        """

        # the path to the file or directory to rename.
        path: Path

    @dataclass
    class MovePathWithPaletteRequested(Message):
        """
        Message to request moving a file or directory via command palette.
        """

        # the path to the file or directory to move.
        path: Path

    @dataclass
    class MoveDestinationSelected(Message):
        """
        Message posted when a destination directory is selected for a move.
        """

        source_path: Path
        destination_dir: Path

    CSS_PATH = "style.tcss"

    BINDINGS = _bindings_for_context("app")

    def __init__(
        self,
        workspace_path: Path,
        with_open_file: Path | None,
        *args,
        user_config_path: Path | None = None,
        skip_sidebar: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._skip_sidebar = skip_sidebar

        # the workspace path to open the explorer
        self.workspace_path = workspace_path
        # the file path to open in the code editor
        # if provided, the file will be opened after the app is ready
        self.with_open_file = with_open_file
        self._user_config_path = user_config_path

        # load editor defaults from config files
        self._config_warnings: list[str] = []
        settings = load_editor_settings(
            workspace_path,
            user_config_path=user_config_path,
            warnings=self._config_warnings,
        )
        self.default_indent_type: str = str(settings["indent_type"])
        self.default_indent_size: int = int(settings["indent_size"])
        self.default_line_ending: str = str(settings["line_ending"])
        self.default_encoding: str = str(settings["encoding"])
        self.default_syntax_theme: str = str(settings.get("syntax_theme", "monokai"))
        self.default_word_wrap: bool = bool(settings.get("word_wrap", True))
        self.default_ui_theme: str = str(settings.get("ui_theme", "textual-dark"))
        self.default_warn_line_ending: bool = bool(
            settings.get("warn_line_ending", True)
        )
        self.default_show_hidden_files: bool = bool(
            settings.get("show_hidden_files", True)
        )
        self.default_dim_gitignored: bool = bool(settings.get("dim_gitignored", True))
        self.default_dim_hidden_files: bool = bool(
            settings.get("dim_hidden_files", False)
        )
        self.default_show_git_status: bool = bool(settings.get("show_git_status", True))
        self.default_show_indentation_guides: bool = bool(
            settings.get("show_indentation_guides", True)
        )
        _rw = str(settings.get("render_whitespace", "none"))
        _valid_rw = ("none", "all", "boundary", "trailing")
        self.default_render_whitespace: str = _rw if _rw in _valid_rw else "none"
        mode = str(settings.get("path_display_mode", "absolute"))
        self.default_path_display_mode: str = (
            mode if mode in ("absolute", "relative") else "absolute"
        )
        _default_sw = DEFAULT_EDITOR_SETTINGS["sidebar_width"]
        raw_sw = settings.get("sidebar_width", _default_sw)
        validated_sw = _validate_sidebar_width_setting(raw_sw)
        if validated_sw is not None:
            self.default_sidebar_width: int | str = validated_sw
        else:
            self.default_sidebar_width = _default_sw
            if raw_sw != _default_sw:
                self._sidebar_width_warning = (
                    f"Invalid sidebar_width in config: {raw_sw!r}. "
                    f"Using default ({_default_sw})."
                )
        self.theme = self.default_ui_theme

        # File clipboard for copy/cut/paste in explorer
        self._file_clipboard: tuple[Literal["copy", "cut"], Path] | None = None

        # load and apply custom keybindings and display preferences
        kb_path = get_keybindings_path(user_config_path) if user_config_path else None
        self._custom_keybindings: dict[str, str] = load_keybindings(
            kb_path, warnings=self._config_warnings
        )
        self._shortcut_display: dict[str, ShortcutDisplayEntry] = load_shortcut_display(
            kb_path, warnings=self._config_warnings
        )
        self._footer_orders: FooterOrders = load_footer_orders(
            kb_path, warnings=self._config_warnings
        )
        _patch_input_bindings()
        _apply_custom_keybindings(self._custom_keybindings)

        # Double Ctrl+Q force-quit: timestamp of last Ctrl+Q press
        self._last_ctrl_q_time: float = 0.0

    _FORCE_QUIT_INTERVAL = 1.0  # seconds

    async def on_event(self, event: events.Event) -> None:
        """Intercept Ctrl+Q for double-press force quit before forwarding.

        If Ctrl+Q is pressed twice within 1 second, exit immediately
        regardless of unsaved changes.  This is a safety mechanism to
        ensure the user can always quit even if the quit binding is
        misconfigured or removed.
        """
        if (
            isinstance(event, events.Key)
            and not event.is_forwarded
            and event.key == "ctrl+q"
        ):
            now = time.monotonic()
            if now - self._last_ctrl_q_time < self._FORCE_QUIT_INTERVAL:
                self.exit()
                return
            self._last_ctrl_q_time = now
        await super().on_event(event)

    def compose(self) -> ComposeResult:
        if not self._skip_sidebar:
            yield Sidebar(
                workspace_path=self.workspace_path,
                show_hidden_files=self.default_show_hidden_files,
                dim_gitignored=self.default_dim_gitignored,
                dim_hidden_files=self.default_dim_hidden_files,
                show_git_status=self.default_show_git_status,
                sidebar_width=self.default_sidebar_width,
            )
        yield MainView()
        yield OrderedFooter()

    @on(Ready)
    async def on_ready(self, event: Ready):
        from textual_code.widgets.code_editor import CodeEditorFooter

        footer = self.main_view.query_one(CodeEditorFooter)
        footer.path_display_mode = self.default_path_display_mode
        if hasattr(self, "_sidebar_width_warning"):
            self.notify(self._sidebar_width_warning, severity="warning")
        for msg in dict.fromkeys(self._config_warnings):
            self.notify(msg, severity="warning")
        # open the file in the code editor if provided as with_open_file
        if self.with_open_file is not None:
            await self.main_view.action_open_code_editor(
                path=self.with_open_file, focus=True
            )

    # Mapping from binding action names to their SystemCommand titles.
    def _hidden_palette_titles(self) -> set[str]:
        """Build set of SystemCommand titles that should be hidden."""
        from textual_code.command_registry import _REGISTRY_BY_ACTION

        hidden: set[str] = set()
        for action, entry in self._shortcut_display.items():
            if entry.palette is False:
                cmd = _REGISTRY_BY_ACTION.get(action)
                if cmd:
                    hidden.add(cmd.title)
        return hidden

    def action_command_palette(self) -> None:
        """Block command palette when a modal is already active (#34)."""
        if self.screen.is_modal:
            return
        super().action_command_palette()

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        hidden = self._hidden_palette_titles()
        for cmd in self._all_system_commands(screen):
            if cmd.title not in hidden:
                yield cmd

    def _all_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        from textual_code.command_registry import COMMAND_REGISTRY

        for entry in COMMAND_REGISTRY:
            if not entry.palette_callback:
                continue
            callback = getattr(self, entry.palette_callback, None)
            if callback is None:
                continue
            key = self._custom_keybindings.get(entry.action, entry.default_key)
            if key:
                pretty = _pretty_key(key)
                desc = f"{entry.description} ({pretty})"
            else:
                desc = entry.description
            yield SystemCommand(entry.title, desc, callback)

    def action_sort_lines_ascending_cmd(self) -> None:
        """Sort selected lines ascending via command palette."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.editor.action_sort_lines_ascending)
        else:
            self.notify("No file open.", severity="error")

    def action_sort_lines_descending_cmd(self) -> None:
        """Sort selected lines descending via command palette."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.editor.action_sort_lines_descending)
        else:
            self.notify("No file open.", severity="error")

    def action_transform_uppercase_cmd(self) -> None:
        """Transform selected text to uppercase via command palette."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.editor.action_transform_uppercase)
        else:
            self.notify("No file open.", severity="error")

    def action_transform_lowercase_cmd(self) -> None:
        """Transform selected text to lowercase via command palette."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.editor.action_transform_lowercase)
        else:
            self.notify("No file open.", severity="error")

    def action_transform_title_case_cmd(self) -> None:
        """Transform selected text to title case via command palette."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.editor.action_transform_title_case)
        else:
            self.notify("No file open.", severity="error")

    def action_transform_snake_case_cmd(self) -> None:
        """Transform selected text to snake_case via command palette."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.editor.action_transform_snake_case)
        else:
            self.notify("No file open.", severity="error")

    def action_transform_camel_case_cmd(self) -> None:
        """Transform selected text to camelCase via command palette."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.editor.action_transform_camel_case)
        else:
            self.notify("No file open.", severity="error")

    def action_transform_kebab_case_cmd(self) -> None:
        """Transform selected text to kebab-case via command palette."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.editor.action_transform_kebab_case)
        else:
            self.notify("No file open.", severity="error")

    def action_transform_pascal_case_cmd(self) -> None:
        """Transform selected text to PascalCase via command palette."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.editor.action_transform_pascal_case)
        else:
            self.notify("No file open.", severity="error")

    def action_find_in_workspace(self) -> None:
        """Open workspace search panel (Ctrl+Shift+F)."""
        self.main_view.action_find_in_workspace()

    def action_find_in_workspace_cmd(self) -> None:
        """Open workspace search panel via command palette."""
        self.call_next(self.action_find_in_workspace)

    @on(WorkspaceSearchPane.OpenFileAtLineRequested)
    async def on_open_file_at_line_requested(
        self, event: WorkspaceSearchPane.OpenFileAtLineRequested
    ) -> None:
        """Open a file and jump to the requested line from a workspace search result."""
        await self.main_view.action_open_code_editor(path=event.file_path, focus=True)
        if event.line_number > 0:
            editor = self.main_view.get_active_code_editor()
            if editor is not None:
                row = event.line_number - 1
                line_count = len(editor.editor.document.lines)
                if 0 <= row < line_count:
                    editor.editor.cursor_location = (row, 0)

    def action_open_markdown_preview_tab_cmd(self) -> None:
        """Open markdown preview as tab from command palette."""
        self.call_next(self.main_view.action_open_markdown_preview_tab)

    def action_move_tab_to_other_split_cmd(self) -> None:
        """Move current tab to the other split via command palette."""
        self.call_next(self.main_view.action_move_tab_to_other_split)

    def action_move_tab_left_cmd(self) -> None:
        self.call_next(self.main_view.action_move_tab_left)

    def action_move_tab_right_cmd(self) -> None:
        self.call_next(self.main_view.action_move_tab_right)

    def action_move_tab_up_cmd(self) -> None:
        self.call_next(self.main_view.action_move_tab_up)

    def action_move_tab_down_cmd(self) -> None:
        self.call_next(self.main_view.action_move_tab_down)

    def action_reorder_tab_right_cmd(self) -> None:
        self.call_next(self.main_view.action_reorder_tab_right)

    def action_reorder_tab_left_cmd(self) -> None:
        self.call_next(self.main_view.action_reorder_tab_left)

    def _save_config(self, save_fn, *args) -> None:
        """Call a config save function and notify on failure."""
        if not save_fn(*args):
            self.notify("Failed to save settings", severity="error")

    def _save_editor_settings(self, save_level: str) -> None:
        """Build and persist editor settings at the given level."""
        settings = self._build_editor_settings()
        if save_level == "project":
            self._save_config(
                save_project_editor_settings,
                settings,
                self.workspace_path,
            )
        else:
            self._save_config(
                save_user_editor_settings,
                settings,
                self._user_config_path,
            )

    def _build_editor_settings(self) -> dict[str, str | int | bool]:
        """Build the current editor settings dict for saving to config."""
        return {
            "indent_type": self.default_indent_type,
            "indent_size": self.default_indent_size,
            "line_ending": self.default_line_ending,
            "encoding": self.default_encoding,
            "syntax_theme": self.default_syntax_theme,
            "word_wrap": self.default_word_wrap,
            "ui_theme": self.default_ui_theme,
            "warn_line_ending": self.default_warn_line_ending,
            "show_hidden_files": self.default_show_hidden_files,
            "path_display_mode": self.default_path_display_mode,
            "dim_gitignored": self.default_dim_gitignored,
            "dim_hidden_files": self.default_dim_hidden_files,
            "show_git_status": self.default_show_git_status,
            "show_indentation_guides": self.default_show_indentation_guides,
            "render_whitespace": self.default_render_whitespace,
            "sidebar_width": self.default_sidebar_width,
        }

    def action_set_default_indentation(self) -> None:
        """Set the default indentation for new files and save to config."""

        def do_change(result: ChangeIndentModalResult | None) -> None:
            if result and not result.is_cancelled:
                self.default_indent_type = (
                    result.indent_type or self.default_indent_type
                )
                self.default_indent_size = (
                    result.indent_size or self.default_indent_size
                )
                self._save_editor_settings(result.save_level)

        self.call_next(
            lambda: self.push_screen(
                ChangeIndentModalScreen(
                    self.default_indent_type, self.default_indent_size
                ),
                do_change,
            )
        )

    def action_set_default_line_ending(self) -> None:
        """Set the default line ending for new files and save to config."""

        def do_change(result: ChangeLineEndingModalResult | None) -> None:
            if result and not result.is_cancelled:
                self.default_line_ending = (
                    result.line_ending or self.default_line_ending
                )
                self._save_editor_settings(result.save_level)

        self.call_next(
            lambda: self.push_screen(
                ChangeLineEndingModalScreen(
                    current_line_ending=self.default_line_ending
                ),
                do_change,
            )
        )

    def action_set_default_encoding(self) -> None:
        """Set the default encoding for new files and save to config."""

        def do_change(result: ChangeEncodingModalResult | None) -> None:
            if result and not result.is_cancelled:
                self.default_encoding = result.encoding or self.default_encoding
                self._save_editor_settings(result.save_level)

        self.call_next(
            lambda: self.push_screen(
                ChangeEncodingModalScreen(current_encoding=self.default_encoding),
                do_change,
            )
        )

    def action_set_syntax_theme(self) -> None:
        """Set the syntax highlighting theme and apply it to all open editors."""

        def do_change(result: ChangeSyntaxThemeModalResult | None) -> None:
            if result and not result.is_cancelled and result.theme:
                self.default_syntax_theme = result.theme
                for editor in self.query(CodeEditor):
                    editor.syntax_theme = result.theme
                self._save_editor_settings(result.save_level)

        self.call_next(
            lambda: self.push_screen(
                ChangeSyntaxThemeModalScreen(current_theme=self.default_syntax_theme),
                do_change,
            )
        )

    def action_add_cursor_below_cmd(self) -> None:
        """Add cursor below via command palette."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.action_add_cursor_below)
        else:
            self.notify("No file open.", severity="error")

    def action_add_cursor_above_cmd(self) -> None:
        """Add cursor above via command palette."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.action_add_cursor_above)
        else:
            self.notify("No file open.", severity="error")

    def action_select_all_occurrences_cmd(self) -> None:
        """Select all occurrences via command palette."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.action_select_all_occurrences)
        else:
            self.notify("No file open.", severity="error")

    def action_add_next_occurrence_cmd(self) -> None:
        """Add next occurrence via command palette."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.action_select_next_occurrence)
        else:
            self.notify("No file open.", severity="error")

    # ── TextArea palette wrappers ────────────────────────────────────────

    def _run_text_area_action(self, action_name: str) -> None:
        """Dispatch a TextArea action from the command palette."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(getattr(code_editor.editor, action_name))
        else:
            self.notify("No file open.", severity="error")

    def action_redo_cmd(self) -> None:
        self._run_text_area_action("action_redo")

    def action_select_all_text_cmd(self) -> None:
        self._run_text_area_action("action_select_all")

    def action_indent_line_cmd(self) -> None:
        self._run_text_area_action("action_indent_line")

    def action_dedent_line_cmd(self) -> None:
        self._run_text_area_action("action_dedent_line")

    def action_move_line_up_cmd(self) -> None:
        self._run_text_area_action("action_move_line_up")

    def action_move_line_down_cmd(self) -> None:
        self._run_text_area_action("action_move_line_down")

    def action_scroll_viewport_up_cmd(self) -> None:
        self._run_text_area_action("action_scroll_viewport_up")

    def action_scroll_viewport_down_cmd(self) -> None:
        self._run_text_area_action("action_scroll_viewport_down")

    def action_toggle_split_vertical_cmd(self) -> None:
        """Toggle split orientation via command palette."""
        self.call_next(self.main_view.action_toggle_split_vertical)

    def action_toggle_word_wrap_cmd(self) -> None:
        """Toggle word wrap for the active file via command palette."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.action_toggle_word_wrap)
        else:
            self.notify("No file open.", severity="error")

    def action_toggle_indentation_guides_cmd(self) -> None:
        """Toggle indentation guides for the active file via command palette."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.action_toggle_indentation_guides)
        else:
            self.notify("No file open.", severity="error")

    def _apply_render_whitespace(self, mode: str) -> None:
        """Apply a render whitespace mode to the active editor."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            code_editor.render_whitespace = mode
            self.default_render_whitespace = mode
            self.notify(f"Render whitespace: {mode}")
        else:
            self.notify("No file open.", severity="error")

    def action_set_render_whitespace_cmd(self) -> None:
        """Open a command palette to select whitespace rendering mode."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is None:
            self.notify("No file open.", severity="error")
            return
        current_mode = code_editor.render_whitespace
        apply_fn = self._apply_render_whitespace
        modes = CodeEditor._RENDER_WHITESPACE_MODES
        items = [(f"{m} (current)" if m == current_mode else m, m) for m in modes]

        class _RenderWhitespaceProvider(Provider):
            async def discover(self) -> Hits:
                for label, m in items:
                    yield DiscoveryHit(
                        label,
                        partial(apply_fn, m),
                        help=f"Set whitespace rendering to {m}",
                    )

            async def search(self, query: str) -> Hits:
                matcher = self.matcher(query)
                for label, m in items:
                    score = matcher.match(label)
                    if score > 0:
                        yield Hit(
                            score,
                            matcher.highlight(label),
                            partial(apply_fn, m),
                            help=f"Set whitespace rendering to {m}",
                        )

        self.call_next(
            lambda: self.push_screen(
                CommandPalette(
                    providers=[_RenderWhitespaceProvider],
                    placeholder="Select render whitespace mode...",
                ),
            )
        )

    def action_set_default_word_wrap(self) -> None:
        """Set default word wrap for new files and save to config."""

        def do_change(result: ChangeWordWrapModalResult | None) -> None:
            if result and not result.is_cancelled and result.word_wrap is not None:
                self.default_word_wrap = result.word_wrap
                self._save_editor_settings(result.save_level)

        self.call_next(
            lambda: self.push_screen(
                ChangeWordWrapModalScreen(current_word_wrap=self.default_word_wrap),
                do_change,
            )
        )

    def _toggle_explorer_tree_setting(
        self, tree_attr: str, new_value: bool, label: str, on_text: str, off_text: str
    ) -> None:
        """Toggle an explorer tree setting, save config, and notify."""
        sb = self.sidebar
        if sb is not None:
            tree = sb.explorer.directory_tree
            setattr(tree, tree_attr, new_value)
            tree.reload()
        self._save_editor_settings("user")
        state = on_text if new_value else off_text
        self.notify(f"{label}: {state}")

    def action_toggle_hidden_files_cmd(self) -> None:
        """Toggle hidden files visibility in the explorer and save to config."""
        self.default_show_hidden_files = not self.default_show_hidden_files
        self._toggle_explorer_tree_setting(
            "show_hidden_files",
            self.default_show_hidden_files,
            "Hidden files",
            "visible",
            "hidden",
        )

    def action_toggle_path_display_mode_cmd(self) -> None:
        """Toggle between absolute and relative path display in footer."""
        from textual_code.widgets.code_editor import CodeEditorFooter

        self.default_path_display_mode = (
            "relative" if self.default_path_display_mode == "absolute" else "absolute"
        )
        footer = self.main_view.query_one(CodeEditorFooter)
        footer.path_display_mode = self.default_path_display_mode
        self._save_editor_settings("user")
        self.notify(f"Path display: {self.default_path_display_mode}")

    def action_toggle_dim_gitignored_cmd(self) -> None:
        """Toggle dim gitignored files in the explorer and save to config."""
        self.default_dim_gitignored = not self.default_dim_gitignored
        self._toggle_explorer_tree_setting(
            "dim_gitignored",
            self.default_dim_gitignored,
            "Gitignored files",
            "dimmed",
            "normal",
        )

    def action_toggle_dim_hidden_files_cmd(self) -> None:
        """Toggle dim hidden files in the explorer and save to config."""
        self.default_dim_hidden_files = not self.default_dim_hidden_files
        self._toggle_explorer_tree_setting(
            "dim_hidden_files",
            self.default_dim_hidden_files,
            "Hidden files",
            "dimmed",
            "normal",
        )

    def action_toggle_show_git_status_cmd(self) -> None:
        """Toggle git status highlighting in the explorer and save to config."""
        self.default_show_git_status = not self.default_show_git_status
        self._toggle_explorer_tree_setting(
            "show_git_status",
            self.default_show_git_status,
            "Git status highlighting",
            "enabled",
            "disabled",
        )

    @property
    def _resolved_user_config_path(self) -> Path:
        """Return the effective user config path (custom or platform default)."""
        return self._user_config_path or get_user_config_path()

    def action_copy_relative_path(self) -> None:
        """Copy the relative file path to clipboard."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is None or code_editor.path is None:
            self.notify("No saved file open.", severity="error")
            return
        try:
            rel = code_editor.path.relative_to(self.workspace_path)
            self.copy_to_clipboard(rel.as_posix())
            self.notify(f"Copied: {rel.as_posix()}")
        except ValueError:
            self.copy_to_clipboard(str(code_editor.path))
            self.notify(f"Copied absolute path: {code_editor.path}")

    def action_copy_absolute_path(self) -> None:
        """Copy the absolute file path to clipboard."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is None or code_editor.path is None:
            self.notify("No saved file open.", severity="error")
            return
        self.copy_to_clipboard(str(code_editor.path))
        self.notify(f"Copied: {code_editor.path}")

    def action_copy_displayed_path(self) -> None:
        """Copy the currently displayed path (respects path_display_mode)."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is None or code_editor.path is None:
            self.notify("No saved file open.", severity="error")
            return
        if self.default_path_display_mode == "relative":
            try:
                displayed = code_editor.path.relative_to(self.workspace_path).as_posix()
            except ValueError:
                displayed = str(code_editor.path)
        else:
            displayed = str(code_editor.path)
        self.copy_to_clipboard(displayed)
        self.notify(f"Copied: {displayed}")

    def _ensure_config_file(self, path: Path) -> bool:
        """Create config file if missing. Returns False on I/O error."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive create avoids overwriting a file created concurrently
            with open(path, "x"):
                pass
        except FileExistsError:
            pass
        except OSError as e:
            self.notify(f"Cannot create settings file: {e}", severity="error")
            return False
        return True

    def action_open_user_settings(self) -> None:
        """Open user settings file in the editor."""
        path = self._resolved_user_config_path
        if not self._ensure_config_file(path):
            return
        self.call_next(
            partial(self.main_view.action_open_code_editor, path=path, focus=True)
        )

    def action_open_project_settings(self) -> None:
        """Open project settings file in the editor."""
        path = get_project_config_path(self.workspace_path)
        if not self._ensure_config_file(path):
            return
        self.call_next(
            partial(self.main_view.action_open_code_editor, path=path, focus=True)
        )

    def action_open_keybindings(self) -> None:
        """Open keybindings config file in the editor."""
        path = self._keybindings_path()
        if not self._ensure_config_file(path):
            return
        self.call_next(
            partial(self.main_view.action_open_code_editor, path=path, focus=True)
        )

    def action_set_ui_theme(self) -> None:
        """Set the UI theme."""

        def do_change(result: ChangeUIThemeModalResult | None) -> None:
            if result and not result.is_cancelled and result.theme:
                self.default_ui_theme = result.theme
                self.theme = result.theme
                self._save_editor_settings(result.save_level)

        self.call_next(
            lambda: self.push_screen(
                ChangeUIThemeModalScreen(current_theme=self.default_ui_theme),
                do_change,
            )
        )

    def action_split_right_cmd(self) -> None:
        """Split editor right via command palette."""
        self.call_next(self.main_view.action_split_right)

    def action_split_left_cmd(self) -> None:
        """Split editor left via command palette."""
        self.call_next(self.main_view.action_split_left)

    def action_split_down_cmd(self) -> None:
        """Split editor down via command palette."""
        self.call_next(self.main_view.action_split_down)

    def action_split_up_cmd(self) -> None:
        """Split editor up via command palette."""
        self.call_next(self.main_view.action_split_up)

    def action_close_split_cmd(self) -> None:
        """Close split via command palette."""
        self.call_next(self.main_view.action_close_split)

    def action_focus_left_split_cmd(self) -> None:
        """Focus left split via command palette."""
        self.main_view.action_focus_left_split()

    def action_focus_right_split_cmd(self) -> None:
        """Focus right split via command palette."""
        self.main_view.action_focus_right_split()

    def action_focus_next_split_cmd(self) -> None:
        """Focus next split via command palette."""
        self.main_view.action_focus_next_split()

    def action_focus_prev_split_cmd(self) -> None:
        """Focus previous split via command palette."""
        self.main_view.action_focus_prev_split()

    def action_goto_line_cmd(self) -> None:
        """
        Open the Goto Line modal via command palette.
        """
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.action_goto_line)
        else:
            self.notify("No file open.", severity="error")

    def action_change_language_cmd(self) -> None:
        """
        Open the Change Language modal via command palette.
        """
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.action_change_language)
        else:
            self.notify("No file open.", severity="error")

    def action_find_cmd(self) -> None:
        """
        Open the Find modal via command palette.
        """
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.action_find)
        else:
            self.notify("No file open.", severity="error")

    def action_replace_cmd(self) -> None:
        """
        Open the Replace modal via command palette.
        """
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.action_replace)
        else:
            self.notify("No file open.", severity="error")

    def action_change_indent_cmd(self) -> None:
        """
        Open the Change Indentation modal via command palette.
        """
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.action_change_indent)
        else:
            self.notify("No file open.", severity="error")

    def action_change_line_ending_cmd(self) -> None:
        """
        Open the Change Line Ending modal via command palette.
        """
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.action_change_line_ending)
        else:
            self.notify("No file open.", severity="error")

    def action_change_encoding_cmd(self) -> None:
        """
        Open the Change Encoding modal via command palette.
        """
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.action_change_encoding)
        else:
            self.notify("No file open.", severity="error")

    def action_reload_file_cmd(self) -> None:
        """Reload current file via command palette."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.action_reload_file)
        else:
            self.notify("No file open.", severity="error")

    def action_resize_sidebar_cmd(self) -> None:
        """Open the Resize Sidebar modal via command palette."""

        def on_result(result: SidebarResizeModalResult | None) -> None:
            if result is None or result.is_cancelled:
                return
            sb = self.sidebar
            if sb is None:
                return
            current_width = sb.size.width
            max_width = self.size.width - 5
            parsed = _parse_sidebar_resize(result.value or "", current_width, max_width)
            if parsed is None:
                self.notify(
                    f"Invalid sidebar width: {result.value!r}. "
                    "Use a number (30), +/-offset (+5), or percent (30%).",
                    severity="error",
                )
                return
            sb.styles.width = parsed

        self.call_next(lambda: self.push_screen(SidebarResizeModalScreen(), on_result))

    def action_resize_split_cmd(self) -> None:
        """Open the Resize Split modal via command palette."""
        if not self.main_view._split_visible:
            self.notify("No split view open.", severity="error")
            return

        def on_result(result: SplitResizeModalResult | None) -> None:
            if result is None or result.is_cancelled:
                return
            from textual_code.widgets.draggable_tabs_content import (
                DraggableTabbedContent,
            )
            from textual_code.widgets.split_container import SplitContainer
            from textual_code.widgets.split_tree import all_leaves

            leaves = all_leaves(self.main_view._split_root)
            if len(leaves) < 2:
                return
            first_dtc = self.main_view.query_one(
                f"#{leaves[0].leaf_id}", DraggableTabbedContent
            )
            containers = list(self.main_view.query(SplitContainer))
            if not containers:
                return
            split_container = containers[0]
            current_width = first_dtc.size.width
            total_width = split_container.size.width
            parsed = _parse_split_resize(result.value or "", current_width, total_width)
            if parsed is None:
                self.notify(
                    f"Invalid split width: {result.value!r}. "
                    "Use a number (50), +/-offset (+10), or percent (40%).",
                    severity="error",
                )
                return
            first_dtc.styles.width = parsed

        self.call_next(lambda: self.push_screen(SplitResizeModalScreen(), on_result))

    def action_save_all_files(self) -> None:
        """Save all open files."""
        self.call_next(self.main_view.action_save_all)

    def action_close_all_files(self) -> None:
        """Close all open files."""
        self.call_next(self.main_view.action_close_all)

    def action_toggle_sidebar(self) -> None:
        """
        Toggle the sidebar visibility.
        """
        sb = self.sidebar
        if sb is not None:
            sb.display = not sb.display

    def action_reload_explorer(self) -> None:
        """
        Reload the explorer directory tree.
        """
        from textual_code.modals import PathSearchModal

        PathSearchModal.invalidate_cache(self.workspace_path)
        if self.sidebar is None:
            return
        # call with call_next to ensure the command palette is closed
        self.call_next(self.sidebar.explorer.directory_tree.reload)

    def action_save_file(self) -> None:
        """
        Save the file in the active code editor.
        """
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            # call with call_next to ensure the command palette is closed
            self.call_next(code_editor.action_save)
        else:
            self.notify("No file to save. Please open a file first.", severity="error")

    def action_save_file_as(self) -> None:
        """
        Save the file in the active code editor as a new file.
        """
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            # call with call_next to ensure the command palette is closed
            self.call_next(code_editor.action_save_as)
        else:
            self.notify("No file to save. Please open a file first.", severity="error")

    async def action_new_editor(self) -> None:
        """
        Open a new code editor with an empty file.
        """
        # call with call_next to ensure the command palette is closed
        self.call_next(
            partial(self.main_view.action_open_code_editor, path=None, focus=True)
        )

    def action_close_file(self) -> None:
        """
        Close the file in the active code editor.
        """
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            # call with call_next to ensure the command palette is closed
            self.call_next(code_editor.action_close)
        else:
            self.notify("No file to close. Please open a file first.", severity="error")

    def action_delete_file(self) -> None:
        """
        Delete the file in the active code editor.
        """
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            # call with call_next to ensure the command palette is closed
            self.call_next(code_editor.action_delete)
        else:
            self.notify(
                "No file to delete. Please open a file first.", severity="error"
            )

    def action_open_file_with_command_palette(self) -> None:
        """
        Open a file in the code editor with the command palette.
        """
        from textual_code.modals import PathSearchModal

        def _on_result(path: Path | None) -> None:
            if path is not None:
                self.post_message(
                    self.OpenFileRequested(path=self.workspace_path / path)
                )

        self.push_screen(
            PathSearchModal(
                self.workspace_path,
                scan_func=_read_workspace_files,
                cache_key="files",
                placeholder="Search for files...",
            ),
            callback=_on_result,
        )

    def _get_explorer_selected_dir_relative(self) -> str:
        """Get the relative path of the explorer's selected directory."""
        sidebar = self.sidebar
        if sidebar is None:
            return ""
        return sidebar.explorer._get_selected_dir_relative()

    async def _push_palette_with_prefill(
        self, palette: CommandPalette, initial_path: str = ""
    ) -> None:
        """Push a command palette and optionally pre-fill its input."""
        if not initial_path:
            initial_path = self._get_explorer_selected_dir_relative()
        await self.push_screen(palette)
        if initial_path:
            try:
                inp = palette.query_one(CommandInput)
                inp.value = initial_path
                inp.cursor_position = len(initial_path)
            except NoMatches:
                pass

    async def action_create_file_with_command_palette(
        self, initial_path: str = ""
    ) -> None:
        """
        Create a new file with the command palette.
        """
        palette = CommandPalette(
            providers=[
                create_create_file_or_dir_command_provider(
                    self.workspace_path,
                    is_dir=False,
                    post_message_callback=lambda path: self.app.post_message(
                        self.CreateFileOrDirRequested(path=path, is_dir=False)
                    ),
                )
            ],
            placeholder="Enter file path...",
        )
        await self._push_palette_with_prefill(palette, initial_path)

    def _push_path_search(
        self,
        message_cls: type,
        placeholder: str,
    ) -> None:
        """Open PathSearchModal for workspace paths, post message_cls on selection."""
        from textual_code.modals import PathSearchModal

        def _on_result(path: Path | None) -> None:
            if path is not None:
                self.post_message(message_cls(path=path))

        self.push_screen(
            PathSearchModal(
                self.workspace_path,
                scan_func=_read_workspace_paths,
                cache_key="paths",
                placeholder=placeholder,
            ),
            callback=_on_result,
        )

    def action_delete_file_or_dir_with_command_palette(self) -> None:
        """Delete a file or directory with the command palette."""
        self._push_path_search(
            self.DeletePathWithPaletteRequested, "Delete file or directory..."
        )

    async def action_create_directory_with_command_palette(
        self, initial_path: str = ""
    ) -> None:
        """
        Create a new directory with the command palette.
        """
        palette = CommandPalette(
            providers=[
                create_create_file_or_dir_command_provider(
                    self.workspace_path,
                    is_dir=True,
                    post_message_callback=lambda path: self.app.post_message(
                        self.CreateFileOrDirRequested(path=path, is_dir=True)
                    ),
                )
            ],
            placeholder="Enter directory path...",
        )
        await self._push_palette_with_prefill(palette, initial_path)

    def action_rename_file_or_dir_with_command_palette(self) -> None:
        """Rename a file or directory with the command palette."""
        self._push_path_search(
            self.RenamePathWithPaletteRequested, "Rename file or directory..."
        )

    def action_rename_active_file(self) -> None:
        """Rename the active file in the editor."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is None or code_editor.path is None:
            self.notify(
                "No file to rename. Please save the file first.", severity="error"
            )
            return
        self._handle_rename_path(code_editor.path)

    def _handle_rename_path(self, path: Path) -> None:
        """Open rename modal and perform the rename on confirmation."""
        from textual_code.modals import RenameModalResult, RenameModalScreen

        current_name = path.name
        is_directory = path.is_dir()

        def do_rename(result: RenameModalResult | None) -> None:
            if not result or result.is_cancelled or not result.new_name:
                return
            new_name = result.new_name.strip()
            if not new_name or new_name == current_name:
                return
            # Reject path separators and traversal
            new_path = path.parent / new_name
            if new_name != new_path.name:
                self.notify(
                    "Invalid name: must not contain path separators.",
                    severity="error",
                )
                return
            if new_path.exists():
                self.notify(f"'{new_name}' already exists.", severity="error")
                return
            try:
                path.rename(new_path)
            except Exception as e:
                self.notify(f"Error renaming '{current_name}': {e}", severity="error")
                return

            self._update_open_tabs_after_rename(path, new_path, is_directory)
            self.action_reload_explorer()
            self.log.info("Renamed: %s → %s", path, new_path)
            self.notify(f"Renamed to '{new_name}'", severity="information")

        self.push_screen(RenameModalScreen(current_name), do_rename)

    def action_move_active_file(self) -> None:
        """Move the active file in the editor to a new path."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is None or code_editor.path is None:
            self.notify(
                "No file to move. Please save the file first.", severity="error"
            )
            return
        self._handle_move_path(code_editor.path)

    def action_move_file_or_dir_with_command_palette(self) -> None:
        """Move a file or directory with the command palette."""
        self._push_path_search(
            self.MovePathWithPaletteRequested, "Move file or directory..."
        )

    def action_copy_explorer_node(self) -> None:
        """Copy the selected explorer node via command palette."""
        if self.sidebar is None:
            return
        self.sidebar.explorer.action_copy_node()

    def action_cut_explorer_node(self) -> None:
        """Cut the selected explorer node via command palette."""
        if self.sidebar is None:
            return
        self.sidebar.explorer.action_cut_node()

    def action_paste_explorer_node(self) -> None:
        """Paste from clipboard to the explorer location via command palette."""
        if self.sidebar is None:
            return
        self.sidebar.explorer.action_paste_node()

    def _handle_move_path(self, path: Path) -> None:
        """Open directory picker for moving a file or directory."""
        from textual_code.modals import PathSearchModal

        name = path.name
        is_source_dir = path.is_dir()

        def _exclude_source(d: Path) -> bool:
            """Filter out source directory and its subtree."""
            if is_source_dir:
                try:
                    d.relative_to(path)
                    return False
                except ValueError:
                    pass
            return True

        def _on_result(dest_dir: Path | None) -> None:
            if dest_dir is not None:
                self.post_message(
                    self.MoveDestinationSelected(
                        source_path=path, destination_dir=dest_dir
                    )
                )

        self.push_screen(
            PathSearchModal(
                self.workspace_path,
                scan_func=_read_workspace_directories,
                cache_key="dirs",
                placeholder=f"Move '{name}' to...",
                path_filter=_exclude_source,
            ),
            callback=_on_result,
        )

    @on(MoveDestinationSelected)
    def on_move_destination_selected(self, event: MoveDestinationSelected) -> None:
        """Handle destination directory selection and perform the move."""
        import shutil

        path = event.source_path
        dest_dir = event.destination_dir
        is_directory = path.is_dir()
        ws_resolved = self.workspace_path.resolve()
        source_resolved = path.resolve()
        new_path = (dest_dir / path.name).resolve()

        self.log.info("Move requested: %s → %s/%s", path, dest_dir, path.name)

        # Validate destination is within workspace
        try:
            new_path.relative_to(ws_resolved)
        except ValueError:
            self.log.warning(
                "Move rejected: destination '%s' is outside workspace", dest_dir
            )
            self.notify("Destination must be within the workspace.", severity="error")
            return

        # Defense-in-depth: reject moving a directory into its own subtree
        if is_directory:
            try:
                dest_dir.resolve().relative_to(source_resolved)
                self.log.warning(
                    "Move rejected: cannot move '%s' into its own subdirectory",
                    path.name,
                )
                self.notify(
                    f"Cannot move '{path.name}' into its own subdirectory.",
                    severity="error",
                )
                return
            except ValueError:
                pass  # not a subtree — OK

        if new_path == source_resolved:
            return  # no-op

        if new_path.exists():
            try:
                dest_relative = str(dest_dir.relative_to(self.workspace_path))
            except ValueError:
                dest_relative = str(dest_dir)
            self.log.warning(
                "Move rejected: '%s' already exists in '%s'",
                path.name,
                dest_relative,
            )
            self.notify(
                f"'{path.name}' already exists in '{dest_relative}'.",
                severity="error",
            )
            return

        try:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(new_path))
        except Exception as e:
            self.log.warning("Move failed: %s → %s: %s", path, new_path, e)
            self.notify(f"Error moving: {e}", severity="error")
            return

        self._update_open_tabs_after_rename(path, new_path, is_directory)
        self.action_reload_explorer()
        try:
            new_relative = str(new_path.relative_to(self.workspace_path))
        except ValueError:
            new_relative = str(new_path)
        self.log.info("Moved: %s → %s", path, new_path)
        self.notify(f"Moved to '{new_relative}'", severity="information")

    def _update_open_tabs_after_rename(
        self, old_path: Path, new_path: Path, is_directory: bool
    ) -> None:
        """Update open tabs and preview panes after a rename."""
        from textual_code.widgets.split_tree import all_leaves

        updated = 0
        for leaf in all_leaves(self.main_view._split_root):
            updates: list[tuple[Path, Path, str]] = []
            for file_path, pane_id in list(leaf.opened_files.items()):
                if is_directory:
                    try:
                        rel = file_path.relative_to(old_path)
                        updates.append((file_path, new_path / rel, pane_id))
                    except ValueError:
                        continue
                else:
                    if file_path == old_path:
                        updates.append((file_path, new_path, pane_id))
            for old_fp, new_fp, pane_id in updates:
                del leaf.opened_files[old_fp]
                leaf.opened_files[new_fp] = pane_id
                tc = self.main_view._tc_for_pane(pane_id)
                if tc is not None:
                    pane = tc.get_pane(pane_id)
                    editors = pane.query(CodeEditor)
                    if editors:
                        editors.first(CodeEditor).path = new_fp
                updated += 1

        # Update preview pane tracking
        preview_updates: dict[Path, Path] = {}
        for fp in list(self.main_view._preview_pane_ids):
            if is_directory:
                try:
                    rel = fp.relative_to(old_path)
                    preview_updates[fp] = new_path / rel
                except ValueError:
                    continue
            elif fp == old_path:
                preview_updates[fp] = new_path
        for old_fp, new_fp in preview_updates.items():
            pid = self.main_view._preview_pane_ids.pop(old_fp)
            self.main_view._preview_pane_ids[new_fp] = pid
            # Also remap pending debounce timers
            timer = self.main_view._preview_update_timers.pop(old_fp, None)
            if timer is not None:
                self.main_view._preview_update_timers[new_fp] = timer

        self.log.info("Updated %d open tab(s) after rename", updated)

    async def action_quit(self) -> None:
        """
        Quit the app.
        """
        if self.main_view.has_unsaved_pane():

            def do_force_quit(
                result: UnsavedChangeQuitModalResult | None,
            ) -> None:
                if result is None or not result.should_quit:
                    return
                self.exit()

            self.push_screen(UnsavedChangeQuitModalScreen(), do_force_quit)
            return
        self.exit()

    @on(DeletePathWithPaletteRequested)
    def on_delete_path_with_palette_requested(
        self, event: DeletePathWithPaletteRequested
    ) -> None:
        import shutil

        path = event.path

        def do_delete(result: DeleteFileModalResult | None) -> None:
            if not result or result.is_cancelled or not result.should_delete:
                return
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
            except Exception as e:
                self.notify(f"Error deleting: {e}", severity="error")
                return

            pane_id = self.main_view.pane_id_from_path(path)
            if pane_id:
                self.call_next(
                    partial(self.main_view.action_close_code_editor, pane_id)
                )

            self.action_reload_explorer()
            self.notify(f"Deleted: {path.name}", severity="information")

        self.push_screen(DeleteFileModalScreen(path), do_delete)

    @on(Explorer.FileDeleteRequested)
    def on_explorer_file_delete_requested(
        self, event: Explorer.FileDeleteRequested
    ) -> None:
        import shutil

        path = event.path

        def do_delete(result: DeleteFileModalResult | None) -> None:
            if not result or result.is_cancelled or not result.should_delete:
                return
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
            except Exception as e:
                self.notify(f"Error deleting: {e}", severity="error")
                return

            # close the tab if the deleted file is open
            pane_id = self.main_view.pane_id_from_path(path)
            if pane_id:
                self.call_next(
                    partial(self.main_view.action_close_code_editor, pane_id)
                )

            self.action_reload_explorer()
            self.notify(f"Deleted: {path.name}", severity="information")

        self.push_screen(DeleteFileModalScreen(path), do_delete)

    @on(Explorer.FileRenameRequested)
    def on_explorer_file_rename_requested(
        self, event: Explorer.FileRenameRequested
    ) -> None:
        self._handle_rename_path(event.path)

    @on(RenamePathWithPaletteRequested)
    def on_rename_path_with_palette_requested(
        self, event: RenamePathWithPaletteRequested
    ) -> None:
        self._handle_rename_path(event.path)

    @on(Explorer.FileMoveRequested)
    def on_explorer_file_move_requested(
        self, event: Explorer.FileMoveRequested
    ) -> None:
        self._handle_move_path(event.path)

    @on(MovePathWithPaletteRequested)
    def on_move_path_with_palette_requested(
        self, event: MovePathWithPaletteRequested
    ) -> None:
        self._handle_move_path(event.path)

    @on(Explorer.FileCopyRequested)
    def on_explorer_file_copy_requested(
        self, event: Explorer.FileCopyRequested
    ) -> None:
        self._file_clipboard = ("copy", event.path)
        self.log.info("File copied to clipboard: %s", event.path)
        self.notify(f"Copied: {event.path.name}")

    @on(Explorer.FileCutRequested)
    def on_explorer_file_cut_requested(self, event: Explorer.FileCutRequested) -> None:
        self._file_clipboard = ("cut", event.path)
        self.log.info("File cut to clipboard: %s", event.path)
        self.notify(f"Cut: {event.path.name}")

    @on(Explorer.FilePasteRequested)
    def on_explorer_file_paste_requested(
        self, event: Explorer.FilePasteRequested
    ) -> None:
        import shutil

        if self._file_clipboard is None:
            self.notify("Nothing to paste.", severity="warning")
            return

        operation, source_path = self._file_clipboard
        target_dir = event.target_dir

        # Validate source still exists
        if not source_path.exists():
            self.log.warning("Paste failed: source no longer exists: %s", source_path)
            self.notify(
                f"Source no longer exists: {source_path.name}", severity="error"
            )
            self._file_clipboard = None
            return

        is_directory = source_path.is_dir()
        ws_resolved = self.workspace_path.resolve()

        # Validate destination is within workspace
        try:
            target_dir.resolve().relative_to(ws_resolved)
        except ValueError:
            self.log.warning(
                "Paste rejected: target '%s' is outside workspace", target_dir
            )
            self.notify("Destination must be within the workspace.", severity="error")
            return

        # Prevent pasting a directory into itself
        if is_directory:
            try:
                target_dir.resolve().relative_to(source_path.resolve())
                self.log.warning(
                    "Paste rejected: cannot paste '%s' into itself", source_path.name
                )
                self.notify(
                    f"Cannot paste '{source_path.name}' into itself.",
                    severity="error",
                )
                return
            except ValueError:
                pass  # not a subtree — OK

        # Resolve destination name (handle conflicts)
        dest_path = _resolve_paste_name(target_dir, source_path.name)

        self.log.info("Paste %s: %s → %s", operation, source_path, dest_path)

        try:
            if operation == "copy":
                if is_directory:
                    shutil.copytree(str(source_path), str(dest_path))
                else:
                    shutil.copy2(str(source_path), str(dest_path))
                # Copy keeps clipboard intact (can paste again)
            else:  # cut
                shutil.move(str(source_path), str(dest_path))
                self._update_open_tabs_after_rename(
                    source_path, dest_path, is_directory
                )
                self._file_clipboard = None
        except Exception as e:
            self.log.warning("Paste failed: %s → %s: %s", source_path, dest_path, e)
            self.notify(f"Error pasting: {e}", severity="error")
            return

        self.action_reload_explorer()
        try:
            dest_relative = str(dest_path.relative_to(self.workspace_path))
        except ValueError:
            dest_relative = str(dest_path)

        if operation == "copy":
            self.notify(f"Copied to '{dest_relative}'", severity="information")
        else:
            self.notify(f"Moved to '{dest_relative}'", severity="information")

    @on(MainView.ActiveFileChanged)
    def on_active_file_changed(self, event: MainView.ActiveFileChanged) -> None:
        if self.sidebar is not None:
            self.sidebar.explorer.select_file(event.path)

    @on(Explorer.FileOpenRequested)
    async def on_file_open_requested(self, event: Explorer.FileOpenRequested):
        # open the file in the code editor when requested from the explorer
        await self.main_view.action_open_code_editor(path=event.path, focus=True)

    @on(CodeEditor.Saved)
    @on(CodeEditor.SavedAs)
    @on(CodeEditor.Deleted)
    def on_file_changed(
        self, event: CodeEditor.Saved | CodeEditor.SavedAs | CodeEditor.Deleted
    ):
        # reload the explorer when a file is saved or deleted
        self.action_reload_explorer()

    @on(ReloadExplorerRequested)
    def on_reload_explorer_requested(self, event: ReloadExplorerRequested):
        # reload the explorer when requested
        self.action_reload_explorer()

    def on_filtered_directory_tree_workspace_changed(self, event) -> None:
        """Invalidate workspace caches when the explorer detects external changes."""
        from textual_code.modals import PathSearchModal

        PathSearchModal.invalidate_cache(self.workspace_path)

    @on(OpenFileRequested)
    async def on_open_file_requested(self, event: OpenFileRequested):
        # open the file in the code editor when requested
        await self.main_view.action_open_code_editor(path=event.path, focus=True)

    @on(CreateFileOrDirRequested)
    async def on_create_file_or_dir_requested(self, event: CreateFileOrDirRequested):
        # check if the file or directory already exists
        if event.path.exists():
            self.notify(
                f"{'Directory' if event.is_dir else 'File'}"
                f" already exists: {event.path}",
                severity="error",
            )
            return

        # create the file or directory
        if not event.is_dir:
            try:
                event.path.touch()
            except Exception as e:
                self.notify(
                    f"Failed to create file: {event.path}: {e}", severity="error"
                )
                return
        else:
            try:
                event.path.mkdir(parents=True)
            except Exception as e:
                self.notify(
                    f"Failed to create directory: {event.path}: {e}", severity="error"
                )
                return

        # reload the explorer after creating the file or directory
        self.action_reload_explorer()

        # open the file in the code editor if it is a file
        if not event.is_dir:
            await self.main_view.action_open_code_editor(path=event.path, focus=True)

    @property
    def main_view(self) -> MainView:
        # Use the base screen so this works even when a modal is active
        return self.screen_stack[0].query_one(MainView)

    def action_show_shortcuts(self) -> None:
        """Open the keyboard shortcuts panel showing ALL registry commands."""
        from textual_code.command_registry import COMMAND_REGISTRY

        context_labels = {"app": "App", "editor": "Editor", "text_area": "Editor"}
        rows: list[tuple[str, str, str, str]] = []
        for entry in COMMAND_REGISTRY:
            key = self._custom_keybindings.get(entry.action, entry.default_key)
            display_key = _pretty_key(key) if key else "(none)"
            rows.append(
                (display_key, entry.title, context_labels[entry.context], entry.action)
            )
        self.push_screen(ShowShortcutsScreen(rows, self._shortcut_display))

    def _collect_bindings_for_area(self, area: str) -> list[tuple[str, str, str, bool]]:
        """Collect (action, description, key, show) tuples for a given area."""
        from textual_code.widgets.explorer import Explorer
        from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

        area_binding_sources: dict[str, list[list[Binding]]] = {
            "editor": [
                MainView.BINDINGS,
                TextualCode.BINDINGS,
                MultiCursorTextArea.BINDINGS,
            ],
            "explorer": [Explorer.BINDINGS, TextualCode.BINDINGS],
            "search": [TextualCode.BINDINGS],
            "image_preview": [TextualCode.BINDINGS],
            "markdown_preview": [TextualCode.BINDINGS],
        }
        binding_lists = area_binding_sources.get(area, [TextualCode.BINDINGS])

        # For preview areas, also include MainView's "close" binding
        include_close = area in ("image_preview", "markdown_preview")

        actions: list[tuple[str, str, str, bool]] = []
        seen: set[str] = set()
        for bindings in binding_lists:
            for b in bindings:
                if b.description and b.action not in seen:
                    seen.add(b.action)
                    actions.append((b.action, b.description, b.key, b.show))
        if include_close:
            for b in MainView.BINDINGS:
                if b.action == "close" and b.action not in seen:
                    seen.add(b.action)
                    actions.append((b.action, b.description, b.key, b.show))
        return actions

    def action_configure_footer(self) -> None:
        """Open the footer configuration modal."""
        from textual_code.config import KNOWN_AREAS
        from textual_code.modals import FooterConfigResult, FooterConfigScreen

        area = self._get_focused_area()
        all_area_actions: dict[str, list[tuple[str, str, str, bool]]] = {}
        for a in KNOWN_AREAS:
            all_area_actions[a] = self._collect_bindings_for_area(a)

        def _on_result(result: FooterConfigResult | None) -> None:
            if result and not result.is_cancelled and result.order is not None:
                self.set_footer_order(result.order, result.area)

        self.push_screen(
            FooterConfigScreen(
                all_area_actions, self._footer_orders, initial_area=area
            ),
            _on_result,
        )

    def _keybindings_path(self) -> Path:
        """Return the keybindings config file path."""
        return (
            get_keybindings_path(self._user_config_path)
            if self._user_config_path
            else get_keybindings_path()
        )

    def set_keybinding(self, action: str, new_key: str) -> None:
        """Save a custom keybinding and apply it immediately."""
        self._custom_keybindings[action] = new_key
        self._save_keybindings_to_disk()
        _apply_custom_keybindings(self._custom_keybindings)
        self.notify("Shortcut saved. Restart to apply changes.")

    def set_shortcut_display(self, action: str, entry: ShortcutDisplayEntry) -> None:
        """Save shortcut display preferences and apply immediately."""
        self._shortcut_display[action] = entry
        self._save_keybindings_to_disk()
        self.notify("Display settings saved.")

    def _get_focused_area(self) -> str:
        """Return the footer area name based on the currently focused widget."""
        from textual_code.widgets.explorer import Explorer
        from textual_code.widgets.image_preview import ImagePreviewPane
        from textual_code.widgets.markdown_preview import MarkdownPreviewPane
        from textual_code.widgets.workspace_search import WorkspaceSearchPane

        focused = self.focused
        if focused is not None:
            for ancestor in focused.ancestors_with_self:
                if isinstance(ancestor, Explorer):
                    return "explorer"
                if isinstance(ancestor, WorkspaceSearchPane):
                    return "search"
                if isinstance(ancestor, ImagePreviewPane):
                    return "image_preview"
                if isinstance(ancestor, MarkdownPreviewPane):
                    return "markdown_preview"
                if isinstance(ancestor, Sidebar):
                    # Focus is in the sidebar (e.g. on tabs) but not in a
                    # specific pane.  Determine area from the active tab.
                    try:
                        active_id = ancestor.tabbed_content.active
                    except (AttributeError, ValueError):
                        return "explorer"
                    if active_id == "search_pane":
                        return "search"
                    return "explorer"
        return "editor"

    def set_footer_order(self, order: list[str], area: str) -> None:
        """Save footer order for *area* and recompose footer immediately."""
        self._footer_orders.set_area(area, order)
        self._save_keybindings_to_disk()
        import contextlib

        with contextlib.suppress(Exception):
            self.footer.refresh(recompose=True)
        self.notify("Footer order saved.")

    def get_footer_order(self) -> list[str]:
        """Return the footer order for the currently focused area.

        Always returns a non-empty list: custom order → DEFAULT_ACTION_ORDERS fallback.
        """
        area = self._get_focused_area()
        custom = self._footer_orders.for_area(area)
        if custom is not None:
            return custom
        default = OrderedFooter.DEFAULT_ACTION_ORDERS.get(
            area, OrderedFooter.ACTION_ORDER
        )
        return list(default)

    def get_footer_priority(self, action: str) -> int:
        """Return the footer display priority for an action.

        Uses the order for the currently focused area.
        """
        order = self.get_footer_order()
        try:
            return order.index(action)
        except ValueError:
            return len(order)

    def _save_keybindings_to_disk(self) -> None:
        """Persist all keybinding-related config sections atomically."""
        ok = save_keybindings_file(
            self._custom_keybindings,
            self._shortcut_display,
            self._keybindings_path(),
            footer_orders=self._footer_orders,
        )
        if not ok:
            self.notify("Failed to save settings", severity="error")

    @property
    def sidebar(self) -> Sidebar | None:
        if self._skip_sidebar:
            return None
        # Use the base screen so this works even when a modal is active
        if not self.screen_stack:
            return None
        return self.screen_stack[0].query_one(Sidebar)

    @property
    def footer(self) -> OrderedFooter:
        return self.query_one(OrderedFooter)


_input_bindings_patched = False


def _patch_input_bindings() -> None:
    """Remap Input widget bindings for standard editing shortcuts.

    - ctrl+a: select_all (instead of home)
    - ctrl+d: removed (no action; Delete key still works for delete_right)
    """
    global _input_bindings_patched
    if _input_bindings_patched:
        return
    _input_bindings_patched = True

    from textual.widgets import Input

    # Expected binding keys to patch (tied to Textual's Input.BINDINGS layout).
    # If Textual changes these, the patch silently becomes a no-op.
    patches = {
        ("home,ctrl+a", "home"): "home",
        ("delete,ctrl+d", "delete_right"): "delete",
    }
    applied: set[str] = set()

    new_bindings: list[BindingType] = []
    for b in Input.BINDINGS:
        if not isinstance(b, Binding):
            new_bindings.append(b)
            continue
        new_key = patches.get((b.key, b.action))
        if new_key is not None:
            new_bindings.append(Binding(new_key, b.action, b.description, show=b.show))
            applied.add(b.key)
        else:
            new_bindings.append(b)
    new_bindings.append(Binding("ctrl+a", "select_all", "Select all", show=False))
    Input.BINDINGS = new_bindings
    # Refresh the cached binding map so new instances use the patched bindings
    Input._merged_bindings = Input._merge_bindings()


def _apply_custom_keybindings(custom: dict[str, str]) -> None:
    """Regenerate class-level BINDINGS from the registry with custom overrides."""
    from textual_code.command_registry import bindings_for_context
    from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

    for context, cls in (
        ("app", TextualCode),
        ("editor", MainView),
        ("text_area", MultiCursorTextArea),
    ):
        cls.BINDINGS = bindings_for_context(context, custom=custom)
