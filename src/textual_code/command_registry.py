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
    """Command palette title (e.g. ``"Save file"``)."""

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
        "Save file",
        "Save the current file",
        "editor",
        "action_save_file",
        "ctrl+s",
        binding_description="Save",
    ),
    CommandEntry(
        "save_all",
        "Save all files",
        "Save all open files",
        "editor",
        "action_save_all_files",
        "ctrl+shift+s",
        show=False,
        binding_description="Save all",
    ),
    CommandEntry(
        "close",
        "Close file",
        "Close the current file",
        "editor",
        "action_close_file",
        "ctrl+w",
        priority=True,
        binding_description="Close tab",
    ),
    CommandEntry(
        "close_all",
        "Close all files",
        "Close all open files",
        "editor",
        "action_close_all_files",
        "ctrl+shift+w",
        show=False,
        priority=True,
        binding_description="Close all",
    ),
    CommandEntry(
        "goto_line",
        "Goto line",
        "Go to a specific line and column",
        "editor",
        "action_goto_line_cmd",
        "ctrl+g",
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
        "Add cursor below",
        "Add an extra cursor one line below",
        "editor",
        "action_add_cursor_below_cmd",
        "ctrl+alt+down",
        show=False,
    ),
    CommandEntry(
        "add_cursor_above",
        "Add cursor above",
        "Add an extra cursor one line above",
        "editor",
        "action_add_cursor_above_cmd",
        "ctrl+alt+up",
        show=False,
    ),
    CommandEntry(
        "select_all_occurrences",
        "Select all occurrences",
        "Select all occurrences of the current selection or word",
        "editor",
        "action_select_all_occurrences_cmd",
        "ctrl+shift+l",
        show=False,
        priority=True,
    ),
    CommandEntry(
        "add_next_occurrence",
        "Add next occurrence",
        "Add a cursor at the next occurrence of the selection or word",
        "editor",
        "action_add_next_occurrence_cmd",
        "ctrl+d",
        show=False,
        priority=True,
    ),
    CommandEntry(
        "split_right",
        "Split editor right",
        "Open current file in a new split to the right",
        "editor",
        "action_split_right_cmd",
        "ctrl+backslash",
        show=False,
    ),
    CommandEntry(
        "close_split",
        "Close split",
        "Close the current split panel",
        "editor",
        "action_close_split_cmd",
        "ctrl+shift+backslash",
        show=False,
    ),
    CommandEntry(
        "open_markdown_preview_tab",
        "Open markdown preview as tab",
        "Open a live markdown preview in a new tab",
        "editor",
        "action_open_markdown_preview_tab_cmd",
        "ctrl+shift+m",
        show=False,
    ),
    CommandEntry(
        "move_tab_to_other_split",
        "Move tab to other split",
        "Move the current tab to the other split panel",
        "editor",
        "action_move_tab_to_other_split_cmd",
        "ctrl+alt+backslash",
        show=False,
    ),
    CommandEntry(
        "rename_file",
        "Rename file",
        "Rename the current file",
        "editor",
        "action_rename_active_file",
        "f2",
        show=False,
        binding_description="Rename",
    ),
    # ── app context (TextualCode) — with default keys ─────────────────────
    CommandEntry(
        "new_editor",
        "New file",
        "Open empty code editor",
        "app",
        "action_new_editor",
        "ctrl+n",
    ),
    CommandEntry(
        "toggle_sidebar",
        "Toggle sidebar",
        "Show or hide the sidebar",
        "app",
        "action_toggle_sidebar",
        "ctrl+b",
    ),
    CommandEntry(
        "find_in_workspace",
        "Find in Workspace",
        "Search all files in the workspace",
        "app",
        "action_find_in_workspace_cmd",
        "ctrl+shift+f",
        show=False,
    ),
    CommandEntry(
        "show_shortcuts",
        "Show keyboard shortcuts",
        "View and change keyboard shortcuts",
        "app",
        "action_show_shortcuts",
        "f1",
        show=False,
        binding_description="Keyboard shortcuts",
    ),
    # Binding-only (no palette entry) — navigation
    CommandEntry(
        "focus_next",
        "Next widget",
        "Move focus to next widget",
        "app",
        "",
        "f6",
        show=False,
        priority=True,
    ),
    CommandEntry(
        "focus_previous",
        "Previous widget",
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
        "Configure footer shortcuts",
        "Choose which shortcuts appear in the footer and their order",
        "app",
        "action_configure_footer",
    ),
    CommandEntry(
        "open_user_settings",
        "Open user settings",
        "Open user settings file (~/.config/textual-code/settings.toml)",
        "app",
        "action_open_user_settings",
    ),
    CommandEntry(
        "open_project_settings",
        "Open project settings",
        "Open project settings file (.textual-code.toml in workspace root)",
        "app",
        "action_open_project_settings",
    ),
    CommandEntry(
        "open_keybindings",
        "Open keybindings",
        "Open keybindings config file (keybindings.toml)",
        "app",
        "action_open_keybindings",
    ),
    CommandEntry(
        "reload_explorer",
        "Reload explorer",
        "Reload the explorer",
        "app",
        "action_reload_explorer",
    ),
    CommandEntry(
        "save_file_as",
        "Save file as",
        "Save the current file as new file",
        "editor",
        "action_save_file_as",
    ),
    CommandEntry(
        "delete_file",
        "Delete file",
        "Delete the current file",
        "editor",
        "action_delete_file",
    ),
    CommandEntry(
        "copy_relative_path",
        "Copy relative path",
        "Copy the relative file path to clipboard",
        "editor",
        "action_copy_relative_path",
    ),
    CommandEntry(
        "copy_absolute_path",
        "Copy absolute path",
        "Copy the absolute file path to clipboard",
        "editor",
        "action_copy_absolute_path",
    ),
    CommandEntry(
        "open_file_with_command_palette",
        "Open file",
        "Open a file in the code editor",
        "app",
        "action_open_file_with_command_palette",
    ),
    CommandEntry(
        "create_file_with_command_palette",
        "Create file",
        "Create a new file at a path",
        "app",
        "action_create_file_with_command_palette",
    ),
    CommandEntry(
        "create_directory_with_command_palette",
        "Create directory",
        "Create a new directory at a path",
        "app",
        "action_create_directory_with_command_palette",
    ),
    CommandEntry(
        "quit",
        "Quit",
        "Quit the app",
        "app",
        "action_quit",
    ),
    CommandEntry(
        "change_language_cmd",
        "Change language",
        "Change the syntax highlighting language",
        "editor",
        "action_change_language_cmd",
    ),
    CommandEntry(
        "delete_file_or_dir_with_command_palette",
        "Delete file or directory",
        "Delete a file or directory from the workspace",
        "app",
        "action_delete_file_or_dir_with_command_palette",
    ),
    CommandEntry(
        "rename_file_or_dir_with_command_palette",
        "Rename file or directory",
        "Rename a file or directory in the workspace",
        "app",
        "action_rename_file_or_dir_with_command_palette",
    ),
    CommandEntry(
        "move_active_file",
        "Move file",
        "Move the current file to a different path",
        "editor",
        "action_move_active_file",
    ),
    CommandEntry(
        "move_file_or_dir_with_command_palette",
        "Move file or directory",
        "Move a file or directory to a different path",
        "app",
        "action_move_file_or_dir_with_command_palette",
    ),
    CommandEntry(
        "copy_explorer_node",
        "Copy file or directory",
        "Copy the selected file or directory in the explorer",
        "app",
        "action_copy_explorer_node",
    ),
    CommandEntry(
        "cut_explorer_node",
        "Cut file or directory",
        "Cut the selected file or directory in the explorer",
        "app",
        "action_cut_explorer_node",
    ),
    CommandEntry(
        "paste_explorer_node",
        "Paste file or directory",
        "Paste the copied/cut file or directory",
        "app",
        "action_paste_explorer_node",
    ),
    CommandEntry(
        "change_indent_cmd",
        "Change Indentation",
        "Change indentation style and size",
        "editor",
        "action_change_indent_cmd",
    ),
    CommandEntry(
        "change_line_ending_cmd",
        "Change Line Ending",
        "Change the line ending style (LF, CRLF, CR)",
        "editor",
        "action_change_line_ending_cmd",
    ),
    CommandEntry(
        "change_encoding_cmd",
        "Change Encoding",
        "Change the file encoding (UTF-8, UTF-8 BOM, UTF-16, Latin-1)",
        "editor",
        "action_change_encoding_cmd",
    ),
    CommandEntry(
        "reload_file_cmd",
        "Reload file",
        "Reload the current file from disk",
        "editor",
        "action_reload_file_cmd",
    ),
    CommandEntry(
        "resize_sidebar_cmd",
        "Resize sidebar",
        "Set the sidebar width (e.g. 30, +5, -3, 30%)",
        "app",
        "action_resize_sidebar_cmd",
    ),
    CommandEntry(
        "resize_split_cmd",
        "Resize split",
        "Set the left split panel width (e.g. 50, +10, -5, 40%)",
        "editor",
        "action_resize_split_cmd",
    ),
    CommandEntry(
        "split_left_cmd",
        "Split editor left",
        "Open current file in a new split to the left",
        "editor",
        "action_split_left_cmd",
    ),
    CommandEntry(
        "split_down_cmd",
        "Split editor down",
        "Open current file in a new split below",
        "editor",
        "action_split_down_cmd",
    ),
    CommandEntry(
        "split_up_cmd",
        "Split editor up",
        "Open current file in a new split above",
        "editor",
        "action_split_up_cmd",
    ),
    CommandEntry(
        "focus_next_split_cmd",
        "Focus next split",
        "Move focus to the next split panel",
        "editor",
        "action_focus_next_split_cmd",
    ),
    CommandEntry(
        "focus_prev_split_cmd",
        "Focus previous split",
        "Move focus to the previous split panel",
        "editor",
        "action_focus_prev_split_cmd",
    ),
    CommandEntry(
        "set_default_indentation",
        "Set default indentation",
        "Set the default indentation for new files",
        "app",
        "action_set_default_indentation",
    ),
    CommandEntry(
        "set_default_line_ending",
        "Set default line ending",
        "Set the default line ending for new files",
        "app",
        "action_set_default_line_ending",
    ),
    CommandEntry(
        "set_default_encoding",
        "Set default encoding",
        "Set the default encoding for new files",
        "app",
        "action_set_default_encoding",
    ),
    CommandEntry(
        "set_syntax_theme",
        "Change syntax highlighting theme",
        "Select the syntax highlighting theme for the editor",
        "app",
        "action_set_syntax_theme",
    ),
    CommandEntry(
        "move_tab_left_cmd",
        "Move tab left",
        "Move the current tab to the split pane on the left",
        "editor",
        "action_move_tab_left_cmd",
    ),
    CommandEntry(
        "move_tab_right_cmd",
        "Move tab right",
        "Move the current tab to the split pane on the right",
        "editor",
        "action_move_tab_right_cmd",
    ),
    CommandEntry(
        "move_tab_up_cmd",
        "Move tab up",
        "Move the current tab to the split pane above",
        "editor",
        "action_move_tab_up_cmd",
    ),
    CommandEntry(
        "move_tab_down_cmd",
        "Move tab down",
        "Move the current tab to the split pane below",
        "editor",
        "action_move_tab_down_cmd",
    ),
    CommandEntry(
        "reorder_tab_right_cmd",
        "Reorder tab right",
        "Move the current tab one position to the right",
        "editor",
        "action_reorder_tab_right_cmd",
    ),
    CommandEntry(
        "reorder_tab_left_cmd",
        "Reorder tab left",
        "Move the current tab one position to the left",
        "editor",
        "action_reorder_tab_left_cmd",
    ),
    CommandEntry(
        "toggle_split_vertical_cmd",
        "Toggle split orientation",
        "Switch between horizontal and vertical split layout",
        "editor",
        "action_toggle_split_vertical_cmd",
    ),
    CommandEntry(
        "toggle_word_wrap_cmd",
        "Toggle word wrap",
        "Toggle word wrap for the active file",
        "editor",
        "action_toggle_word_wrap_cmd",
    ),
    CommandEntry(
        "set_default_word_wrap",
        "Set default word wrap",
        "Toggle default word wrap for new files",
        "app",
        "action_set_default_word_wrap",
    ),
    CommandEntry(
        "set_ui_theme",
        "Change UI theme",
        "Select the UI theme",
        "app",
        "action_set_ui_theme",
    ),
    CommandEntry(
        "toggle_hidden_files_cmd",
        "Toggle hidden files",
        "Show or hide hidden files in the explorer",
        "app",
        "action_toggle_hidden_files_cmd",
    ),
    CommandEntry(
        "toggle_path_display_mode_cmd",
        "Toggle path display mode",
        "Switch between absolute and relative path in footer",
        "app",
        "action_toggle_path_display_mode_cmd",
    ),
    CommandEntry(
        "toggle_dim_gitignored_cmd",
        "Toggle dim gitignored files",
        "Dim or un-dim gitignored files in the explorer",
        "app",
        "action_toggle_dim_gitignored_cmd",
    ),
    CommandEntry(
        "toggle_dim_hidden_files_cmd",
        "Toggle dim hidden files",
        "Dim or un-dim hidden files (dotfiles) in the explorer",
        "app",
        "action_toggle_dim_hidden_files_cmd",
    ),
    CommandEntry(
        "toggle_show_git_status_cmd",
        "Toggle git status highlighting",
        "Show or hide git status colors in the explorer",
        "app",
        "action_toggle_show_git_status_cmd",
    ),
    CommandEntry(
        "toggle_indentation_guides_cmd",
        "Toggle indentation guides",
        "Show or hide indentation guides in the editor",
        "editor",
        "action_toggle_indentation_guides_cmd",
    ),
    CommandEntry(
        "set_render_whitespace_cmd",
        "Set render whitespace",
        "Select whitespace display mode",
        "editor",
        "action_set_render_whitespace_cmd",
    ),
    # Text transformations
    CommandEntry(
        "sort_lines_ascending_cmd",
        "Sort lines ascending",
        "Sort selected lines in ascending order",
        "editor",
        "action_sort_lines_ascending_cmd",
    ),
    CommandEntry(
        "sort_lines_descending_cmd",
        "Sort lines descending",
        "Sort selected lines in descending order",
        "editor",
        "action_sort_lines_descending_cmd",
    ),
    CommandEntry(
        "transform_uppercase_cmd",
        "Transform to uppercase",
        "Convert selected text to uppercase",
        "editor",
        "action_transform_uppercase_cmd",
    ),
    CommandEntry(
        "transform_lowercase_cmd",
        "Transform to lowercase",
        "Convert selected text to lowercase",
        "editor",
        "action_transform_lowercase_cmd",
    ),
    CommandEntry(
        "transform_title_case_cmd",
        "Transform to title case",
        "Convert selected text to title case",
        "editor",
        "action_transform_title_case_cmd",
    ),
    CommandEntry(
        "transform_snake_case_cmd",
        "Transform to snake_case",
        "Convert selected text to snake_case",
        "editor",
        "action_transform_snake_case_cmd",
    ),
    CommandEntry(
        "transform_camel_case_cmd",
        "Transform to camelCase",
        "Convert selected text to camelCase",
        "editor",
        "action_transform_camel_case_cmd",
    ),
    CommandEntry(
        "transform_kebab_case_cmd",
        "Transform to kebab-case",
        "Convert selected text to kebab-case",
        "editor",
        "action_transform_kebab_case_cmd",
    ),
    CommandEntry(
        "transform_pascal_case_cmd",
        "Transform to PascalCase",
        "Convert selected text to PascalCase",
        "editor",
        "action_transform_pascal_case_cmd",
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
        "Select all",
        "Select all text in the document",
        "text_area",
        "action_select_all_text_cmd",
        "ctrl+a",
        show=False,
    ),
    CommandEntry(
        "indent_line",
        "Indent",
        "Indent line or selection",
        "text_area",
        "action_indent_line_cmd",
        "tab",
        show=False,
    ),
    CommandEntry(
        "dedent_line",
        "Dedent",
        "Dedent line or selection",
        "text_area",
        "action_dedent_line_cmd",
        "shift+tab",
        show=False,
    ),
    CommandEntry(
        "move_line_up",
        "Move line up",
        "Move line(s) up",
        "text_area",
        "action_move_line_up_cmd",
        "alt+up",
        show=False,
    ),
    CommandEntry(
        "move_line_down",
        "Move line down",
        "Move line(s) down",
        "text_area",
        "action_move_line_down_cmd",
        "alt+down",
        show=False,
    ),
    CommandEntry(
        "scroll_viewport_up",
        "Scroll up",
        "Scroll viewport up",
        "text_area",
        "action_scroll_viewport_up_cmd",
        "ctrl+up",
        show=False,
    ),
    CommandEntry(
        "scroll_viewport_down",
        "Scroll down",
        "Scroll viewport down",
        "text_area",
        "action_scroll_viewport_down_cmd",
        "ctrl+down",
        show=False,
    ),
    # Binding-only entries (no palette callback — navigation-only)
    CommandEntry(
        "cursor_page_up_select",
        "Select page up",
        "Select from cursor to page start",
        "text_area",
        "",
        "shift+pageup",
        show=False,
    ),
    CommandEntry(
        "cursor_page_down_select",
        "Select page down",
        "Select from cursor to page end",
        "text_area",
        "",
        "shift+pagedown",
        show=False,
    ),
    CommandEntry(
        "cursor_document_start",
        "Go to start",
        "Move cursor to document start",
        "text_area",
        "",
        "ctrl+home",
        show=False,
    ),
    CommandEntry(
        "cursor_document_end",
        "Go to end",
        "Move cursor to document end",
        "text_area",
        "",
        "ctrl+end",
        show=False,
    ),
    CommandEntry(
        "cursor_document_start(True)",
        "Select to start",
        "Select from cursor to document start",
        "text_area",
        "",
        "ctrl+shift+home",
        show=False,
    ),
    CommandEntry(
        "cursor_document_end(True)",
        "Select to end",
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
