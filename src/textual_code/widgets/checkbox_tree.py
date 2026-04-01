"""CheckboxTree widget for workspace search results with per-match selection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from typing import ClassVar

from rich.markup import escape as markup_escape
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, VerticalScroll
from textual.content import Content
from textual.css.query import NoMatches
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.style import Style
from textual.widgets import Checkbox, Static
from textual.widgets._toggle_button import ToggleButton

from textual_code.search import WorkspaceSearchResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TriStateCheckbox
# ---------------------------------------------------------------------------


class TriStateCheckbox(ToggleButton):
    """A checkbox with three states: True (all), None (partial), False (none).

    Rendering: ``▐X▌`` (True) / ``▐-▌`` (None) / ``▐ ▌`` (False).
    Toggle cycle: False→True, None→True, True→False.
    """

    BUTTON_INNER_TRUE = "X"
    BUTTON_INNER_PARTIAL = "-"
    BUTTON_INNER_FALSE = " "

    DEFAULT_CSS = """
    TriStateCheckbox {
        width: auto;
        height: 1;
        border: none;
        padding: 0;
        min-width: 3;
        background: transparent;

        &.-partial > .toggle--button {
            color: $text-warning;
        }
    }
    """

    value: reactive[bool | None] = reactive(False, init=False)
    """Tri-state value: True (all selected), None (partial), False (none)."""

    def __init__(
        self,
        value: bool | None = False,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(
            label="",
            value=False,  # ToggleButton expects bool; we override immediately
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        with self.prevent(self.Changed):
            self.value = value

    @property
    def _button(self) -> Content:
        button_style = self.get_visual_style("toggle--button")
        side_style = Style(
            foreground=button_style.background,
            background=self.background_colors[1],
        )
        if self.value is True:
            inner = self.BUTTON_INNER_TRUE
        elif self.value is None:
            inner = self.BUTTON_INNER_PARTIAL
        else:
            inner = self.BUTTON_INNER_FALSE
        return Content.assemble(
            (self.BUTTON_LEFT, side_style),
            (inner, button_style),
            (self.BUTTON_RIGHT, side_style),
        )

    def render(self) -> Content:
        return self._button

    def toggle(self) -> TriStateCheckbox:
        """Toggle: False→True, None→True, True→False."""
        if self.value is True:
            self.value = False
        else:
            self.value = True
        return self

    def watch_value(self) -> None:
        """Manage CSS classes and post Changed message."""
        self.set_class(self.value is True, "-on")
        self.set_class(self.value is None, "-partial")
        self.post_message(self.Changed(self, self.value))

    class Changed(ToggleButton.Changed):
        """Posted when the tri-state checkbox value changes."""

        def __init__(self, toggle_button: TriStateCheckbox, value: bool | None) -> None:
            Message.__init__(self)
            self._toggle_button = toggle_button
            self.value: bool | None = value

        @property
        def tri_state_checkbox(self) -> TriStateCheckbox:
            assert isinstance(self._toggle_button, TriStateCheckbox)
            return self._toggle_button

        @property
        def control(self) -> TriStateCheckbox:
            return self.tri_state_checkbox


# ---------------------------------------------------------------------------
# Internal row widgets
# ---------------------------------------------------------------------------


class _InlineCheckbox(Checkbox, can_focus=False):
    """Checkbox that cannot receive independent focus (managed by parent row)."""

    DEFAULT_CSS = """
    _InlineCheckbox {
        width: auto;
        height: 1;
        border: none;
        padding: 0;
        min-width: 3;
        background: transparent;
    }
    """

    def render(self) -> Content:
        """Render button only (no label) to match TriStateCheckbox appearance."""
        return self._button


class _InlineTriState(TriStateCheckbox, can_focus=False):
    """TriStateCheckbox that cannot receive independent focus."""


class _ExpandToggle(Static):
    """Expand/collapse indicator for file rows."""

    DEFAULT_CSS = """
    _ExpandToggle {
        width: 2;
        height: 1;
    }
    """

    expanded: reactive[bool] = reactive(True)

    def render(self) -> str:
        return "▼ " if self.expanded else "▶ "

    def on_click(self, _event: Click) -> None:
        self.expanded = not self.expanded
        self.post_message(_ToggleExpand(self))


class _NodeLabel(Static):
    """Clickable label that posts a message when clicked."""

    DEFAULT_CSS = """
    _NodeLabel {
        width: 1fr;
        height: 1;
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }
    """

    def on_click(self, _event: Click) -> None:
        self.post_message(_LabelClicked(self))


# Internal messages (not exposed to users)
@dataclass
class _ToggleExpand(Message):
    toggle: _ExpandToggle


@dataclass
class _LabelClicked(Message):
    label: _NodeLabel


class _FileRow(Horizontal, can_focus=True):
    """A file header row in the CheckboxTree."""

    DEFAULT_CSS = """
    _FileRow {
        height: 1;
        width: 1fr;
        &:focus {
            background: $accent-darken-2;
        }
        &.-cursor {
            background: $surface-lighten-1;
        }
        &:hover {
            background: $surface-lighten-1;
        }
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("space", "toggle_check", "Toggle", show=False),
        Binding("enter", "select_node", "Select", show=False),
    ]

    def __init__(
        self,
        file_path: Path,
        first_line: int,
        label_text: str,
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._file_path = file_path
        self._first_line = first_line
        self._label_text = label_text
        self._match_rows: list[_MatchRow] = []

    @property
    def data(self) -> tuple[Path, int]:
        return (self._file_path, self._first_line)

    @property
    def label_text(self) -> str:
        return self._label_text

    def compose(self):
        yield _ExpandToggle()
        yield _InlineTriState(value=True)
        yield _NodeLabel(markup_escape(self._label_text))

    def action_toggle_check(self) -> None:
        cb = self.query_one(_InlineTriState)
        cb.toggle()

    def action_select_node(self) -> None:
        self.post_message(_LabelClicked(self.query_one(_NodeLabel)))


class _MatchRow(Horizontal, can_focus=True):
    """A match line row in the CheckboxTree."""

    DEFAULT_CSS = """
    _MatchRow {
        height: 1;
        width: 1fr;
        &:focus {
            background: $accent-darken-2;
        }
        &.-cursor {
            background: $surface-lighten-1;
        }
        &:hover {
            background: $surface-lighten-1;
        }
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("space", "toggle_check", "Toggle", show=False),
        Binding("enter", "select_node", "Select", show=False),
    ]

    def __init__(
        self,
        file_path: Path,
        line_number: int,
        label_text: str,
        result: WorkspaceSearchResult,
        parent_file_row: _FileRow,
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._file_path = file_path
        self._line_number = line_number
        self._parent_file_row = parent_file_row
        self._label_text = label_text
        self._result = result

    @property
    def data(self) -> tuple[Path, int]:
        return (self._file_path, self._line_number)

    @property
    def label_text(self) -> str:
        return self._label_text

    def compose(self):
        yield Static("   ", classes="indent-spacer")
        yield _InlineCheckbox(value=True)
        yield _NodeLabel(markup_escape(self._label_text))

    def action_toggle_check(self) -> None:
        cb = self.query_one(_InlineCheckbox)
        cb.toggle()

    def action_select_node(self) -> None:
        self.post_message(_LabelClicked(self.query_one(_NodeLabel)))


# ---------------------------------------------------------------------------
# CheckboxTree
# ---------------------------------------------------------------------------


class CheckboxTree(VerticalScroll):
    """Scrollable tree of workspace search results with per-match checkboxes.

    Replaces Textual's ``Tree`` widget for ``WorkspaceSearchPane`` to enable
    selective Replace All.
    """

    DEFAULT_CSS = """
    CheckboxTree {
        height: 1fr;
        scrollbar-size-vertical: 1;
    }
    CheckboxTree Static.indent-spacer {
        width: 5;
        height: 1;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "focus_previous_row", "Previous", show=False),
        Binding("down", "focus_next_row", "Next", show=False),
        Binding("home", "focus_first_row", "First", show=False),
        Binding("end", "focus_last_row", "Last", show=False),
    ]

    @dataclass
    class NodeSelected(Message):
        """Posted when a result label is clicked or Enter is pressed."""

        file_path: Path
        line_number: int

    class SelectionChanged(Message):
        """Posted when any checkbox state changes."""

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._file_row_list: list[_FileRow] = []
        self._syncing = False
        self._last_focused_row: _FileRow | _MatchRow | None = None

    # ── Public API ────────────────────────────────────────────────────────

    def populate(
        self,
        results: list[WorkspaceSearchResult],
        workspace_path: Path,
    ) -> None:
        """Build the checkbox tree from search results."""
        self._file_row_list.clear()
        self.remove_children()

        if not results:
            return

        widgets: list[_FileRow | _MatchRow] = []
        for file_path, file_results in groupby(results, key=lambda r: r.file_path):
            matches = list(file_results)
            count = len(matches)
            try:
                relative = file_path.relative_to(workspace_path)
            except ValueError:
                relative = file_path
            suffix = "match" if count == 1 else "matches"
            first_line = matches[0].line_number
            label = f"{relative} ({count} {suffix})"

            file_row = _FileRow(
                file_path=file_path,
                first_line=first_line,
                label_text=label,
            )
            widgets.append(file_row)
            self._file_row_list.append(file_row)

            for match in matches:
                match_label = f"{match.line_number}: {match.line_text.strip()}"
                match_row = _MatchRow(
                    file_path=file_path,
                    line_number=match.line_number,
                    label_text=match_label,
                    result=match,
                    parent_file_row=file_row,
                )
                file_row._match_rows.append(match_row)
                widgets.append(match_row)

        self.mount_all(widgets)

    def clear(self) -> None:
        """Remove all rows and reset state."""
        self._file_row_list.clear()
        self.remove_children()

    def file_rows(self) -> list[_FileRow]:
        """Return all file rows."""
        return list(self._file_row_list)

    def match_rows_for(self, file_row: _FileRow) -> list[_MatchRow]:
        """Return match rows belonging to a file row."""
        return list(file_row._match_rows)

    def remove_file_row(self, file_row: _FileRow) -> None:
        """Remove a file row and all its match rows from the tree."""
        if file_row not in self._file_row_list:
            return
        for mr in file_row._match_rows:
            mr.remove()
        file_row._match_rows.clear()
        self._file_row_list.remove(file_row)
        file_row.remove()

    def remove_match_row(self, match_row: _MatchRow) -> None:
        """Remove a single match row from the tree.

        If this was the last match in its file, the file row is also removed.
        """
        parent = match_row._parent_file_row
        if match_row in parent._match_rows:
            parent._match_rows.remove(match_row)
        match_row.remove()

        if not parent._match_rows:
            # No more matches — remove the file row too
            if parent in self._file_row_list:
                self._file_row_list.remove(parent)
            parent.remove()
        else:
            self._update_file_checkbox(parent)

    @property
    def selected_results(self) -> list[WorkspaceSearchResult]:
        """Return only the checked (selected) search results."""
        selected: list[WorkspaceSearchResult] = []
        for file_row in self._file_row_list:
            for match_row in file_row._match_rows:
                try:
                    cb = match_row.query_one(_InlineCheckbox)
                except NoMatches:
                    continue
                if cb.value:
                    selected.append(match_row._result)
        return selected

    @property
    def all_selected(self) -> bool:
        """True if every match checkbox is checked (or tree is empty)."""
        for file_row in self._file_row_list:
            for match_row in file_row._match_rows:
                try:
                    cb = match_row.query_one(_InlineCheckbox)
                except NoMatches:
                    continue
                if not cb.value:
                    return False
        return True

    # ── Navigation actions ────────────────────────────────────────────────

    def _visible_rows(self) -> list[_FileRow | _MatchRow]:
        rows: list[_FileRow | _MatchRow] = []
        for fr in self._file_row_list:
            rows.append(fr)
            if fr.query_one(_ExpandToggle).expanded:
                rows.extend(fr._match_rows)
        return rows

    def _focused_index(self, visible: list[_FileRow | _MatchRow]) -> int | None:
        """Return the index of the currently focused row, or None."""
        current = self.screen.focused
        for i, row in enumerate(visible):
            if row is current:
                return i
        return None

    def action_focus_next_row(self) -> None:
        visible = self._visible_rows()
        if not visible:
            return
        idx = self._focused_index(visible)
        next_idx = min(idx + 1, len(visible) - 1) if idx is not None else 0
        visible[next_idx].focus()
        visible[next_idx].scroll_visible()

    def action_focus_previous_row(self) -> None:
        visible = self._visible_rows()
        if not visible:
            return
        idx = self._focused_index(visible)
        prev_idx = max(idx - 1, 0) if idx is not None else len(visible) - 1
        visible[prev_idx].focus()
        visible[prev_idx].scroll_visible()

    def action_focus_first_row(self) -> None:
        visible = self._visible_rows()
        if visible:
            visible[0].focus()
            visible[0].scroll_visible()

    def action_focus_last_row(self) -> None:
        visible = self._visible_rows()
        if visible:
            visible[-1].focus()
            visible[-1].scroll_visible()

    # ── Focus memory ─────────────────────────────────────────────────────

    def on_descendant_focus(self, event: object) -> None:
        """Track which row was last focused and update cursor highlight."""
        focused = self.screen.focused
        if isinstance(focused, (_FileRow, _MatchRow)):
            if (
                self._last_focused_row is not None
                and self._last_focused_row is not focused
            ):
                self._last_focused_row.remove_class("-cursor")
            self._last_focused_row = focused
            focused.add_class("-cursor")

    def on_focus(self) -> None:
        """Restore focus to the last-focused row when the tree regains focus."""
        row = self._last_focused_row
        if row is not None and row.display and row.is_attached:
            row.focus()
            row.scroll_visible()
            return
        # Fallback: focus the first visible row
        visible = self._visible_rows()
        if visible:
            visible[0].focus()

    # ── Checkbox synchronization (central handler) ────────────────────────

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """When a match checkbox changes, update the parent file's tri-state."""
        if self._syncing:
            return
        event.stop()

        match_row = event.control.parent
        if not isinstance(match_row, _MatchRow):
            return

        self._update_file_checkbox(match_row._parent_file_row)

        self.post_message(self.SelectionChanged())

    def on_tri_state_checkbox_changed(self, event: TriStateCheckbox.Changed) -> None:
        """When a file checkbox changes, update all child match checkboxes."""
        if self._syncing:
            return
        event.stop()

        file_row = event.control.parent
        if not isinstance(file_row, _FileRow):
            return

        new_value = event.value is not False  # None→True, True→True, False→False
        self._syncing = True
        try:
            for mr in file_row._match_rows:
                cb = mr.query_one(_InlineCheckbox)
                if cb.value != new_value:
                    with cb.prevent(Checkbox.Changed):
                        cb.value = new_value
            # Ensure file checkbox shows True or False (not partial)
            tri = file_row.query_one(_InlineTriState)
            if tri.value is None:
                with tri.prevent(TriStateCheckbox.Changed):
                    tri.value = new_value
        finally:
            self._syncing = False

        self.post_message(self.SelectionChanged())

    def _update_file_checkbox(self, file_row: _FileRow) -> None:
        """Recompute the tri-state of a file row from its children."""
        values = []
        for mr in file_row._match_rows:
            try:
                values.append(mr.query_one(_InlineCheckbox).value)
            except NoMatches:
                continue

        if not values:
            new_val: bool | None = True
        elif all(values):
            new_val = True
        elif not any(values):
            new_val = False
        else:
            new_val = None

        tri = file_row.query_one(_InlineTriState)
        self._syncing = True
        try:
            with tri.prevent(TriStateCheckbox.Changed):
                tri.value = new_val
        finally:
            self._syncing = False

    # ── Label click → NodeSelected ────────────────────────────────────────

    def on__label_clicked(self, event: _LabelClicked) -> None:
        """Convert internal label click to public NodeSelected message."""
        event.stop()
        row = event.label.parent
        if isinstance(row, (_FileRow, _MatchRow)):
            file_path, line_number = row.data
            self.post_message(
                self.NodeSelected(file_path=file_path, line_number=line_number)
            )

    # ── Expand/collapse ───────────────────────────────────────────────────

    def on__toggle_expand(self, event: _ToggleExpand) -> None:
        """Show/hide match rows when a file row's expand toggle is clicked."""
        event.stop()
        file_row = event.toggle.parent
        if not isinstance(file_row, _FileRow):
            return
        expanded = event.toggle.expanded
        for mr in file_row._match_rows:
            mr.display = expanded
