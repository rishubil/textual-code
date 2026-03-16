from collections.abc import Iterable
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.command import CommandPalette
from textual.events import Ready
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Footer

from textual_code.commands import (
    create_create_file_or_dir_command_provider,
    create_delete_path_command_provider,
    create_open_file_command_provider,
)
from textual_code.config import (
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
from textual_code.widgets.sidebar import SIDEBAR_MIN_WIDTH, Sidebar
from textual_code.widgets.workspace_search import WorkspaceSearchPane

# Textual's built-in "Theme" command title — used to filter it out from command palette.
# This string matches the title yielded by textual.app.App.get_system_commands().
_TEXTUAL_BUILTIN_THEME_CMD = "Theme"


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
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

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
        self.theme = self.default_ui_theme

        # load and apply custom keybindings
        kb_path = get_keybindings_path(user_config_path) if user_config_path else None
        self._custom_keybindings: dict[str, str] = load_keybindings(kb_path)
        _apply_custom_keybindings(self._custom_keybindings)

    def compose(self) -> ComposeResult:
        yield Sidebar(workspace_path=self.workspace_path)
        yield MainView()
        yield Footer()

    @on(Ready)
    async def on_ready(self, event: Ready):
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
                settings = self._build_editor_settings()
                if result.save_level == "project":
                    save_project_editor_settings(settings, self.workspace_path)
                else:
                    save_user_editor_settings(settings, self._user_config_path)

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
                settings = self._build_editor_settings()
                if result.save_level == "project":
                    save_project_editor_settings(settings, self.workspace_path)
                else:
                    save_user_editor_settings(settings, self._user_config_path)

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
                settings = self._build_editor_settings()
                if result.save_level == "project":
                    save_project_editor_settings(settings, self.workspace_path)
                else:
                    save_user_editor_settings(settings, self._user_config_path)

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
                settings = self._build_editor_settings()
                if result.save_level == "project":
                    save_project_editor_settings(settings, self.workspace_path)
                else:
                    save_user_editor_settings(settings, self._user_config_path)

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
                settings = self._build_editor_settings()
                if result.save_level == "project":
                    save_project_editor_settings(settings, self.workspace_path)
                else:
                    save_user_editor_settings(settings, self._user_config_path)

        self.call_next(
            lambda: self.push_screen(
                ChangeWordWrapModalScreen(current_word_wrap=self.default_word_wrap),
                do_change,
            )
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

    def action_open_user_settings(self) -> None:
        """Open user settings file in the editor."""
        path = self._resolved_user_config_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("")
        self.call_next(
            partial(self.main_view.action_open_code_editor, path=path, focus=True)
        )

    def action_open_project_settings(self) -> None:
        """Open project settings file in the editor."""
        path = get_project_config_path(self.workspace_path)
        if not path.exists():
            path.write_text("")
        self.call_next(
            partial(self.main_view.action_open_code_editor, path=path, focus=True)
        )

    def action_set_ui_theme(self) -> None:
        """Set the UI theme."""

        def do_change(result: ChangeUIThemeModalResult | None) -> None:
            if result and not result.is_cancelled and result.theme:
                self.default_ui_theme = result.theme
                self.theme = result.theme
                settings = self._build_editor_settings()
                if result.save_level == "project":
                    save_project_editor_settings(settings, self.workspace_path)
                else:
                    save_user_editor_settings(settings, self._user_config_path)

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
            current_width = self.sidebar.size.width
            max_width = self.size.width - 5
            parsed = _parse_sidebar_resize(result.value or "", current_width, max_width)
            if parsed is None:
                self.notify(
                    f"Invalid sidebar width: {result.value!r}. "
                    "Use a number (30), +/-offset (+5), or percent (30%).",
                    severity="error",
                )
                return
            self.sidebar.styles.width = parsed

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
        self.sidebar.display = not self.sidebar.display

    def action_reload_explorer(self) -> None:
        """
        Reload the explorer directory tree.
        """
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

    def action_create_file_with_command_palette(self) -> None:
        """
        Create a new file with the command palette.
        """
        self.push_screen(
            CommandPalette(
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
            ),
        )

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

    def action_create_directory_with_command_palette(self) -> None:
        """
        Create a new directory with the command palette.
        """
        self.push_screen(
            CommandPalette(
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
            ),
        )

    def action_quit(self) -> None:
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

    @on(MainView.ActiveFileChanged)
    def on_active_file_changed(self, event: MainView.ActiveFileChanged) -> None:
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
        save_keybindings(self._custom_keybindings, kb_path)
        _apply_custom_keybindings({action: new_key})
        self.notify("Shortcut saved. Restart to apply changes.")

    @property
    def sidebar(self) -> Sidebar:
        # Use the base screen so this works even when a modal is active
        return self.screen_stack[0].query_one(Sidebar)

    @property
    def footer(self) -> Footer:
        return self.query_one(Footer)


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
