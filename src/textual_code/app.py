from collections.abc import Iterable
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.command import CommandPalette
from textual.containers import Horizontal
from textual.events import Ready
from textual.message import Message
from textual.screen import Screen
from textual.widgets import (
    Footer,
    Static,
    TabbedContent,
    TabPane,
)

from textual_code.commands import (
    create_create_file_or_dir_command_provider,
    create_delete_path_command_provider,
    create_open_file_command_provider,
)
from textual_code.config import load_editor_settings, save_user_editor_settings
from textual_code.modals import (
    ChangeEncodingModalResult,
    ChangeEncodingModalScreen,
    ChangeIndentModalResult,
    ChangeIndentModalScreen,
    ChangeLineEndingModalResult,
    ChangeLineEndingModalScreen,
    DeleteFileModalResult,
    DeleteFileModalScreen,
    SidebarResizeModalResult,
    SidebarResizeModalScreen,
    SplitResizeModalResult,
    SplitResizeModalScreen,
    UnsavedChangeQuitModalResult,
    UnsavedChangeQuitModalScreen,
)
from textual_code.widgets.code_editor import CodeEditor
from textual_code.widgets.explorer import Explorer
from textual_code.widgets.markdown_preview import MarkdownPreviewPane
from textual_code.widgets.sidebar import Sidebar


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
        if result < 5 or result > max_width:
            return None
        return result

    # Absolute
    try:
        result = int(value)
    except ValueError:
        return None
    if result < 5 or result > max_width:
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


