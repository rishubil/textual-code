"""Unified command registry — single source of truth for all bindable commands.

Every command that can appear in the command palette, F1 shortcuts viewer,
or be assigned a keyboard shortcut is defined here exactly once.

From this registry, the app derives:
- BINDINGS lists for TextualCode, MainView, MultiCursorTextArea
- SystemCommand entries for the command palette
- Rows for the F1 keyboard shortcuts viewer
- The action-to-title mapping for palette visibility control
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from textual.binding import Binding

_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CommandEntry:
    """A single bindable command."""

    action: str
    """Binding action name passed to Textual (e.g. ``"save"``)."""

    title: str
    """Command palette title (e.g. ``"Save"``)."""

    description: str
    """Palette description without key hint."""

    context: str
    """Which class owns the Binding: ``"app"`` | ``"editor"`` | ``"text_area"``."""

    palette_callback: str = ""
    """Method name on ``TextualCode`` for the palette callback.
    Empty string means binding-only (no palette entry)."""

    default_key: str = ""
    """Default keyboard shortcut. Empty string means unbound."""

    show: bool = True
    """Whether the binding shows in the footer by default."""

    priority: bool = False
    """Textual binding priority flag."""

    binding_description: str = ""
    """Short label for the footer / F1 viewer.
    Falls back to *title* when empty."""


# ── Registry ──────────────────────────────────────────────────────────────────
#
# Entries are grouped by context.  Within each group, commands with a
# default_key come first (matching the original BINDINGS order), followed
# by palette-only commands.

COMMAND_REGISTRY: tuple[CommandEntry, ...] = (
    # ── editor context (MainView) ─────────────────────────────────────────
    CommandEntry(
        "save",
        "Save",
        "Save the current file",
        "editor",
        "action_save_file",
        "ctrl+s",
        binding_description="Save",
    ),
    CommandEntry(
        "save_all",
        "Save All",
        "Save all open files",
        "editor",
        "action_save_all_files",
        "ctrl+shift+s",
        show=False,
        binding_description="Save All",
    ),
    CommandEntry(
        "close_editor",
        "Close Editor",
        "Close the current editor",
        "editor",
        "action_close_editor_cmd",
        "ctrl+w",
        priority=True,
        binding_description="Close",
    ),
    CommandEntry(
        "close_all_editors",
        "Close All Editors",
        "Close all open editors",
        "editor",
        "action_close_all_editors_cmd",
        "ctrl+shift+w",
        show=False,
        priority=True,
        binding_description="Close All",
    ),
    CommandEntry(
        "goto_line",
        "Go to Line/Column...",
        "Go to a specific line and column",
        "editor",
        "action_goto_line_cmd",
        "ctrl+g",
        binding_description="Go to Line",
    ),
    CommandEntry(
        "find",
        "Find",
        "Find text in the current file",
        "editor",
        "action_find_cmd",
        "ctrl+f",
        priority=True,
    ),
    CommandEntry(
        "replace",
        "Replace",
        "Find and replace text in the current file",
        "editor",
        "action_replace_cmd",
        "ctrl+h",
        priority=True,
    ),
    CommandEntry(
        "add_cursor_below",
        "Add Cursor Below",
        "Add an extra cursor one line below",
        "editor",
        "action_add_cursor_below_cmd",
        "ctrl+alt+down",
        show=False,
    ),
    CommandEntry(
        "add_cursor_above",
        "Add Cursor Above",
        "Add an extra cursor one line above",
        "editor",
        "action_add_cursor_above_cmd",
        "ctrl+alt+up",
        show=False,
    ),
    CommandEntry(
        "select_all_occurrences",
        "Select All Occurrences of Find Match",
        "Select all occurrences of the current selection or word",
        "editor",
        "action_select_all_occurrences_cmd",
        "ctrl+shift+l",
        show=False,
        priority=True,
    ),
    CommandEntry(
        "add_next_occurrence",
        "Add Selection to Next Find Match",
        "Add a cursor at the next occurrence of the selection or word",
        "editor",
        "action_add_next_occurrence_cmd",
        "ctrl+d",
        show=False,
        priority=True,
    ),
    CommandEntry(
        "split_right",
        "Split Editor Right",
        "Open current file in a new split to the right",
        "editor",
        "action_split_right_cmd",
        "ctrl+backslash",
        show=False,
    ),
    CommandEntry(
        "close_editor_group",
        "Close Editor Group",
        "Close the current editor group",
        "editor",
        "action_close_editor_group_cmd",
        "ctrl+shift+backslash",
        show=False,
    ),
    CommandEntry(
        "open_markdown_preview",
        "Open Markdown Preview",
        "Open a live markdown preview in a new tab",
        "editor",
        "action_open_markdown_preview_cmd",
        "ctrl+shift+m",
        show=False,
    ),
    CommandEntry(
        "move_editor_to_next_group",
        "Move Editor into Next Group",
        "Move the current editor into the next group",
        "editor",
        "action_move_editor_to_next_group_cmd",
        "ctrl+alt+backslash",
        show=False,
    ),
    CommandEntry(
        "rename_file",
        "Rename...",
        "Rename the current file",
        "editor",
        "action_rename_active_file",
        "f2",
        show=False,
        binding_description="Rename",
    ),
    # ── app context (TextualCode) — with default keys ─────────────────────
    CommandEntry(
        "new_untitled_file",
        "New Untitled File",
        "Open a new untitled editor",
        "app",
        "action_new_untitled_file",
        "ctrl+n",
    ),
    CommandEntry(
        "toggle_sidebar",
        "Toggle Sidebar",
        "Show or hide the sidebar",
        "app",
        "action_toggle_sidebar",
        "ctrl+b",
    ),
    CommandEntry(
        "find_in_files",
        "Find in Files",
        "Search all files in the workspace",
        "app",
        "action_find_in_files_cmd",
        "ctrl+shift+f",
        show=False,
    ),
    CommandEntry(
        "show_keyboard_shortcuts",
        "Show Keyboard Shortcuts",
        "View and change keyboard shortcuts",
        "app",
        "action_show_keyboard_shortcuts",
        "f1",
        show=False,
        binding_description="Keyboard Shortcuts",
    ),
    # Binding-only (no palette entry) — navigation
    CommandEntry(
        "focus_next",
        "Next Widget",
        "Move focus to next widget",
        "app",
        "",
        "f6",
        show=False,
        priority=True,
    ),
    CommandEntry(
        "focus_previous",
        "Previous Widget",
        "Move focus to previous widget",
        "app",
        "",
        "shift+f6",
        show=False,
        priority=True,
    ),
    # ── app context — palette-only (no default key) ───────────────────────
    CommandEntry(
        "configure_footer",
        "Configure Footer Shortcuts",
        "Choose which shortcuts appear in the footer and their order",
        "app",
        "action_configure_footer",
    ),
    CommandEntry(
        "open_user_settings",
        "Open User Settings",
        "Open user settings file (~/.config/textual-code/settings.toml)",
        "app",
        "action_open_user_settings",
    ),
    CommandEntry(
        "open_project_settings",
        "Open Project Settings",
        "Open project settings file (.textual-code.toml in workspace root)",
        "app",
        "action_open_project_settings",
    ),
    CommandEntry(
        "open_keyboard_shortcuts_file",
        "Open Keyboard Shortcuts File",
        "Open keybindings config file (keybindings.toml)",
        "app",
        "action_open_keyboard_shortcuts_file",
    ),
    CommandEntry(
        "refresh_explorer",
        "Refresh Explorer",
        "Refresh the file explorer tree",
        "app",
        "action_refresh_explorer",
    ),
    CommandEntry(
        "save_as",
        "Save As...",
        "Save the current file as new file",
        "editor",
        "action_save_as",
    ),
    CommandEntry(
        "delete_file",
        "Delete File",
        "Delete the current file",
        "editor",
        "action_delete_file",
    ),
    CommandEntry(
        "copy_relative_path",
        "Copy Relative Path",
        "Copy the relative file path to clipboard",
        "editor",
        "action_copy_relative_path",
    ),
    CommandEntry(
        "copy_absolute_path",
        "Copy Absolute Path",
        "Copy the absolute file path to clipboard",
        "editor",
        "action_copy_absolute_path",
    ),
    CommandEntry(
        "open_file",
        "Open File...",
        "Open a file in the code editor",
        "app",
        "action_open_file",
    ),
    CommandEntry(
        "new_file",
        "New File...",
        "Create a new file at a path",
        "app",
        "action_new_file",
        binding_description="New File",
    ),
    CommandEntry(
        "new_folder",
        "New Folder...",
        "Create a new directory at a path",
        "app",
        "action_new_folder",
        binding_description="New Folder",
    ),
    CommandEntry(
        "quit",
        "Quit",
        "Quit the app",
        "app",
        "action_quit",
        "ctrl+q",
        show=False,
        priority=True,
    ),
    CommandEntry(
        "change_language",
        "Change Language...",
        "Change the syntax highlighting language",
        "editor",
        "action_change_language",
    ),
    CommandEntry(
        "delete_file_or_directory",
        "Delete File or Directory",
        "Delete a file or directory from the workspace",
        "app",
        "action_delete_file_or_directory",
    ),
    CommandEntry(
        "rename_file_or_directory",
        "Rename File or Directory...",
        "Rename a file or directory in the workspace",
        "app",
        "action_rename_file_or_directory",
    ),
    CommandEntry(
        "move_file",
        "Move File...",
        "Move the current file to a different path",
        "editor",
        "action_move_file",
    ),
    CommandEntry(
        "move_file_or_directory",
        "Move File or Directory...",
        "Move a file or directory to a different path",
        "app",
        "action_move_file_or_directory",
    ),
    CommandEntry(
        "copy_file_or_directory",
        "Copy File or Directory",
        "Copy the selected file or directory in the explorer",
        "app",
        "action_copy_file_or_directory",
    ),
    CommandEntry(
        "cut_file_or_directory",
        "Cut File or Directory",
        "Cut the selected file or directory in the explorer",
        "app",
        "action_cut_file_or_directory",
    ),
    CommandEntry(
        "paste_file_or_directory",
        "Paste File or Directory",
        "Paste the copied/cut file or directory",
        "app",
        "action_paste_file_or_directory",
    ),
    CommandEntry(
        "change_indentation",
        "Change Indentation...",
        "Change indentation style and size",
        "editor",
        "action_change_indentation",
    ),
    CommandEntry(
        "change_line_ending",
        "Change Line Ending...",
        "Change the line ending style (LF, CRLF, CR)",
        "editor",
        "action_change_line_ending",
    ),
    CommandEntry(
        "change_encoding",
        "Change Encoding...",
        "Change the file encoding (UTF-8, UTF-8 BOM, UTF-16, Latin-1)",
        "editor",
        "action_change_encoding",
    ),
    CommandEntry(
        "revert_file",
        "Revert File",
        "Revert the current file from disk",
        "editor",
        "action_revert_file",
    ),
    CommandEntry(
        "resize_sidebar",
        "Resize Sidebar...",
        "Set the sidebar width (e.g. 30, +5, -3, 30%)",
        "app",
        "action_resize_sidebar",
    ),
    CommandEntry(
        "resize_split",
        "Resize Split...",
        "Set the left split panel width (e.g. 50, +10, -5, 40%)",
        "editor",
        "action_resize_split",
    ),
    CommandEntry(
        "split_left",
        "Split Editor Left",
        "Open current file in a new split to the left",
        "editor",
        "action_split_left",
    ),
    CommandEntry(
        "split_down",
        "Split Editor Down",
        "Open current file in a new split below",
        "editor",
        "action_split_down",
    ),
    CommandEntry(
        "split_up",
        "Split Editor Up",
        "Open current file in a new split above",
        "editor",
        "action_split_up",
    ),
    CommandEntry(
        "focus_next_group",
        "Focus Next Group",
        "Move focus to the next editor group",
        "editor",
        "action_focus_next_group",
    ),
    CommandEntry(
        "focus_previous_group",
        "Focus Previous Group",
        "Move focus to the previous editor group",
        "editor",
        "action_focus_previous_group",
    ),
    CommandEntry(
        "set_default_indentation",
        "Set Default Indentation...",
        "Set the default indentation for new files",
        "app",
        "action_set_default_indentation",
    ),
    CommandEntry(
        "set_default_line_ending",
        "Set Default Line Ending...",
        "Set the default line ending for new files",
        "app",
        "action_set_default_line_ending",
    ),
    CommandEntry(
        "set_default_encoding",
        "Set Default Encoding...",
        "Set the default encoding for new files",
        "app",
        "action_set_default_encoding",
    ),
    CommandEntry(
        "change_syntax_theme",
        "Change Syntax Theme...",
        "Select the syntax highlighting theme for the editor",
        "app",
        "action_change_syntax_theme",
    ),
    CommandEntry(
        "move_editor_left",
        "Move Editor into Left Group",
        "Move the current editor into the left group",
        "editor",
        "action_move_editor_left",
    ),
    CommandEntry(
        "move_editor_right",
        "Move Editor into Right Group",
        "Move the current editor into the right group",
        "editor",
        "action_move_editor_right",
    ),
    CommandEntry(
        "move_editor_up",
        "Move Editor into Group Above",
        "Move the current editor into the group above",
        "editor",
        "action_move_editor_up",
    ),
    CommandEntry(
        "move_editor_down",
        "Move Editor into Group Below",
        "Move the current editor into the group below",
        "editor",
        "action_move_editor_down",
    ),
    CommandEntry(
        "reorder_tab_right",
        "Reorder Tab Right",
        "Move the current tab one position to the right",
        "editor",
        "action_reorder_tab_right",
    ),
    CommandEntry(
        "reorder_tab_left",
        "Reorder Tab Left",
        "Move the current tab one position to the left",
        "editor",
        "action_reorder_tab_left",
    ),
    CommandEntry(
        "toggle_split_orientation",
        "Toggle Split Orientation",
        "Switch between horizontal and vertical split layout",
        "editor",
        "action_toggle_split_orientation",
    ),
    CommandEntry(
        "toggle_word_wrap",
        "Toggle Word Wrap",
        "Toggle word wrap for the active file",
        "editor",
        "action_toggle_word_wrap",
    ),
    CommandEntry(
        "set_default_word_wrap",
        "Set Default Word Wrap...",
        "Toggle default word wrap for new files",
        "app",
        "action_set_default_word_wrap",
    ),
    CommandEntry(
        "change_ui_theme",
        "Change UI Theme...",
        "Select the UI theme",
        "app",
        "action_change_ui_theme",
    ),
    CommandEntry(
        "toggle_hidden_files",
        "Toggle Hidden Files",
        "Show or hide hidden files in the explorer",
        "app",
        "action_toggle_hidden_files",
    ),
    CommandEntry(
        "toggle_path_display_mode",
        "Toggle Path Display Mode",
        "Switch between absolute and relative path in footer",
        "app",
        "action_toggle_path_display_mode",
    ),
    CommandEntry(
        "toggle_dim_gitignored",
        "Toggle Dim Gitignored Files",
        "Dim or un-dim gitignored files in the explorer",
        "app",
        "action_toggle_dim_gitignored",
    ),
    CommandEntry(
        "toggle_dim_hidden_files",
        "Toggle Dim Hidden Files",
        "Dim or un-dim hidden files (dotfiles) in the explorer",
        "app",
        "action_toggle_dim_hidden_files",
    ),
    CommandEntry(
        "toggle_git_status",
        "Toggle Git Status Highlighting",
        "Show or hide git status colors in the explorer",
        "app",
        "action_toggle_git_status",
    ),
    CommandEntry(
        "toggle_indentation_guides",
        "Toggle Indentation Guides",
        "Show or hide indentation guides in the editor",
        "editor",
        "action_toggle_indentation_guides",
    ),
    CommandEntry(
        "set_render_whitespace",
        "Set Render Whitespace...",
        "Select whitespace display mode",
        "editor",
        "action_set_render_whitespace",
    ),
    # Text transformations
    CommandEntry(
        "sort_lines_ascending",
        "Sort Lines Ascending",
        "Sort selected lines in ascending order",
        "editor",
        "action_sort_lines_ascending",
    ),
    CommandEntry(
        "sort_lines_descending",
        "Sort Lines Descending",
        "Sort selected lines in descending order",
        "editor",
        "action_sort_lines_descending",
    ),
    CommandEntry(
        "transform_uppercase",
        "Transform to Uppercase",
        "Convert selected text to uppercase",
        "editor",
        "action_transform_uppercase",
    ),
    CommandEntry(
        "transform_lowercase",
        "Transform to Lowercase",
        "Convert selected text to lowercase",
        "editor",
        "action_transform_lowercase",
    ),
    CommandEntry(
        "transform_title_case",
        "Transform to Title Case",
        "Convert selected text to title case",
        "editor",
        "action_transform_title_case",
    ),
    CommandEntry(
        "transform_snake_case",
        "Transform to Snake Case",
        "Convert selected text to snake_case",
        "editor",
        "action_transform_snake_case",
    ),
    CommandEntry(
        "transform_camel_case",
        "Transform to Camel Case",
        "Convert selected text to camelCase",
        "editor",
        "action_transform_camel_case",
    ),
    CommandEntry(
        "transform_kebab_case",
        "Transform to Kebab Case",
        "Convert selected text to kebab-case",
        "editor",
        "action_transform_kebab_case",
    ),
    CommandEntry(
        "transform_pascal_case",
        "Transform to Pascal Case",
        "Convert selected text to PascalCase",
        "editor",
        "action_transform_pascal_case",
    ),
    # ── text_area context (MultiCursorTextArea) ───────────────────────────
    CommandEntry(
        "redo",
        "Redo",
        "Redo the last undone action",
        "text_area",
        "action_redo_cmd",
        "ctrl+shift+z",
        show=False,
    ),
    CommandEntry(
        "select_all",
        "Select All",
        "Select all text in the document",
        "text_area",
        "action_select_all_text_cmd",
        "ctrl+a",
        show=False,
    ),
    CommandEntry(
        "indent_line",
        "Indent Line",
        "Indent line or selection",
        "text_area",
        "action_indent_line_cmd",
        "tab",
        show=False,
    ),
    CommandEntry(
        "outdent_line",
        "Outdent Line",
        "Outdent line or selection",
        "text_area",
        "action_outdent_line_cmd",
        "shift+tab",
        show=False,
    ),
    CommandEntry(
        "move_line_up",
        "Move Line Up",
        "Move line(s) up",
        "text_area",
        "action_move_line_up_cmd",
        "alt+up",
        show=False,
    ),
    CommandEntry(
        "move_line_down",
        "Move Line Down",
        "Move line(s) down",
        "text_area",
        "action_move_line_down_cmd",
        "alt+down",
        show=False,
    ),
    CommandEntry(
        "scroll_up",
        "Scroll Up",
        "Scroll viewport up",
        "text_area",
        "action_scroll_up_cmd",
        "ctrl+up",
        show=False,
    ),
    CommandEntry(
        "scroll_down",
        "Scroll Down",
        "Scroll viewport down",
        "text_area",
        "action_scroll_down_cmd",
        "ctrl+down",
        show=False,
    ),
    # Binding-only entries (no palette callback — navigation-only)
    CommandEntry(
        "cursor_page_up_select",
        "Select Page Up",
        "Select from cursor to page start",
        "text_area",
        "",
        "shift+pageup",
        show=False,
    ),
    CommandEntry(
        "cursor_page_down_select",
        "Select Page Down",
        "Select from cursor to page end",
        "text_area",
        "",
        "shift+pagedown",
        show=False,
    ),
    CommandEntry(
        "cursor_document_start",
        "Go to Start",
        "Move cursor to document start",
        "text_area",
        "",
        "ctrl+home",
        show=False,
    ),
    CommandEntry(
        "cursor_document_end",
        "Go to End",
        "Move cursor to document end",
        "text_area",
        "",
        "ctrl+end",
        show=False,
    ),
    CommandEntry(
        "cursor_document_start(True)",
        "Select to Start",
        "Select from cursor to document start",
        "text_area",
        "",
        "ctrl+shift+home",
        show=False,
    ),
    CommandEntry(
        "cursor_document_end(True)",
        "Select to End",
        "Select from cursor to document end",
        "text_area",
        "",
        "ctrl+shift+end",
        show=False,
    ),
)

# ── Cached lookups ────────────────────────────────────────────────────────────

_REGISTRY_BY_ACTION: dict[str, CommandEntry] = {e.action: e for e in COMMAND_REGISTRY}


# ── Binding generation ────────────────────────────────────────────────────────


def bindings_for_context(
    context: str, custom: dict[str, str] | None = None
) -> list[Binding]:
    """Generate a ``Binding`` list for *context*, with optional custom overrides.

    Semantics for *custom*:
    - Key **not in** *custom* → use ``entry.default_key``
    - Key **in** *custom* with a non-empty value → use custom value
    - Key **in** *custom* with ``""`` → explicitly unbound (no Binding created)
    """
    bindings: list[Binding] = []
    for entry in COMMAND_REGISTRY:
        if entry.context != context:
            continue
        if custom is not None and entry.action in custom:
            key = custom[entry.action]
        else:
            key = entry.default_key
        if key:
            desc = entry.binding_description or entry.title
            bindings.append(
                Binding(
                    key,
                    entry.action,
                    desc,
                    show=entry.show,
                    priority=entry.priority,
                )
            )
    return bindings
