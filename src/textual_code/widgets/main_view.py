from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.timer import Timer
from textual.widgets import Button, Static, TabbedContent, TabPane

from textual_code.utils import is_binary_file
from textual_code.widgets.code_editor import CodeEditor, CodeEditorFooter
from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent
from textual_code.widgets.markdown_preview import (
    MARKDOWN_EXTENSIONS,
    MarkdownPreviewPane,
)
from textual_code.widgets.split_container import SplitContainer, build_split_widgets
from textual_code.widgets.split_resize_handle import SplitResizeHandle
from textual_code.widgets.split_tree import (
    BranchNode,
    LeafNode,
    adjacent_leaf,
    all_leaves,
    all_pane_ids,
    find_leaf,
    make_leaf,
    parent_of,
    remove_leaf,
    split_leaf,
)

log = logging.getLogger(__name__)

PREVIEW_DEBOUNCE_DELAY = 0.3


class MainView(Static):
    """
    Main view of the app with a tabbed content for code editors.

    Supports recursive split view: unlimited nested horizontal/vertical splits.
    Uses a tree data structure (split_tree) internally.
    """

    class ActiveFileChanged(Message):
        """Posted when the active tab's file changes."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

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
            "open_markdown_preview_tab",
            "Open markdown preview tab",
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

        # Tree-based state
        initial_leaf = make_leaf()
        self._split_root: LeafNode | BranchNode = initial_leaf
        self._active_leaf_id: str = initial_leaf.leaf_id
        self._pane_to_leaf: dict[str, str] = {}  # pane_id → leaf_id

        # Map from source file path to open preview pane_id
        self._preview_pane_ids: dict[Path, str] = {}
        # Debounce timers for preview updates, keyed by source file path
        self._preview_update_timers: dict[Path, Timer] = {}

    def compose(self) -> ComposeResult:
        yield build_split_widgets(self._split_root)
        yield CodeEditorFooter()

    # ── Compatibility properties ─────────────────────────────────────────────
    # These provide backward-compatible access for tests and app.py

    @property
    def _split_visible(self) -> bool:
        """Whether more than one split is visible."""
        return isinstance(self._split_root, BranchNode)

    @property
    def _active_split(self) -> str:
        """Backward compat: return 'left' or 'right' based on active leaf position."""
        if isinstance(self._split_root, LeafNode):
            return "left"
        leaves = all_leaves(self._split_root)
        for i, leaf in enumerate(leaves):
            if leaf.leaf_id == self._active_leaf_id:
                return "left" if i == 0 else "right"
        return "left"

    @_active_split.setter
    def _active_split(self, value: str) -> None:
        """Backward compat: set active leaf by 'left'/'right'."""
        if isinstance(self._split_root, LeafNode):
            return
        leaves = all_leaves(self._split_root)
        if value == "left" and leaves:
            self._active_leaf_id = leaves[0].leaf_id
        elif value == "right" and len(leaves) > 1:
            self._active_leaf_id = leaves[1].leaf_id

    @property
    def _pane_ids(self) -> dict[str, set[str]]:
        """Backward compat: {'left': set, 'right': set}."""
        leaves = all_leaves(self._split_root)
        result: dict[str, set[str]] = {"left": set(), "right": set()}
        for i, leaf in enumerate(leaves):
            key = "left" if i == 0 else "right"
            result[key].update(leaf.pane_ids)
        return result

    @property
    def _opened_files(self) -> dict[str, dict[Path, str]]:
        """Backward compat: {'left': dict, 'right': dict}."""
        leaves = all_leaves(self._split_root)
        result: dict[str, dict[Path, str]] = {"left": {}, "right": {}}
        for i, leaf in enumerate(leaves):
            key = "left" if i == 0 else "right"
            result[key].update(leaf.opened_files)
        return result

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def _active_leaf(self) -> LeafNode:
        leaf = find_leaf(self._split_root, self._active_leaf_id)
        assert leaf is not None
        return leaf

    @property
    def opened_pane_ids(self) -> set[str]:
        """All open pane IDs across all leaves."""
        return all_pane_ids(self._split_root)

    @property
    def _active_pane_ids(self) -> set[str]:
        """Mutable set for the active leaf's pane IDs."""
        return self._active_leaf.pane_ids

    @property
    def opened_files(self) -> dict[Path, str]:
        """Open files in the active leaf."""
        return self._active_leaf.opened_files

    @property
    def tabbed_content(self) -> TabbedContent:
        """The active leaf's TabbedContent."""
        return self.query_one(f"#{self._active_leaf_id}", TabbedContent)

    @property
    def left_tabbed_content(self) -> TabbedContent:
        """First leaf's TabbedContent."""
        leaves = all_leaves(self._split_root)
        return self.query_one(f"#{leaves[0].leaf_id}", TabbedContent)

    @property
    def right_tabbed_content(self) -> TabbedContent:
        """Second leaf's TabbedContent (or raises if not split)."""
        leaves = all_leaves(self._split_root)
        if len(leaves) < 2:
            # Return a DraggableTabbedContent that is not displayed for compat
            return self.query_one(f"#{leaves[0].leaf_id}", TabbedContent)
        return self.query_one(f"#{leaves[1].leaf_id}", TabbedContent)

    # ── Leaf helpers ─────────────────────────────────────────────────────────

    def _leaf_of_pane(self, pane_id: str) -> LeafNode | None:
        """Return the LeafNode that owns pane_id, or None."""
        leaf_id = self._pane_to_leaf.get(pane_id)
        if leaf_id is None:
            return None
        return find_leaf(self._split_root, leaf_id)

    def _split_of_pane(self, pane_id: str) -> str | None:
        """Backward compat: return 'left' or 'right' for the split that owns pane_id."""
        leaf = self._leaf_of_pane(pane_id)
        if leaf is None:
            return None
        leaves = all_leaves(self._split_root)
        for i, lf in enumerate(leaves):
            if lf is leaf:
                return "left" if i == 0 else "right"
        return None

    def _tc_for_pane(self, pane_id: str) -> TabbedContent | None:
        """Return the TabbedContent that owns pane_id, or None."""
        leaf = self._leaf_of_pane(pane_id)
        if leaf is None:
            return None
        return self.query_one(f"#{leaf.leaf_id}", TabbedContent)

    def _get_active_code_editor_in_leaf(self, leaf: LeafNode) -> CodeEditor | None:
        """Return the active CodeEditor in the given leaf, or None."""
        tc = self.query_one(f"#{leaf.leaf_id}", TabbedContent)
        active_id = tc.active
        if not active_id:
            return None
        pane = tc.get_pane(active_id)
        editors = pane.query(CodeEditor)
        return editors.first(CodeEditor) if editors else None

    def _get_active_code_editor_in_split(self, split: str) -> CodeEditor | None:
        """Backward compat: get active editor by 'left'/'right'."""
        leaves = all_leaves(self._split_root)
        if split == "left" and leaves:
            return self._get_active_code_editor_in_leaf(leaves[0])
        if split == "right" and len(leaves) > 1:
            return self._get_active_code_editor_in_leaf(leaves[1])
        return None

    def _set_active_split(self, split: str) -> None:
        """Switch focus to the given split and focus its active editor."""
        self._active_split = split
        leaf = self._active_leaf
        editor = self._get_active_code_editor_in_leaf(leaf)
        if editor:
            editor.editor.focus()
        else:
            self.query_one(f"#{leaf.leaf_id}", TabbedContent).focus()

    def _set_active_leaf(self, leaf: LeafNode) -> None:
        """Switch focus to the given leaf."""
        self._active_leaf_id = leaf.leaf_id
        editor = self._get_active_code_editor_in_leaf(leaf)
        if editor:
            editor.editor.focus()
        else:
            self.query_one(f"#{leaf.leaf_id}", TabbedContent).focus()

    async def _auto_close_split_if_empty(self) -> None:
        """Remove empty leaves from the tree."""
        if isinstance(self._split_root, LeafNode):
            return

        changed = True
        while changed:
            changed = False
            leaves = all_leaves(self._split_root)
            if len(leaves) <= 1:
                break
            for idx, leaf in enumerate(leaves):
                if not leaf.pane_ids:
                    new_root = remove_leaf(self._split_root, leaf.leaf_id)
                    if new_root is None:
                        break
                    await self._collapse_leaf_widget(leaf, new_root)
                    self._split_root = new_root

                    if self._active_leaf_id == leaf.leaf_id:
                        remaining = all_leaves(self._split_root)
                        nearest = min(idx, len(remaining) - 1)
                        self._active_leaf_id = remaining[nearest].leaf_id

                    changed = True
                    break  # restart iteration since tree changed

        # Focus active editor
        active_leaf = self._active_leaf
        editor = self._get_active_code_editor_in_leaf(active_leaf)
        if editor:
            editor.editor.focus()

    async def _collapse_leaf_widget(
        self, removed_leaf: LeafNode, new_root: LeafNode | BranchNode
    ) -> None:
        """Remove widgets for collapsed leaf and restructure."""
        removed_widget = self.query_one(
            f"#{removed_leaf.leaf_id}", DraggableTabbedContent
        )
        parent_container = removed_widget.parent

        if not isinstance(parent_container, SplitContainer):
            await removed_widget.remove()
            return

        # Remove the DTC and its handle
        await removed_widget.remove()

        handles = list(parent_container.query(SplitResizeHandle))
        if handles:
            await handles[-1].remove()

        # If only one child remains in the container, reparent it to grandparent
        non_handle_children = [
            c for c in parent_container.children if not isinstance(c, SplitResizeHandle)
        ]
        if len(non_handle_children) == 1:
            surviving = non_handle_children[0]
            grandparent = parent_container.parent
            if grandparent is not None:
                # Reparent: move surviving widget from container to grandparent
                parent_container._nodes._remove(surviving)
                surviving._detach()
                idx = grandparent._nodes.index(parent_container)
                surviving._attach(grandparent)
                grandparent._nodes._insert(idx, surviving)
                self.app.stylesheet.apply(surviving)
                # Now parent_container is empty (surviving removed above),
                # so .remove() won't destroy any reparented children
                await parent_container.remove()
                grandparent.refresh(layout=True)

    # ── Pane management ──────────────────────────────────────────────────────

    def is_opened_pane(self, pane_id: str) -> bool:
        return pane_id in self.opened_pane_ids

    def pane_id_from_path(self, path: Path) -> str | None:
        """Get the pane_id for a path in the active leaf, or None."""
        return self._active_leaf.opened_files.get(path, None)

    async def open_new_pane(
        self, pane_id: str, pane: TabPane, *, leaf_id: str | None = None
    ) -> bool:
        target_leaf_id = leaf_id or self._active_leaf_id
        if self.is_opened_pane(pane_id):
            return False
        leaf = find_leaf(self._split_root, target_leaf_id)
        if leaf is None:
            return False
        leaf.pane_ids.add(pane_id)
        self._pane_to_leaf[pane_id] = target_leaf_id
        tc = self.query_one(f"#{target_leaf_id}", TabbedContent)
        await tc.add_pane(pane)
        return True

    async def close_pane(self, pane_id: str) -> bool:
        leaf = self._leaf_of_pane(pane_id)
        if leaf is None:
            return False
        tc = self.query_one(f"#{leaf.leaf_id}", TabbedContent)
        await tc.remove_pane(pane_id)
        leaf.pane_ids.discard(pane_id)
        self._pane_to_leaf.pop(pane_id, None)
        return True

    def focus_pane(self, pane_id: str) -> bool:
        leaf = self._leaf_of_pane(pane_id)
        if leaf is None:
            return False
        tc = self.query_one(f"#{leaf.leaf_id}", TabbedContent)
        if tc.active != pane_id:
            tc.active = pane_id
        pane = tc.get_pane(pane_id)
        # Focus the first focusable descendant (e.g. CodeEditor, MarkdownPreviewPane)
        focusable = (
            pane.query("*:can-focus").first() if pane.query("*:can-focus") else None
        )
        if focusable is not None:
            focusable.focus()
        else:
            pane.focus()
        self._active_leaf_id = leaf.leaf_id
        return True

    async def open_code_editor_pane(
        self, path: Path | None = None, *, leaf_id: str | None = None
    ) -> str:
        target_leaf_id = leaf_id or self._active_leaf_id
        target_leaf = find_leaf(self._split_root, target_leaf_id)
        assert target_leaf is not None

        if path is None:
            pane_id = CodeEditor.generate_pane_id()
        else:
            existing_pane_id = target_leaf.opened_files.get(path, None)
            if existing_pane_id is None:
                pane_id = CodeEditor.generate_pane_id()
            else:
                pane_id = existing_pane_id

        if (
            self.is_opened_pane(pane_id)
            and self._pane_to_leaf.get(pane_id) == target_leaf_id
        ):
            self.focus_pane(pane_id)
            return pane_id

        if path is not None and is_binary_file(path):
            pane = TabPane(
                path.name,
                Static("⚠  Binary file — not supported", classes="binary-notice"),
                id=pane_id,
            )
            target_leaf.opened_files[path] = pane_id
            await self.open_new_pane(pane_id, pane, leaf_id=target_leaf_id)
            return pane_id

        pane = TabPane(
            "...",
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
            target_leaf.opened_files[path] = pane_id
        await self.open_new_pane(pane_id, pane, leaf_id=target_leaf_id)
        return pane_id

    def get_active_code_editor(self) -> CodeEditor | None:
        return self._get_active_code_editor_in_leaf(self._active_leaf)

    def has_unsaved_pane(self) -> bool:
        for pane_id in list(self.opened_pane_ids):
            tc = self._tc_for_pane(pane_id)
            if tc is None:
                continue
            pane = tc.get_pane(pane_id)
            editors = pane.query(CodeEditor)
            if not editors:
                continue
            code_editor = editors.first(CodeEditor)
            if code_editor.text != code_editor.initial_text:
                return True
        return False

    async def action_open_code_editor(
        self,
        path: Path | None = None,
        focus: bool = True,
    ) -> None:
        pane_id = await self.open_code_editor_pane(path)
        leaf = self._leaf_of_pane(pane_id)
        if leaf is None:
            leaf = self._active_leaf
        tc = self.query_one(f"#{leaf.leaf_id}", TabbedContent)
        tc.active = pane_id
        if focus:
            editors = tc.get_pane(pane_id).query(CodeEditor)
            if editors:
                editors.first(CodeEditor).action_focus()

    async def action_close_code_editor(
        self, pane_id: str, *, auto_close_split: bool = True
    ) -> None:
        leaf = self._leaf_of_pane(pane_id)
        await self.close_pane(pane_id)
        if leaf:
            leaf.opened_files = {
                k: v for k, v in leaf.opened_files.items() if v != pane_id
            }
        if auto_close_split:
            await self._auto_close_split_if_empty()
        self._sync_footer_to_active_editor()

    def action_save(self):
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_save()

    def action_save_all(self) -> None:
        editors = []
        for pane_id in list(self.opened_pane_ids):
            tc = self._tc_for_pane(pane_id)
            if tc is None:
                continue
            pane = tc.get_pane(pane_id)
            pane_editors = pane.query(CodeEditor)
            if not pane_editors:
                continue
            code_editor = pane_editors.first(CodeEditor)
            if code_editor.text != code_editor.initial_text:
                editors.append(code_editor)
        editors.sort(key=lambda e: e.path is None)
        self._save_next(editors)

    def _save_next(self, editors: list[CodeEditor]) -> None:
        if not editors:
            return
        editor = editors[0]
        remaining = editors[1:]
        if editor.path is not None:
            editor.action_save()
            self._save_next(remaining)
        else:
            leaf = self._leaf_of_pane(editor.pane_id)
            if leaf is not None:
                self._active_leaf_id = leaf.leaf_id
            tc = self.tabbed_content
            tc.active = editor.pane_id
            editor.action_save_as(on_complete=lambda: self._save_next(remaining))

    async def action_close(self) -> None:
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_close()
        else:
            tc = self.tabbed_content
            pane_id = tc.active
            if pane_id and self.is_opened_pane(pane_id):
                # Cancel any pending debounce timer for this preview
                for path, pid in list(self._preview_pane_ids.items()):
                    if pid == pane_id:
                        self._cancel_preview_timer(path)
                self._preview_pane_ids = {
                    path: pid
                    for path, pid in self._preview_pane_ids.items()
                    if pid != pane_id
                }
                await self.close_pane(pane_id)
                await self._auto_close_split_if_empty()
                self._sync_footer_to_active_editor()

    def action_goto_line(self) -> None:
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_goto_line()

    def action_find(self) -> None:
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_find()

    def action_replace(self) -> None:
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_replace()

    def action_add_cursor_below(self) -> None:
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_add_cursor_below()

    def action_add_cursor_above(self) -> None:
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_add_cursor_above()

    def action_select_all_occurrences(self) -> None:
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_select_all_occurrences()

    def action_add_next_occurrence(self) -> None:
        code_editor = self.get_active_code_editor()
        if code_editor is not None:
            code_editor.action_select_next_occurrence()

    def action_close_all(self) -> None:
        editors: list[CodeEditor] = []
        for pane_id in list(self.opened_pane_ids):
            tc = self._tc_for_pane(pane_id)
            if tc is None:
                continue
            pane = tc.get_pane(pane_id)
            pane_editors = pane.query(CodeEditor)
            if pane_editors:
                editors.append(pane_editors.first(CodeEditor))
        self._close_next(editors)

    def _close_next(self, editors: list[CodeEditor]) -> None:
        if not editors:
            return
        editor = editors[0]
        remaining = editors[1:]
        editor.action_close(
            on_complete=lambda closed: self._close_next(remaining) if closed else None
        )

    # ── Split actions ────────────────────────────────────────────────────────

    async def action_split_right(self) -> None:
        """Open the current file (or a new editor) in a new split to the right."""
        # Capture current file from the active leaf before splitting
        active_editor = self.get_active_code_editor()
        path = active_editor.path if active_editor else None

        await self._do_split(path, "horizontal")

    async def action_split_down(self) -> None:
        """Open the current file (or a new editor) in a new split below."""
        active_editor = self.get_active_code_editor()
        path = active_editor.path if active_editor else None
        await self._do_split(path, "vertical")

    async def _do_split(self, path: Path | None, direction: str) -> None:
        """Create a new split in the given direction."""
        if isinstance(self._split_root, LeafNode):
            # First split: create a branch
            new_root, new_leaf = split_leaf(
                self._split_root, self._active_leaf_id, direction
            )
            self._split_root = new_root
            await self._mount_new_split(new_leaf, direction)
        else:
            # Already split: create new leaf
            new_root, new_leaf = split_leaf(
                self._split_root, self._active_leaf_id, direction
            )
            old_root = self._split_root
            self._split_root = new_root
            await self._mount_new_split_in_existing(new_leaf, old_root)

        # Open editor in the new leaf and focus it
        self._active_leaf_id = new_leaf.leaf_id
        pane_id = await self.open_code_editor_pane(path, leaf_id=new_leaf.leaf_id)
        # Ensure DOM focus moves to the new leaf's editor
        tc = self.query_one(f"#{new_leaf.leaf_id}", TabbedContent)
        tc.active = pane_id
        editors = tc.get_pane(pane_id).query(CodeEditor)
        if editors:
            editors.first(CodeEditor).editor.focus()

    async def _mount_new_split(self, new_leaf: LeafNode, direction: str) -> None:
        """Mount a new split when going from 1 leaf to 2 (first split)."""
        leaves = all_leaves(self._split_root)
        assert len(leaves) == 2

        # Get the existing DTC
        existing_dtc = self.query_one(f"#{leaves[0].leaf_id}", DraggableTabbedContent)

        # Create new DTC and handle
        new_dtc = DraggableTabbedContent(id=new_leaf.leaf_id)
        handle = SplitResizeHandle(child_index=0)

        # Create SplitContainer, mount after existing DTC, then reparent
        container = SplitContainer(direction=direction)
        parent = existing_dtc.parent
        await parent.mount(container, after=existing_dtc)

        # Reparent existing DTC into container via DOM manipulation
        # Must remove from old parent's _nodes first, then attach to new parent
        parent._nodes._remove(existing_dtc)
        existing_dtc._detach()
        existing_dtc._attach(container)
        container._nodes._append(existing_dtc)

        # Re-apply CSS for new parent context and mount new children
        self.app.stylesheet.apply(existing_dtc)
        await container.mount(handle)
        await container.mount(new_dtc)
        container.refresh(layout=True)

    async def _mount_new_split_in_existing(
        self, new_leaf: LeafNode, old_root: LeafNode | BranchNode
    ) -> None:
        """Mount a new split when there are already multiple splits."""
        parent_node = parent_of(self._split_root, new_leaf)

        if parent_node is not None:
            idx = parent_node.children.index(new_leaf)
            if idx > 0:
                sibling = parent_node.children[idx - 1]
            else:
                sibling = parent_node.children[1]

            if isinstance(sibling, LeafNode):
                sibling_widget = self.query_one(
                    f"#{sibling.leaf_id}", DraggableTabbedContent
                )
            else:
                sibling_leaves = all_leaves(sibling)
                sibling_widget = self.query_one(
                    f"#{sibling_leaves[0].leaf_id}", DraggableTabbedContent
                )

            container = sibling_widget.parent
            new_dtc = DraggableTabbedContent(id=new_leaf.leaf_id)

            if (
                isinstance(container, SplitContainer)
                and container.direction == parent_node.direction
            ):
                handle = SplitResizeHandle(child_index=len(parent_node.children) - 2)
                await container.mount(handle)
                await container.mount(new_dtc)
            else:
                handle = SplitResizeHandle(child_index=0)
                old_widget = sibling_widget
                new_container = SplitContainer(direction=parent_node.direction)

                p = old_widget.parent
                # Mount new container at old_widget's position, then reparent
                await p.mount(new_container, after=old_widget)
                # Reparent old_widget into new container via DOM manipulation
                p._nodes._remove(old_widget)
                old_widget._detach()
                old_widget._attach(new_container)
                new_container._nodes._append(old_widget)
                self.app.stylesheet.apply(old_widget)
                await new_container.mount(handle)
                await new_container.mount(new_dtc)
                new_container.refresh(layout=True)

    async def action_close_split(self) -> None:
        """Close all tabs in the active split (unless it's the last one)."""
        if isinstance(self._split_root, LeafNode):
            return
        # Close all panes in the active leaf
        active_leaf = self._active_leaf
        for pane_id in list(active_leaf.pane_ids):
            tc = self.query_one(f"#{active_leaf.leaf_id}", TabbedContent)
            pane = tc.get_pane(pane_id)
            pane_editors = pane.query(CodeEditor)
            if pane_editors:
                pane_editors.first(CodeEditor).action_close()
            else:
                # Binary pane: close directly
                self.app.call_later(self.action_close_code_editor, pane_id)

    def action_find_in_workspace(self) -> None:
        sidebar = self.app.sidebar
        sidebar.display = True
        sidebar.tabbed_content.active = "search_pane"
        sidebar.workspace_search.focus_query_input()

    def action_focus_left_split(self) -> None:
        leaves = all_leaves(self._split_root)
        if leaves:
            self._set_active_leaf(leaves[0])

    def action_focus_right_split(self) -> None:
        if not self._split_visible:
            return
        leaves = all_leaves(self._split_root)
        if len(leaves) > 1:
            self._set_active_leaf(leaves[1])

    def action_focus_next_split(self) -> None:
        """Focus the next split (wrapping around)."""
        result = adjacent_leaf(self._split_root, self._active_leaf_id, delta=+1)
        if result:
            self._set_active_leaf(result)

    def action_focus_prev_split(self) -> None:
        """Focus the previous split (wrapping around)."""
        result = adjacent_leaf(self._split_root, self._active_leaf_id, delta=-1)
        if result:
            self._set_active_leaf(result)

    async def _move_pane_to_leaf(
        self, source_pane_id: str, dest_leaf: LeafNode
    ) -> str | None:
        """Move a pane to dest_leaf. Returns new_pane_id or None on failure."""
        source_leaf = self._leaf_of_pane(source_pane_id)
        if source_leaf is None:
            return None

        tc_source = self.query_one(f"#{source_leaf.leaf_id}", TabbedContent)
        pane = tc_source.get_pane(source_pane_id)

        # Handle markdown preview panes separately
        preview_results = pane.query(MarkdownPreviewPane)
        if preview_results:
            return await self._move_preview_pane_to_leaf(
                source_pane_id, preview_results.first(), dest_leaf
            )

        editor = pane.query_one(CodeEditor)
        path = editor.path
        text = editor.text
        has_unsaved = text != editor.initial_text

        # Check for duplicate file in destination
        if path is not None and path in dest_leaf.opened_files:
            existing_pane_id = dest_leaf.opened_files[path]
            await self.action_close_code_editor(source_pane_id, auto_close_split=False)
            await self._auto_close_split_if_empty()
            tc_dest = self.query_one(f"#{dest_leaf.leaf_id}", TabbedContent)
            tc_dest.active = existing_pane_id
            self._active_leaf_id = dest_leaf.leaf_id
            return existing_pane_id

        # Open in destination leaf first (before closing source, to avoid
        # _auto_close_split_if_empty collapsing while source leaf is empty)
        self._active_leaf_id = dest_leaf.leaf_id
        new_pane_id = await self.open_code_editor_pane(path)

        # Restore unsaved content
        if has_unsaved:
            tc_dest = self.query_one(f"#{dest_leaf.leaf_id}", TabbedContent)
            new_editor = tc_dest.get_pane(new_pane_id).query_one(CodeEditor)
            new_editor.replace_editor_text(text)

        # Close the source pane (defer auto-close to preserve tree structure)
        await self.action_close_code_editor(source_pane_id, auto_close_split=False)
        await self._auto_close_split_if_empty()
        return new_pane_id

    async def _move_preview_pane_to_leaf(
        self,
        source_pane_id: str,
        source_preview: MarkdownPreviewPane,
        dest_leaf: LeafNode,
    ) -> str | None:
        """Move a markdown preview pane to dest_leaf."""
        path = source_preview.source_path
        if path is not None:
            self._cancel_preview_timer(path)

        # Create new preview in destination
        self._active_leaf_id = dest_leaf.leaf_id
        new_pane_id = f"md-preview-{uuid4().hex}"
        new_preview = MarkdownPreviewPane(source_path=path)
        new_tab_pane = TabPane(
            f"Preview: {path.name}" if path else "Preview", new_preview, id=new_pane_id
        )
        await self.open_new_pane(new_pane_id, new_tab_pane)

        # Update tracking
        if path is not None:
            self._preview_pane_ids[path] = new_pane_id

        # Update preview content from source editor (if available)
        if path is not None:
            for leaf in all_leaves(self._split_root):
                if path in leaf.opened_files:
                    editor_pane_id = leaf.opened_files[path]
                    tc = self.query_one(f"#{leaf.leaf_id}", TabbedContent)
                    editor = tc.get_pane(editor_pane_id).query_one(CodeEditor)
                    await new_preview.update_for(editor.text, path)
                    break

        # Close source pane
        await self.close_pane(source_pane_id)
        await self._auto_close_split_if_empty()
        return new_pane_id

    async def _move_pane_to_split(
        self, source_pane_id: str, dest_split: str
    ) -> str | None:
        """Backward compat: Move a pane to 'left'/'right' split."""
        leaves = all_leaves(self._split_root)

        if dest_split == "right":
            if len(leaves) < 2:
                # Need to create right split first
                await self._ensure_split_exists()
                leaves = all_leaves(self._split_root)
            dest_leaf = leaves[1] if len(leaves) > 1 else leaves[0]
        else:
            dest_leaf = leaves[0]

        return await self._move_pane_to_leaf(source_pane_id, dest_leaf)

    async def _ensure_split_exists(self) -> None:
        """Ensure at least 2 splits exist."""
        if isinstance(self._split_root, LeafNode):
            new_root, new_leaf = split_leaf(
                self._split_root, self._active_leaf_id, "horizontal"
            )
            self._split_root = new_root
            await self._mount_new_split(new_leaf, "horizontal")

    async def action_move_tab_to_other_split(self) -> None:
        editor = self.get_active_code_editor()
        if editor is None:
            return

        leaves = all_leaves(self._split_root)
        current_leaf = self._active_leaf

        if len(leaves) < 2:
            # Only one leaf: create split and move to it
            dest_split = "right"
        else:
            # Find the "other" leaf
            idx = next((i for i, lf in enumerate(leaves) if lf is current_leaf), 0)
            dest_split = "left" if idx > 0 else "right"

        new_pane_id = await self._move_pane_to_split(editor.pane_id, dest_split)
        if new_pane_id is None:
            return

        dest_leaves = all_leaves(self._split_root)
        dest_leaf = dest_leaves[0] if dest_split == "left" else dest_leaves[-1]
        tc = self.query_one(f"#{dest_leaf.leaf_id}", TabbedContent)
        tc.active = new_pane_id
        self._set_active_leaf(dest_leaf)

    # ── Preview debounce helpers ────────────────────────────────────────────

    def _cancel_preview_timer(self, path: Path) -> None:
        """Cancel and remove a pending preview-update timer for *path*."""
        timer = self._preview_update_timers.pop(path, None)
        if timer is not None:
            timer.stop()
            log.debug("preview debounce: cancelled timer for %s", path)

    # ── Footer helpers ───────────────────────────────────────────────────────

    def _sync_footer_to_active_editor(self) -> None:
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

    # ── Event handlers ───────────────────────────────────────────────────────

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        widget = event.widget
        for ancestor in widget.ancestors_with_self:
            if isinstance(ancestor, DraggableTabbedContent) and ancestor.id:
                leaf = find_leaf(self._split_root, ancestor.id)
                if leaf is not None:
                    self._active_leaf_id = leaf.leaf_id
                break

    @on(TabbedContent.TabActivated)
    async def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        # Update active leaf based on which TabbedContent fired
        if isinstance(event.control, DraggableTabbedContent) and event.control.id:
            leaf = find_leaf(self._split_root, event.control.id)
            if leaf is not None:
                self._active_leaf_id = leaf.leaf_id
        self._sync_footer_to_active_editor()
        editor = self.get_active_code_editor()
        if editor is not None and editor.path is not None:
            self.post_message(self.ActiveFileChanged(editor.path))

    @on(DraggableTabbedContent.TabMovedToOtherSplit)
    async def on_tab_moved_to_other_split(
        self, event: DraggableTabbedContent.TabMovedToOtherSplit
    ) -> None:
        source_leaf = self._leaf_of_pane(event.source_pane_id)
        if source_leaf is None:
            return

        # Find destination leaf (the "other" one)
        leaves = all_leaves(self._split_root)
        source_idx = next((i for i, lf in enumerate(leaves) if lf is source_leaf), 0)
        dest_split = "left" if source_idx > 0 else "right"

        new_pane_id = await self._move_pane_to_split(event.source_pane_id, dest_split)
        if new_pane_id is None:
            return

        # Reorder the new pane relative to the drop target (skip when edge-drop)
        if event.target_pane_id is not None:
            dest_leaves = all_leaves(self._split_root)
            dest_leaf = dest_leaves[0] if dest_split == "left" else dest_leaves[-1]
            dest_tc = self.query_one(f"#{dest_leaf.leaf_id}", DraggableTabbedContent)
            dest_tc.reorder_tab(new_pane_id, event.target_pane_id, before=event.before)

        dest_leaves = all_leaves(self._split_root)
        dest_leaf = dest_leaves[0] if dest_split == "left" else dest_leaves[-1]
        tc = self.query_one(f"#{dest_leaf.leaf_id}", TabbedContent)
        tc.active = new_pane_id
        self._set_active_leaf(dest_leaf)
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
    def on_code_editor_text_changed(self, event: CodeEditor.TextChanged) -> None:
        editor = event.code_editor
        path = editor.path
        if path is None or path not in self._preview_pane_ids:
            return
        pane_id = self._preview_pane_ids[path]
        if not self.is_opened_pane(pane_id):
            return

        self._cancel_preview_timer(path)

        async def _do_update() -> None:
            self._preview_update_timers.pop(path, None)
            try:
                if not self.is_opened_pane(pane_id):
                    return
                tc = self._tc_for_pane(pane_id)
                if tc is None:
                    return
                preview = tc.get_pane(pane_id).query_one(MarkdownPreviewPane)
                await preview.update_for(editor.text, path)
                log.debug("preview debounce: updated preview for %s", path)
            except Exception:
                log.error("preview debounce: update failed for %s", path, exc_info=True)

        self._preview_update_timers[path] = self.set_timer(
            PREVIEW_DEBOUNCE_DELAY, _do_update, name=f"preview-update-{path.name}"
        )

    def action_toggle_split_vertical(self) -> None:
        """Toggle between horizontal and vertical split orientation."""
        # Find the top-level SplitContainer if any
        containers = list(self.query(SplitContainer))
        if containers:
            container = containers[0]
            container.toggle_class("split-vertical")
            if "split-vertical" in container.classes:
                container._direction = "vertical"
            else:
                container._direction = "horizontal"

    async def action_open_markdown_preview_tab(self) -> None:
        """Open a markdown preview tab for the active editor's file."""
        editor = self.get_active_code_editor()
        if editor is None or editor.path is None:
            return
        path = editor.path
        if path.suffix.lower() not in MARKDOWN_EXTENSIONS:
            return

        # If preview already open, focus it
        if path in self._preview_pane_ids:
            pane_id = self._preview_pane_ids[path]
            if self.is_opened_pane(pane_id):
                self.focus_pane(pane_id)
                return

        pane_id = f"md-preview-{uuid4().hex}"
        preview = MarkdownPreviewPane(source_path=path)
        pane = TabPane(f"Preview: {path.name}", preview, id=pane_id)
        await self.open_new_pane(pane_id, pane)
        self.focus_pane(pane_id)
        await preview.update_for(editor.text, path)
        self._preview_pane_ids[path] = pane_id

    @on(CodeEditor.TitleChanged)
    def on_code_editor_title_changed(self, event: CodeEditor.TitleChanged):
        if self.is_opened_pane(event.control.pane_id):
            tc = self._tc_for_pane(event.control.pane_id)
            if tc is not None:
                tc.get_tab(event.control.pane_id).label = event.control.title

    @on(CodeEditor.SavedAs)
    def on_code_editor_saved_as(self, event: CodeEditor.SavedAs):
        if event.control.path is None:
            raise ValueError("CodeEditor.SavedAs event must have a path")
        leaf = self._leaf_of_pane(event.control.pane_id)
        if leaf is not None:
            leaf.opened_files[event.control.path] = event.control.pane_id

    @on(CodeEditor.Closed)
    async def on_code_editor_closed(self, event: CodeEditor.Closed):
        path = event.control.path
        # Close the linked preview pane if one exists
        if path is not None and path in self._preview_pane_ids:
            self._cancel_preview_timer(path)
            preview_pane_id = self._preview_pane_ids.pop(path)
            if self.is_opened_pane(preview_pane_id):
                await self.close_pane(preview_pane_id)
                await self._auto_close_split_if_empty()
        await self.action_close_code_editor(event.control.pane_id)

    @on(CodeEditor.Deleted)
    async def on_code_editor_deleted(self, event: CodeEditor.Deleted):
        await self.action_close_code_editor(event.control.pane_id)
