from collections.abc import Iterable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Literal

from textual import on
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.command import CommandInput, CommandPalette
from textual.css.query import NoMatches
from textual.events import Ready
from textual.message import Message
from textual.screen import Screen

from textual_code.commands import (
    create_create_file_or_dir_command_provider,
    create_delete_path_command_provider,
    create_move_path_command_provider,
    create_open_file_command_provider,
    create_rename_path_command_provider,
)
from textual_code.config import (
    DEFAULT_EDITOR_SETTINGS,
    get_keybindings_path,
    get_project_config_path,
    get_user_config_path,
    load_editor_settings,
    load_keybindings,
    save_keybindings,
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

# Textual's built-in "Theme" command title — used to filter it out from command palette.
# This string matches the title yielded by textual.app.App.get_system_commands().
_TEXTUAL_BUILTIN_THEME_CMD = "Theme"


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

    BINDINGS = [
        Binding("ctrl+n", "new_editor", "New file"),
        Binding("ctrl+b", "toggle_sidebar", "Toggle sidebar"),
        Binding(
            "ctrl+shift+f",
            "find_in_workspace",
            "Find in Workspace",
            show=False,
        ),
        Binding("f1", "show_shortcuts", "Keyboard shortcuts", show=False),
        Binding("f6", "focus_next", "Next widget", show=False, priority=True),
        Binding(
            "shift+f6", "focus_previous", "Previous widget", show=False, priority=True
        ),
    ]

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
        settings = load_editor_settings(
            workspace_path, user_config_path=user_config_path
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

        # load and apply custom keybindings
        kb_path = get_keybindings_path(user_config_path) if user_config_path else None
        self._custom_keybindings: dict[str, str] = load_keybindings(kb_path)
        _apply_custom_keybindings(self._custom_keybindings)

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
        # open the file in the code editor if provided as with_open_file
        if self.with_open_file is not None:
            await self.main_view.action_open_code_editor(
                path=self.with_open_file, focus=True
            )

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        for cmd in super().get_system_commands(screen):
            if cmd.title != _TEXTUAL_BUILTIN_THEME_CMD:
                yield cmd
        yield SystemCommand(
            "Show keyboard shortcuts",
            "View and change keyboard shortcuts (F1)",
            self.action_show_shortcuts,
        )
        yield SystemCommand(
            "Open user settings",
            "Open user settings file (~/.config/textual-code/settings.toml)",
            self.action_open_user_settings,
        )
        yield SystemCommand(
            "Open project settings",
            "Open project settings file (.textual-code.toml in workspace root)",
            self.action_open_project_settings,
        )
        yield SystemCommand(
            "Toggle sidebar",
            "Show or hide the sidebar (Ctrl+B)",
            self.action_toggle_sidebar,
        )
        yield SystemCommand(
            "Reload explorer", "Reload the explorer", self.action_reload_explorer
        )
        yield SystemCommand(
            "Save file", "Save the current file (Ctrl+S)", self.action_save_file
        )
        yield SystemCommand(
            "Save all files",
            "Save all open files (Ctrl+Shift+S)",
            self.action_save_all_files,
        )
        yield SystemCommand(
            "Save file as",
            "Save the current file as new file",
            self.action_save_file_as,
        )
        yield SystemCommand(
            "New file", "Open empty code editor (Ctrl+N)", self.action_new_editor
        )
        yield SystemCommand(
            "Close file", "Close the current file (Ctrl+W)", self.action_close_file
        )
        yield SystemCommand(
            "Close all files",
            "Close all open files (Ctrl+Shift+W)",
            self.action_close_all_files,
        )
        yield SystemCommand(
            "Delete file", "Delete the current file", self.action_delete_file
        )
        yield SystemCommand(
            "Rename file",
            "Rename the current file (F2)",
            self.action_rename_active_file,
        )
        yield SystemCommand(
            "Copy relative path",
            "Copy the relative file path to clipboard",
            self.action_copy_relative_path,
        )
        yield SystemCommand(
            "Copy absolute path",
            "Copy the absolute file path to clipboard",
            self.action_copy_absolute_path,
        )
        yield SystemCommand(
            "Open file",
            "Open a file in the code editor",
            self.action_open_file_with_command_palette,
        )
        yield SystemCommand(
            "Create file",
            "Create a new file at a path",
            self.action_create_file_with_command_palette,
        )
        yield SystemCommand(
            "Create directory",
            "Create a new directory at a path",
            self.action_create_directory_with_command_palette,
        )
        yield SystemCommand("Open folder", "Quit the app", self.action_quit)
        yield SystemCommand(
            "Goto line",
            "Go to a specific line and column (Ctrl+G)",
            self.action_goto_line_cmd,
        )
        yield SystemCommand(
            "Change language",
            "Change the syntax highlighting language",
            self.action_change_language_cmd,
        )
        yield SystemCommand(
            "Find",
            "Find text in the current file (Ctrl+F)",
            self.action_find_cmd,
        )
        yield SystemCommand(
            "Replace",
            "Find and replace text in the current file (Ctrl+H)",
            self.action_replace_cmd,
        )
        yield SystemCommand(
            "Delete file or directory",
            "Delete a file or directory from the workspace",
            self.action_delete_file_or_dir_with_command_palette,
        )
        yield SystemCommand(
            "Rename file or directory",
            "Rename a file or directory in the workspace (F2)",
            self.action_rename_file_or_dir_with_command_palette,
        )
        yield SystemCommand(
            "Move file",
            "Move the current file to a different path",
            self.action_move_active_file,
        )
        yield SystemCommand(
            "Move file or directory",
            "Move a file or directory to a different path",
            self.action_move_file_or_dir_with_command_palette,
        )
        yield SystemCommand(
            "Copy file or directory",
            "Copy the selected file or directory in the explorer (Ctrl+C)",
            self.action_copy_explorer_node,
        )
        yield SystemCommand(
            "Cut file or directory",
            "Cut the selected file or directory in the explorer (Ctrl+X)",
            self.action_cut_explorer_node,
        )
        yield SystemCommand(
            "Paste file or directory",
            "Paste the copied/cut file or directory (Ctrl+V)",
            self.action_paste_explorer_node,
        )
        yield SystemCommand(
            "Change Indentation",
            "Change indentation style and size",
            self.action_change_indent_cmd,
        )
        yield SystemCommand(
            "Change Line Ending",
            "Change the line ending style (LF, CRLF, CR)",
            self.action_change_line_ending_cmd,
        )
        yield SystemCommand(
            "Change Encoding",
            "Change the file encoding (UTF-8, UTF-8 BOM, UTF-16, Latin-1)",
            self.action_change_encoding_cmd,
        )
        yield SystemCommand(
            "Reload file",
            "Reload the current file from disk",
            self.action_reload_file_cmd,
        )
        yield SystemCommand(
            "Resize sidebar",
            "Set the sidebar width (e.g. 30, +5, -3, 30%)",
            self.action_resize_sidebar_cmd,
        )
        yield SystemCommand(
            "Resize split",
            "Set the left split panel width (e.g. 50, +10, -5, 40%)",
            self.action_resize_split_cmd,
        )
        yield SystemCommand(
            "Add cursor below",
            "Add an extra cursor one line below (Ctrl+Alt+Down)",
            self.action_add_cursor_below_cmd,
        )
        yield SystemCommand(
            "Add cursor above",
            "Add an extra cursor one line above (Ctrl+Alt+Up)",
            self.action_add_cursor_above_cmd,
        )
        yield SystemCommand(
            "Select all occurrences",
            "Select all occurrences of the current selection or word (Ctrl+Shift+L)",
            self.action_select_all_occurrences_cmd,
        )
        yield SystemCommand(
            "Add next occurrence",
            "Add a cursor at the next occurrence of the selection or word (Ctrl+D)",
            self.action_add_next_occurrence_cmd,
        )
        yield SystemCommand(
            "Split editor right",
            "Open current file in a new split to the right (Ctrl+\\)",
            self.action_split_right_cmd,
        )
        yield SystemCommand(
            "Split editor left",
            "Open current file in a new split to the left",
            self.action_split_left_cmd,
        )
        yield SystemCommand(
            "Split editor down",
            "Open current file in a new split below",
            self.action_split_down_cmd,
        )
        yield SystemCommand(
            "Split editor up",
            "Open current file in a new split above",
            self.action_split_up_cmd,
        )
        yield SystemCommand(
            "Close split",
            "Close the current split panel (Ctrl+Shift+\\)",
            self.action_close_split_cmd,
        )
        yield SystemCommand(
            "Focus next split",
            "Move focus to the next split panel",
            self.action_focus_next_split_cmd,
        )
        yield SystemCommand(
            "Focus previous split",
            "Move focus to the previous split panel",
            self.action_focus_prev_split_cmd,
        )
        yield SystemCommand(
            "Set default indentation",
            "Set the default indentation for new files",
            self.action_set_default_indentation,
        )
        yield SystemCommand(
            "Set default line ending",
            "Set the default line ending for new files",
            self.action_set_default_line_ending,
        )
        yield SystemCommand(
            "Set default encoding",
            "Set the default encoding for new files",
            self.action_set_default_encoding,
        )
        yield SystemCommand(
            "Change syntax highlighting theme",
            "Select the syntax highlighting theme for the editor",
            self.action_set_syntax_theme,
        )
        yield SystemCommand(
            "Open markdown preview as tab",
            "Open a live markdown preview in a new tab (Ctrl+Shift+M)",
            self.action_open_markdown_preview_tab_cmd,
        )
        yield SystemCommand(
            "Move tab to other split",
            "Move the current tab to the other split panel (Ctrl+Alt+\\)",
            self.action_move_tab_to_other_split_cmd,
        )
        yield SystemCommand(
            "Move tab left",
            "Move the current tab to the split pane on the left",
            self.action_move_tab_left_cmd,
        )
        yield SystemCommand(
            "Move tab right",
            "Move the current tab to the split pane on the right",
            self.action_move_tab_right_cmd,
        )
        yield SystemCommand(
            "Move tab up",
            "Move the current tab to the split pane above",
            self.action_move_tab_up_cmd,
        )
        yield SystemCommand(
            "Move tab down",
            "Move the current tab to the split pane below",
            self.action_move_tab_down_cmd,
        )
        yield SystemCommand(
            "Reorder tab right",
            "Move the current tab one position to the right",
            self.action_reorder_tab_right_cmd,
        )
        yield SystemCommand(
            "Reorder tab left",
            "Move the current tab one position to the left",
            self.action_reorder_tab_left_cmd,
        )
        yield SystemCommand(
            "Find in Workspace",
            "Search all files in the workspace (Ctrl+Shift+F)",
            self.action_find_in_workspace_cmd,
        )
        yield SystemCommand(
            "Toggle split orientation",
            "Switch between horizontal and vertical split layout",
            self.action_toggle_split_vertical_cmd,
        )
        yield SystemCommand(
            "Toggle word wrap",
            "Toggle word wrap for the active file",
            self._toggle_word_wrap_cmd,
        )
        yield SystemCommand(
            "Set default word wrap",
            "Toggle default word wrap for new files",
            self.action_set_default_word_wrap,
        )
        yield SystemCommand(
            "Change UI theme",
            "Select the UI theme",
            self.action_set_ui_theme,
        )
        yield SystemCommand(
            "Toggle hidden files",
            "Show or hide hidden files in the explorer",
            self._toggle_hidden_files_cmd,
        )
        yield SystemCommand(
            "Toggle path display mode",
            "Switch between absolute and relative path in footer",
            self._toggle_path_display_mode_cmd,
        )
        yield SystemCommand(
            "Toggle dim gitignored files",
            "Dim or un-dim gitignored files in the explorer",
            self._toggle_dim_gitignored_cmd,
        )
        yield SystemCommand(
            "Toggle dim hidden files",
            "Dim or un-dim hidden files (dotfiles) in the explorer",
            self._toggle_dim_hidden_files_cmd,
        )
        yield SystemCommand(
            "Toggle git status highlighting",
            "Show or hide git status colors in the explorer",
            self._toggle_show_git_status_cmd,
        )

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

    def action_toggle_split_vertical_cmd(self) -> None:
        """Toggle split orientation via command palette."""
        self.call_next(self.main_view.action_toggle_split_vertical)

    def _toggle_word_wrap_cmd(self) -> None:
        """Toggle word wrap for the active file via command palette."""
        code_editor = self.main_view.get_active_code_editor()
        if code_editor is not None:
            self.call_next(code_editor.action_toggle_word_wrap)
        else:
            self.notify("No file open.", severity="error")

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

    def _toggle_hidden_files_cmd(self) -> None:
        """Toggle hidden files visibility in the explorer and save to config."""
        self.default_show_hidden_files = not self.default_show_hidden_files
        self._toggle_explorer_tree_setting(
            "show_hidden_files",
            self.default_show_hidden_files,
            "Hidden files",
            "visible",
            "hidden",
        )

    def _toggle_path_display_mode_cmd(self) -> None:
        """Toggle between absolute and relative path display in footer."""
        from textual_code.widgets.code_editor import CodeEditorFooter

        self.default_path_display_mode = (
            "relative" if self.default_path_display_mode == "absolute" else "absolute"
        )
        footer = self.main_view.query_one(CodeEditorFooter)
        footer.path_display_mode = self.default_path_display_mode
        self._save_editor_settings("user")
        self.notify(f"Path display: {self.default_path_display_mode}")

    def _toggle_dim_gitignored_cmd(self) -> None:
        """Toggle dim gitignored files in the explorer and save to config."""
        self.default_dim_gitignored = not self.default_dim_gitignored
        self._toggle_explorer_tree_setting(
            "dim_gitignored",
            self.default_dim_gitignored,
            "Gitignored files",
            "dimmed",
            "normal",
        )

    def _toggle_dim_hidden_files_cmd(self) -> None:
        """Toggle dim hidden files in the explorer and save to config."""
        self.default_dim_hidden_files = not self.default_dim_hidden_files
        self._toggle_explorer_tree_setting(
            "dim_hidden_files",
            self.default_dim_hidden_files,
            "Hidden files",
            "dimmed",
            "normal",
        )

    def _toggle_show_git_status_cmd(self) -> None:
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
        self.push_screen(
            CommandPalette(
                providers=[
                    create_open_file_command_provider(
                        self.workspace_path,
                        post_message_callback=lambda path: self.app.post_message(
                            self.OpenFileRequested(path=path)
                        ),
                    )
                ],
                placeholder="Search for files...",
            ),
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

    def action_delete_file_or_dir_with_command_palette(self) -> None:
        """
        Delete a file or directory with the command palette.
        """
        self.push_screen(
            CommandPalette(
                providers=[
                    create_delete_path_command_provider(
                        self.workspace_path,
                        post_message_callback=lambda path: self.app.post_message(
                            self.DeletePathWithPaletteRequested(path=path)
                        ),
                    )
                ],
                placeholder="Delete file or directory...",
            ),
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
        """
        Rename a file or directory with the command palette.
        """
        self.push_screen(
            CommandPalette(
                providers=[
                    create_rename_path_command_provider(
                        self.workspace_path,
                        post_message_callback=lambda path: self.app.post_message(
                            self.RenamePathWithPaletteRequested(path=path)
                        ),
                    )
                ],
                placeholder="Rename file or directory...",
            ),
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
        self.push_screen(
            CommandPalette(
                providers=[
                    create_move_path_command_provider(
                        self.workspace_path,
                        post_message_callback=lambda path: self.app.post_message(
                            self.MovePathWithPaletteRequested(path=path)
                        ),
                    )
                ],
                placeholder="Move file or directory...",
            ),
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
        """Open directory picker CommandPalette for moving a file or directory."""
        from textual_code.commands import create_move_destination_command_provider

        name = path.name
        self.push_screen(
            CommandPalette(
                providers=[
                    create_move_destination_command_provider(
                        self.workspace_path,
                        source_path=path,
                        post_message_callback=lambda dest_dir: self.post_message(
                            self.MoveDestinationSelected(
                                source_path=path, destination_dir=dest_dir
                            )
                        ),
                    )
                ],
                placeholder=f"Move '{name}' to...",
            ),
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
        """Open the keyboard shortcuts panel."""
        from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

        rows: list[tuple[str, str, str, str]] = []
        for cls, ctx in [
            (MainView, "Editor"),
            (TextualCode, "App"),
            (MultiCursorTextArea, "Text Area"),
        ]:
            for b in cls.BINDINGS:
                if b.description:
                    rows.append((b.key, b.description, ctx, b.action))
        self.push_screen(ShowShortcutsScreen(rows))

    def set_keybinding(self, action: str, new_key: str) -> None:
        """Save a custom keybinding and apply it immediately."""
        self._custom_keybindings[action] = new_key
        kb_path = (
            get_keybindings_path(self._user_config_path)
            if self._user_config_path
            else get_keybindings_path()
        )
        self._save_config(save_keybindings, self._custom_keybindings, kb_path)
        _apply_custom_keybindings({action: new_key})
        self.notify("Shortcut saved. Restart to apply changes.")

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


def _apply_custom_keybindings(custom: dict[str, str]) -> None:
    """Patch class-level BINDINGS lists with custom key mappings."""
    from textual_code.widgets.multi_cursor_text_area import MultiCursorTextArea

    for cls in (MainView, TextualCode, MultiCursorTextArea):
        cls.BINDINGS = [
            Binding(
                custom[b.action],
                b.action,
                b.description,
                show=b.show,
                priority=b.priority,
            )
            if b.action in custom
            else b
            for b in cls.BINDINGS
        ]
