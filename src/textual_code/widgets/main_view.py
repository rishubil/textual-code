from pathlib import Path

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, Static, TabbedContent, TabPane

from textual_code.widgets.code_editor import CodeEditor, CodeEditorFooter
from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent
from textual_code.widgets.markdown_preview import MarkdownPreviewPane
from textual_code.widgets.split_resize_handle import SplitResizeHandle


class MainView(Static):
    """
    Main view of the app with a tabbed content for code editors.

    Supports horizontal split view: a left and right TabbedContent side by side.
    The right panel is hidden until a split is opened.
    """

    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("ctrl+shift+s", "save_all", "Save all", show=False),
        Binding("ctrl+w", "close", "Close tab", priority=True),
        Binding("ctrl+shift+w", "close_all", "Close all", priority=True, show=False),
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
            yield DraggableTabbedContent(id="split_left", split_side="left")
            yield SplitResizeHandle()
            yield DraggableTabbedContent(id="split_right", split_side="right")
            yield MarkdownPreviewPane(id="markdown_preview")
        yield CodeEditorFooter()

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
            self.query_one(SplitResizeHandle).display = False
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
                default_syntax_theme=getattr(
                    self.app, "default_syntax_theme", "monokai"
                ),
                default_word_wrap=getattr(self.app, "default_word_wrap", False),
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
        self._sync_footer_to_active_editor()

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
            self.query_one(SplitResizeHandle).display = True
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

    def action_find_in_workspace(self) -> None:
        """Open the workspace search panel in the sidebar."""
        sidebar = self.app.sidebar
        sidebar.display = True
        sidebar.tabbed_content.active = "search_pane"
        sidebar.workspace_search.focus_query_input()

    def action_focus_left_split(self) -> None:
        """Move keyboard focus to the left split."""
        self._set_active_split("left")

    def action_focus_right_split(self) -> None:
        """Move keyboard focus to the right split (no-op if not open)."""
        if self._split_visible:
            self._set_active_split("right")

    async def _move_pane_to_split(
        self, source_pane_id: str, dest_split: str
    ) -> str | None:
        """Move a pane to dest_split. Returns new_pane_id or None on failure.

        If dest_split already has the same file open, focuses that pane and
        closes the source — no duplicate tab is created.
        """
        source_split = self._split_of_pane(source_pane_id)
        if source_split is None:
            return None

        tc_source = self.query_one(f"#split_{source_split}", TabbedContent)
        pane = tc_source.get_pane(source_pane_id)
        editor = pane.query_one(CodeEditor)
        path = editor.path
        text = editor.text
        has_unsaved = text != editor.initial_text

        # Show right split if not visible
        if dest_split == "right" and not self._split_visible:
            self._split_visible = True
            self.right_tabbed_content.display = True
            self.query_one(SplitResizeHandle).display = True

        # Check for duplicate file in destination
        if path is not None and path in self._opened_files[dest_split]:
            existing_pane_id = self._opened_files[dest_split][path]
            await self.action_close_code_editor(source_pane_id)
            tc_dest = self.query_one(f"#split_{dest_split}", TabbedContent)
            tc_dest.active = existing_pane_id
            self._set_active_split(dest_split)
            return existing_pane_id

        # Open in destination split first (before closing source, to avoid
        # _auto_close_split_if_empty resetting _split_visible while right is empty)
        self._active_split = dest_split
        new_pane_id = await self.open_code_editor_pane(path)

        # Restore unsaved content if the editor had unsaved changes
        if has_unsaved:
            tc_dest = self.query_one(f"#split_{dest_split}", TabbedContent)
            new_editor = tc_dest.get_pane(new_pane_id).query_one(CodeEditor)
            new_editor.replace_editor_text(text)

        # Close the source pane now that the destination is ready
        await self.action_close_code_editor(source_pane_id)
        return new_pane_id

    async def action_move_tab_to_other_split(self) -> None:
        """Move the current tab to the other split panel."""
        editor = self.get_active_code_editor()
        if editor is None:
            return

        source_split = self._active_split
        other_split = "right" if source_split == "left" else "left"
        new_pane_id = await self._move_pane_to_split(editor.pane_id, other_split)
        if new_pane_id is None:
            return

        tc = self.query_one(f"#split_{other_split}", TabbedContent)
        tc.active = new_pane_id
        self._set_active_split(other_split)

    # ── Footer helpers ────────────────────────────────────────────────────────

    def _sync_footer_to_active_editor(self) -> None:
        """Update the global CodeEditorFooter to reflect the active editor's state."""
        footer = self.query_one(CodeEditorFooter)
        editor = self.get_active_code_editor()
        if editor is None:
            footer.reset()
            return
        footer.path = editor.path
        footer.language = editor.language
        footer.line_ending = editor.line_ending
        footer.encoding = editor.encoding
        footer.indent_type = editor.indent_type
        footer.indent_size = editor.indent_size
        footer.cursor_location = editor.editor.selection.end
        footer.cursor_count = 1 + len(editor.editor.extra_cursors)

    # ── Event handlers ────────────────────────────────────────────────────────

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        # Update _active_split when focus moves into a split panel.
        # Covers the case where the user clicks inside the editor content
        # (not the tab bar), which does not trigger TabbedContent.TabActivated.
        widget = event.widget
        for ancestor in widget.ancestors_with_self:
            if ancestor.id == "split_left":
                self._active_split = "left"
                break
            if ancestor.id == "split_right":
                self._active_split = "right"
                break

    @on(TabbedContent.TabActivated)
    async def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        # _active_split is also updated by on_descendant_focus.
        # This handler is kept for markdown preview synchronization.
        # Track which split has focus when a tab is activated
        if event.control.id == "split_left":
            self._active_split = "left"
            if self._preview_visible:
                editor = self._get_active_code_editor_in_split("left")
                await self._update_markdown_preview(editor)
        elif event.control.id == "split_right":
            self._active_split = "right"
        self._sync_footer_to_active_editor()

    @on(DraggableTabbedContent.TabMovedToOtherSplit)
    async def on_tab_moved_to_other_split(
        self, event: DraggableTabbedContent.TabMovedToOtherSplit
    ) -> None:
        source_split = self._split_of_pane(event.source_pane_id)
        if source_split is None:
            return
        dest_split = "right" if source_split == "left" else "left"

        new_pane_id = await self._move_pane_to_split(event.source_pane_id, dest_split)
        if new_pane_id is None:
            return

        # Reorder the new pane relative to the drop target (skip when edge-drop)
        if event.target_pane_id is not None:
            dest_tc = self.query_one(f"#split_{dest_split}", DraggableTabbedContent)
            dest_tc.reorder_tab(new_pane_id, event.target_pane_id, before=event.before)

        tc = self.query_one(f"#split_{dest_split}", TabbedContent)
        tc.active = new_pane_id
        self._set_active_split(dest_split)
        event.stop()

    @on(CodeEditor.FooterStateChanged)
    def on_footer_state_changed(self, event: CodeEditor.FooterStateChanged) -> None:
        if event.code_editor is not self.get_active_code_editor():
            return
        self._sync_footer_to_active_editor()

    @on(Button.Pressed, "CodeEditorFooter #cursor_btn")
    def on_footer_cursor_btn(self, event: Button.Pressed) -> None:
        event.stop()
        if editor := self.get_active_code_editor():
            editor.action_goto_line()

    @on(Button.Pressed, "CodeEditorFooter #line_ending_btn")
    def on_footer_line_ending_btn(self, event: Button.Pressed) -> None:
        event.stop()
        if editor := self.get_active_code_editor():
            editor.action_change_line_ending()

    @on(Button.Pressed, "CodeEditorFooter #encoding_btn")
    def on_footer_encoding_btn(self, event: Button.Pressed) -> None:
        event.stop()
        if editor := self.get_active_code_editor():
            editor.action_change_encoding()

    @on(Button.Pressed, "CodeEditorFooter #indent_btn")
    def on_footer_indent_btn(self, event: Button.Pressed) -> None:
        event.stop()
        if editor := self.get_active_code_editor():
            editor.action_change_indent()

    @on(Button.Pressed, "CodeEditorFooter #language")
    def on_footer_language_btn(self, event: Button.Pressed) -> None:
        event.stop()
        if editor := self.get_active_code_editor():
            editor.action_change_language()

    @on(CodeEditor.TextChanged)
    async def on_code_editor_text_changed(self, event: CodeEditor.TextChanged) -> None:
        if not self._preview_visible:
            return
        left_editor = self._get_active_code_editor_in_split("left")
        if left_editor is event.code_editor:
            await self._update_markdown_preview(left_editor)

    def action_toggle_split_vertical(self) -> None:
        """Toggle between horizontal and vertical split orientation."""
        container = self.query_one("#split_container")
        container.toggle_class("split-vertical")

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