class MainView(Static):
    """
    Main view of the app with a tabbed content for code editors.

    Supports horizontal split view: a left and right TabbedContent side by side.
    The right panel is hidden until a split is opened.
    """

    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("ctrl+shift+s", "save_all", "Save all"),
        Binding("ctrl+w", "close", "Close tab", priority=True),
        Binding("ctrl+shift+w", "close_all", "Close all", priority=True),
        Binding("ctrl+g", "goto_line", "Goto line"),
        Binding("ctrl+f", "find", "Find", priority=True),
        Binding("ctrl+h", "replace", "Replace", priority=True),
        Binding("ctrl+alt+down", "add_cursor_below", "Add cursor below", show=False),
        Binding("ctrl+alt+up", "add_cursor_above", "Add cursor above", show=False),
        Binding(
            "ctrl+shift+l",
            "select_all_occurrences",
            "Select all occurrences",
            show=False,
            priority=True,
        ),
        Binding(
            "ctrl+d",
            "add_next_occurrence",
            "Add next occurrence",
            show=False,
            priority=True,
        ),
        Binding(
            "ctrl+backslash",
            "split_right",
            "Split editor right",
            show=False,
        ),
        Binding(
            "ctrl+shift+backslash",
            "close_split",
            "Close split",
            show=False,
        ),
        Binding(
            "ctrl+shift+m",
            "toggle_markdown_preview",
            "Toggle preview",
            show=False,
        ),
        Binding(
            "ctrl+alt+backslash",
            "move_tab_to_other_split",
            "Move tab to other split",
            show=False,
        ),
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # Per-split pane tracking: {"left": set(), "right": set()}
        self._pane_ids: dict[str, set[str]] = {"left": set(), "right": set()}
        # Per-split file tracking: {"left": {path: pane_id}, "right": {path: pane_id}}
        self._opened_files: dict[str, dict[Path, str]] = {
            "left": {},
            "right": {},
        }
        # Which split currently has focus
        self._active_split: str = "left"
        # Whether the right split panel is visible
        self._split_visible: bool = False
        # Whether the markdown preview panel is visible
        self._preview_visible: bool = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="split_container"):
            yield TabbedContent(id="split_left")
            yield TabbedContent(id="split_right")
            yield MarkdownPreviewPane(id="markdown_preview")

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def opened_pane_ids(self) -> set[str]:
        """All open pane IDs across both splits (read-only union)."""
        return self._pane_ids["left"] | self._pane_ids["right"]

    @property
    def _active_pane_ids(self) -> set[str]:
        """Mutable set for the active split's pane IDs."""
        return self._pane_ids[self._active_split]

    @property
    def opened_files(self) -> dict[Path, str]:
        """Open files in the active split (mutable — mutations affect active split)."""
        return self._opened_files[self._active_split]

    @property
    def tabbed_content(self) -> TabbedContent:
        """The active split's TabbedContent."""
        return self.query_one(f"#split_{self._active_split}", TabbedContent)

    @property
    def left_tabbed_content(self) -> TabbedContent:
        return self.query_one("#split_left", TabbedContent)

    @property
    def right_tabbed_content(self) -> TabbedContent:
        return self.query_one("#split_right", TabbedContent)

    # ── Split helpers ─────────────────────────────────────────────────────────

    def _split_of_pane(self, pane_id: str) -> str | None:
        """Return 'left' or 'right' for the split that owns pane_id, or None."""
        if pane_id in self._pane_ids["left"]:
            return "left"
        if pane_id in self._pane_ids["right"]:
            return "right"
        return None

    def _tc_for_pane(self, pane_id: str) -> TabbedContent | None:
        """Return the TabbedContent that owns pane_id, or None."""
        split = self._split_of_pane(pane_id)
        if split is None:
            return None
        return self.query_one(f"#split_{split}", TabbedContent)

    def _get_active_code_editor_in_split(self, split: str) -> "CodeEditor | None":
        """Return the active CodeEditor in the given split, or None."""
        tc = self.query_one(f"#split_{split}", TabbedContent)
        active_id = tc.active
        if not active_id:
            return None
        pane = tc.get_pane(active_id)
        return pane.query_one(CodeEditor)

    def _set_active_split(self, split: str) -> None:
        """Switch focus to the given split and focus its active editor."""
        self._active_split = split
        editor = self._get_active_code_editor_in_split(split)
        if editor:
            editor.editor.focus()
        else:
            self.query_one(f"#split_{split}", TabbedContent).focus()

    def _auto_close_split_if_empty(self) -> None:
        """Hide the right split and reset state if it has no open panes."""
        if self._split_visible and not self._pane_ids["right"]:
            self._split_visible = False
            self.right_tabbed_content.display = False
            self._active_split = "left"
            editor = self._get_active_code_editor_in_split("left")
            if editor:
                editor.editor.focus()

    # ── Pane management ───────────────────────────────────────────────────────

    def is_opened_pane(self, pane_id: str) -> bool:
        """Check if a pane is already opened by its pane_id."""
        return pane_id in self.opened_pane_ids

    def pane_id_from_path(self, path: Path) -> str | None:
        """Get the pane_id for a path in the active split, or None."""
        return self._opened_files[self._active_split].get(path, None)

    async def open_new_pane(self, pane_id: str, pane: TabPane) -> bool:
        """
        Open a new pane in the active split if not already opened.

        Returns True if a new pane was opened.
        """
        if self.is_opened_pane(pane_id):
            return False
        self._active_pane_ids.add(pane_id)
        await self.tabbed_content.add_pane(pane)
        return True

    async def close_pane(self, pane_id: str) -> bool:
        """
        Close a pane by its pane_id (routes to the correct split).

        Returns True if the pane was closed.
        """
        split = self._split_of_pane(pane_id)
        if split is None:
            return False
        tc = self.query_one(f"#split_{split}", TabbedContent)
        await tc.remove_pane(pane_id)
        self._pane_ids[split].discard(pane_id)
        return True

    def focus_pane(self, pane_id: str) -> bool:
        """
        Focus a pane by its pane_id (routes to the correct split).

        Returns True if the pane was focused.
        """
        split = self._split_of_pane(pane_id)
        if split is None:
            return False
        tc = self.query_one(f"#split_{split}", TabbedContent)
        if tc.active != pane_id:
            tc.active = pane_id
        tc.get_pane(pane_id).focus()
        self._active_split = split
        return True

    async def open_code_editor_pane(self, path: Path | None = None) -> str:
        """
        Open a new code editor pane in the active split.

        Returns the pane_id of the new or existing pane.

        If a path is provided, open the file in the code editor.
        Otherwise, open a new empty code editor.

        If the file is already open in the active split, focus it instead.
        """
        if path is None:
            pane_id = CodeEditor.generate_pane_id()
        else:
            existing_pane_id = self.pane_id_from_path(path)
            if existing_pane_id is None:
                pane_id = CodeEditor.generate_pane_id()
            else:
                pane_id = existing_pane_id

        if (
            self.is_opened_pane(pane_id)
            and self._split_of_pane(pane_id) == self._active_split
        ):
            self.focus_pane(pane_id)
            return pane_id

        pane = TabPane(
            "...",  # temporary title, will be updated later
            CodeEditor(
                pane_id=pane_id,
                path=path,
                default_indent_type=getattr(self.app, "default_indent_type", "spaces"),
                default_indent_size=getattr(self.app, "default_indent_size", 4),
                default_line_ending=getattr(self.app, "default_line_ending", "lf"),
                default_encoding=getattr(self.app, "default_encoding", "utf-8"),
            ),
            id=pane_id,
        )
        if path is not None:
            self._opened_files[self._active_split][path] = pane_id
        await self.open_new_pane(pane_id, pane)
        return pane_id

    def get_active_code_editor(self) -> "CodeEditor | None":
        """Get the active code editor in the active split."""
        return self._get_active_code_editor_in_split(self._active_split)

    def has_unsaved_pane(self) -> bool:
        """Check if there is any unsaved code editor pane across all splits."""
        for pane_id in list(self.opened_pane_ids):
            tc = self._tc_for_pane(pane_id)
            if tc is None:
                continue
            pane = tc.get_pane(pane_id)
            code_editor = pane.query_one(CodeEditor)
            if code_editor.text != code_editor.initial_text:
                return True
        return False

    async def action_open_code_editor(
        self,
        path: Path | None = None,
        focus: bool = True,
    ) -> None:
        """
        Open a code editor pane with the given file path.

        Parameters:
            path: The file path to open in the code editor.
            focus: If True, focus the code editor after opening.
        """
        pane_id = await self.open_code_editor_pane(path)
        split = self._split_of_pane(pane_id) or self._active_split
        tc = self.query_one(f"#split_{split}", TabbedContent)
        tc.active = pane_id
        if focus:
            editor = tc.get_pane(pane_id).query_one(CodeEditor)
            editor.action_focus()

    async def action_close_code_editor(self, pane_id: str) -> None:
        """Close a code editor pane by its pane_id."""
        split = self._split_of_pane(pane_id)
        await self.close_pane(pane_id)
        if split:
            self._opened_files[split] = {
                k: v for k, v in self._opened_files[split].items() if v != pane_id
            }
        self._auto_close_split_if_empty()

    def action_save(self):
        """Save file in the active code editor."""
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_save()

    def action_save_all(self) -> None:
        """Save all open code editors with unsaved changes."""
        editors = []
        for pane_id in list(self.opened_pane_ids):
            tc = self._tc_for_pane(pane_id)
            if tc is None:
                continue
            pane = tc.get_pane(pane_id)
            code_editor = pane.query_one(CodeEditor)
            if code_editor.text != code_editor.initial_text:
                editors.append(code_editor)
        # Files with paths first (save synchronously), untitled last (needs modal)
        editors.sort(key=lambda e: e.path is None)
        self._save_next(editors)

    def _save_next(self, editors: list["CodeEditor"]) -> None:
        if not editors:
            return
        editor = editors[0]
        remaining = editors[1:]
        if editor.path is not None:
            editor.action_save()
            self._save_next(remaining)
        else:
            split = self._split_of_pane(editor.pane_id) or self._active_split
            tc = self.query_one(f"#split_{split}", TabbedContent)
            tc.active = editor.pane_id
            self._active_split = split
            editor.action_save_as(on_complete=lambda: self._save_next(remaining))

    def action_close(self):
        """Close the active code editor."""
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_close()

    def action_goto_line(self) -> None:
        """Open the Goto Line modal for the active code editor."""
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_goto_line()

    def action_find(self) -> None:
        """Open the Find modal for the active code editor."""
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_find()

    def action_replace(self) -> None:
        """Open the Replace modal for the active code editor."""
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_replace()

    def action_add_cursor_below(self) -> None:
        """Add an extra cursor one line below the primary cursor."""
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_add_cursor_below()

    def action_add_cursor_above(self) -> None:
        """Add an extra cursor one line above the primary cursor."""
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_add_cursor_above()

    def action_select_all_occurrences(self) -> None:
        """Select all occurrences of the selection or word under cursor."""
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_select_all_occurrences()

    def action_add_next_occurrence(self) -> None:
        """Add a cursor at the next occurrence of the current selection or word."""
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_select_next_occurrence()

    def action_close_all(self) -> None:
        """Close all open code editors across all splits."""
        editors: list[CodeEditor] = []
        for pane_id in list(self.opened_pane_ids):
            tc = self._tc_for_pane(pane_id)
            if tc is None:
                continue
            pane = tc.get_pane(pane_id)
            editors.append(pane.query_one(CodeEditor))
        self._close_next(editors)

    def _close_next(self, editors: list["CodeEditor"]) -> None:
        if not editors:
            return
        editor = editors[0]
        remaining = editors[1:]
        editor.action_close(
            on_complete=lambda closed: self._close_next(remaining) if closed else None
        )

    # ── Split actions ─────────────────────────────────────────────────────────

    async def action_split_right(self) -> None:
        """Open the current file (or a new editor) in the right split."""
        if not self._split_visible:
            self._split_visible = True
            self.right_tabbed_content.display = True
        # Capture current file from the left split before switching
        left_editor = self._get_active_code_editor_in_split("left")
        path = left_editor.path if left_editor else None
        self._active_split = "right"
        await self.open_code_editor_pane(path)

    async def action_close_split(self) -> None:
        """Close all tabs in the right split and hide the right panel."""
        if not self._split_visible:
            return
        for pane_id in list(self._pane_ids["right"]):
            tc = self.right_tabbed_content
            pane = tc.get_pane(pane_id)
            editor = pane.query_one(CodeEditor)
            editor.action_close()

    def action_focus_left_split(self) -> None:
        """Move keyboard focus to the left split."""
        self._set_active_split("left")

    def action_focus_right_split(self) -> None:
        """Move keyboard focus to the right split (no-op if not open)."""
        if self._split_visible:
            self._set_active_split("right")

    async def action_move_tab_to_other_split(self) -> None:
        """Move the current tab to the other split panel."""
        editor = self.get_active_code_editor()
        if editor is None:
            return

        source_split = self._active_split
        other_split = "right" if source_split == "left" else "left"
        source_pane_id = editor.pane_id
        path = editor.path
        text = editor.text
        initial_text = editor.initial_text
        has_unsaved = text != initial_text

        # Show right split if it doesn't exist yet
        if other_split == "right" and not self._split_visible:
            self._split_visible = True
            self.right_tabbed_content.display = True

        # Open in destination split first (before closing source, to avoid
        # _auto_close_split_if_empty resetting _split_visible while right is empty)
        self._active_split = other_split
        new_pane_id = await self.open_code_editor_pane(path)

        # Restore unsaved content if the editor had unsaved changes
        if has_unsaved:
            tc = self.query_one(f"#split_{other_split}", TabbedContent)
            pane = tc.get_pane(new_pane_id)
            new_editor = pane.query_one(CodeEditor)
            new_editor.replace_editor_text(text)

        # Close the source pane now that the destination is ready
        await self.action_close_code_editor(source_pane_id)

        # Focus destination
        tc = self.query_one(f"#split_{other_split}", TabbedContent)
        tc.active = new_pane_id
        self._set_active_split(other_split)

    # ── Event handlers ────────────────────────────────────────────────────────

    @on(TabbedContent.TabActivated)
    async def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        # Track which split has focus when a tab is activated
        if event.control.id == "split_left":
            self._active_split = "left"
            if self._preview_visible:
                editor = self._get_active_code_editor_in_split("left")
                await self._update_markdown_preview(editor)
        elif event.control.id == "split_right":
            self._active_split = "right"

    @on(CodeEditor.TextChanged)
    async def on_code_editor_text_changed(self, event: CodeEditor.TextChanged) -> None:
        if not self._preview_visible:
            return
        left_editor = self._get_active_code_editor_in_split("left")
        if left_editor is event.code_editor:
            await self._update_markdown_preview(left_editor)

    async def action_toggle_markdown_preview(self) -> None:
        """Toggle the markdown preview panel."""
        preview = self.query_one(MarkdownPreviewPane)
        self._preview_visible = not self._preview_visible
        preview.display = self._preview_visible
        if self._preview_visible:
            editor = self._get_active_code_editor_in_split("left")
            await self._update_markdown_preview(editor)

    async def _update_markdown_preview(self, editor: "CodeEditor | None") -> None:
        """Push current editor content to the preview panel."""
        preview = self.query_one(MarkdownPreviewPane)
        if editor is None:
            await preview.update_for(text="", path=None)
        else:
            await preview.update_for(text=editor.text, path=editor.path)

    @on(CodeEditor.TitleChanged)
    def on_code_editor_title_changed(self, event: CodeEditor.TitleChanged):
        # Update the tab label when the title of the code editor changes
        if self.is_opened_pane(event.control.pane_id):
            tc = self._tc_for_pane(event.control.pane_id)
            if tc is not None:
                tc.get_tab(event.control.pane_id).label = event.control.title

    @on(CodeEditor.SavedAs)
    def on_code_editor_saved_as(self, event: CodeEditor.SavedAs):
        # Update the file tracking when a file is saved as a new path
        if event.control.path is None:
            raise ValueError("CodeEditor.SavedAs event must have a path")
        split = self._split_of_pane(event.control.pane_id) or self._active_split
        self._opened_files[split][event.control.path] = event.control.pane_id

    @on(CodeEditor.Closed)
    async def on_code_editor_closed(self, event: CodeEditor.Closed):
        # Close the pane when the code editor signals it should close
        await self.action_close_code_editor(event.control.pane_id)

    @on(CodeEditor.Deleted)
    async def on_code_editor_deleted(self, event: CodeEditor.Deleted):
        # Close the pane when the underlying file is deleted
        await self.action_close_code_editor(event.control.pane_id)


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
    ]

    def __init__(
        self, workspace_path: Path, with_open_file: Path | None, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)

        # the workspace path to open the explorer
        self.workspace_path = workspace_path
        # the file path to open in the code editor
        # if provided, the file will be opened after the app is ready
        self.with_open_file = with_open_file

        # load editor defaults from config files
        settings = load_editor_settings(workspace_path)
        self.default_indent_type: str = str(settings["indent_type"])
        self.default_indent_size: int = int(settings["indent_size"])
        self.default_line_ending: str = str(settings["line_ending"])
        self.default_encoding: str = str(settings["encoding"])

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
        yield from super().get_system_commands(screen)
        yield SystemCommand(
            "Toggle sidebar", "Show or hide the sidebar", self.action_toggle_sidebar
        )
        yield SystemCommand(
            "Reload explorer", "Reload the explorer", self.action_reload_explorer
        )
        yield SystemCommand("Save file", "Save the current file", self.action_save_file)
        yield SystemCommand(
            "Save all files", "Save all open files", self.action_save_all_files
        )
        yield SystemCommand(
            "Save file as",
            "Save the current file as new file",
            self.action_save_file_as,
        )
        yield SystemCommand(
            "New file", "Open empty code editor", self.action_new_editor
        )
        yield SystemCommand(
            "Close file", "Close the current file", self.action_close_file
        )
        yield SystemCommand(
            "Close all files", "Close all open files", self.action_close_all_files
        )
        yield SystemCommand(
            "Delete file", "Delete the current file", self.action_delete_file
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
            "Go to a specific line and column",
            self.action_goto_line_cmd,
        )
        yield SystemCommand(
            "Change language",
            "Change the syntax highlighting language",
            self.action_change_language_cmd,
        )
        yield SystemCommand(
            "Find",
            "Find text in the current file",
            self.action_find_cmd,
        )
        yield SystemCommand(
            "Replace",
            "Find and replace text in the current file",
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
            "Select all occurrences of the current selection or word",
            self.action_select_all_occurrences_cmd,
        )
        yield SystemCommand(
            "Add next occurrence",
            "Add a cursor at the next occurrence of the selection or word (Ctrl+D)",
            self.action_add_next_occurrence_cmd,
        )
        yield SystemCommand(
            "Split editor right",
            "Open current file in right split panel (Ctrl+\\)",
            self.action_split_right_cmd,
        )
        yield SystemCommand(
            "Close split",
            "Close the right split panel",
            self.action_close_split_cmd,
        )
        yield SystemCommand(
            "Focus left split",
            "Move focus to the left split panel",
            self.action_focus_left_split_cmd,
        )
        yield SystemCommand(
            "Focus right split",
            "Move focus to the right split panel",
            self.action_focus_right_split_cmd,
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
            "Toggle markdown preview",
            "Show/hide the markdown preview panel (Ctrl+Shift+M)",
            self.action_toggle_markdown_preview_cmd,
        )
        yield SystemCommand(
            "Move tab to other split",
            "Move the current tab to the other split panel (Ctrl+Alt+\\)",
            self.action_move_tab_to_other_split_cmd,
        )

    def action_toggle_markdown_preview_cmd(self) -> None:
        """Toggle markdown preview from command palette."""
        self.call_next(self.main_view.action_toggle_markdown_preview)

    def action_move_tab_to_other_split_cmd(self) -> None:
        """Move current tab to the other split via command palette."""
        self.call_next(self.main_view.action_move_tab_to_other_split)

    def action_set_default_indentation(self) -> None:
        """Set the default indentation for new files and save to user config."""

        def do_change(result: ChangeIndentModalResult | None) -> None:
            if result and not result.is_cancelled:
                self.default_indent_type = (
                    result.indent_type or self.default_indent_type
                )
                self.default_indent_size = (
                    result.indent_size or self.default_indent_size
                )
                save_user_editor_settings(
                    {
                        "indent_type": self.default_indent_type,
                        "indent_size": self.default_indent_size,
                        "line_ending": self.default_line_ending,
                        "encoding": self.default_encoding,
                    }
                )

        self.call_next(lambda: self.push_screen(ChangeIndentModalScreen(), do_change))

    def action_set_default_line_ending(self) -> None:
        """Set the default line ending for new files and save to user config."""

        def do_change(result: ChangeLineEndingModalResult | None) -> None:
            if result and not result.is_cancelled:
                self.default_line_ending = (
                    result.line_ending or self.default_line_ending
                )
                save_user_editor_settings(
                    {
                        "indent_type": self.default_indent_type,
                        "indent_size": self.default_indent_size,
                        "line_ending": self.default_line_ending,
                        "encoding": self.default_encoding,
                    }
                )

        self.call_next(
            lambda: self.push_screen(
                ChangeLineEndingModalScreen(
                    current_line_ending=self.default_line_ending
                ),
                do_change,
            )
        )

    def action_set_default_encoding(self) -> None:
        """Set the default encoding for new files and save to user config."""

        def do_change(result: ChangeEncodingModalResult | None) -> None:
            if result and not result.is_cancelled:
                self.default_encoding = result.encoding or self.default_encoding
                save_user_editor_settings(
                    {
                        "indent_type": self.default_indent_type,
                        "indent_size": self.default_indent_size,
                        "line_ending": self.default_line_ending,
                        "encoding": self.default_encoding,
                    }
                )

        self.call_next(
            lambda: self.push_screen(
                ChangeEncodingModalScreen(current_encoding=self.default_encoding),
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

    def action_split_right_cmd(self) -> None:
        """Split editor right via command palette."""
        self.call_next(self.main_view.action_split_right)

    def action_close_split_cmd(self) -> None:
        """Close split via command palette."""
        self.call_next(self.main_view.action_close_split)

    def action_focus_left_split_cmd(self) -> None:
        """Focus left split via command palette."""
        self.main_view.action_focus_left_split()

    def action_focus_right_split_cmd(self) -> None:
        """Focus right split via command palette."""
        self.main_view.action_focus_right_split()

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
            split_left = self.main_view.query_one("#split_left")
            split_container = self.main_view.query_one("#split_container")
            current_width = split_left.size.width
            total_width = split_container.size.width
            parsed = _parse_split_resize(result.value or "", current_width, total_width)
            if parsed is None:
                self.notify(
                    f"Invalid split width: {result.value!r}. "
                    "Use a number (50), +/-offset (+10), or percent (40%).",
                    severity="error",
                )
                return
            split_left.styles.width = parsed

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

    @property
    def sidebar(self) -> Sidebar:
        # Use the base screen so this works even when a modal is active
        return self.screen_stack[0].query_one(Sidebar)

    @property
    def footer(self) -> Footer:
        return self.query_one(Footer)
