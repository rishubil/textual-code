"""MultiCursorTextArea — TextArea subclass with multiple simultaneous cursors."""

from collections import defaultdict

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widgets import TextArea


def _is_editing_key(event: events.Key) -> bool:
    """Return True if the key is a simple single-character edit (no newline)."""
    if event.character is not None and event.character.isprintable():
        return True
    return event.key in ("backspace", "delete")


def _is_movement_key(event: events.Key) -> bool:
    """Return True if the key moves the cursor without editing."""
    return event.key in (
        "up",
        "down",
        "left",
        "right",
        "home",
        "end",
        "pageup",
        "pagedown",
        "ctrl+left",
        "ctrl+right",
        "ctrl+home",
        "ctrl+end",
        "shift+up",
        "shift+down",
        "shift+left",
        "shift+right",
        "shift+home",
        "shift+end",
    )


class MultiCursorTextArea(TextArea):
    """TextArea with multi-cursor support.

    Extra cursors are stored in ``_extra_cursors`` as a plain list so that
    Textual's reactive system does not interfere (list mutation would not
    trigger a watch).  The widget posts a ``CursorsChanged`` message whenever
    the extra-cursor set changes.
    """

    BINDINGS = [
        Binding("ctrl+shift+z", "redo", "Redo", show=False),
        Binding("tab", "indent_line", "Indent", show=False),
        Binding("shift+tab", "dedent_line", "Dedent", show=False),
    ]

    # ── inner message ─────────────────────────────────────────────────────────

    class CursorsChanged(Message):
        """Posted when the extra-cursor list changes (added or cleared)."""

        def __init__(self, text_area: "MultiCursorTextArea") -> None:
            super().__init__()
            self.text_area = text_area

        @property
        def control(self) -> "MultiCursorTextArea":
            return self.text_area

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._extra_cursors: list[tuple[int, int]] = []

    # ── public API ────────────────────────────────────────────────────────────

    @property
    def extra_cursors(self) -> list[tuple[int, int]]:
        """A copy of the extra-cursor list (read-only view)."""
        return list(self._extra_cursors)

    def add_cursor(self, location: tuple[int, int]) -> None:
        """Add an extra cursor at *location*.

        No-op if *location* equals the primary cursor position or is already
        present in the extra-cursor list.
        """
        if location != self.cursor_location and location not in self._extra_cursors:
            self._extra_cursors = self._extra_cursors + [location]
            self._line_cache.clear()
            self.refresh()
            self.post_message(self.CursorsChanged(self))

    def clear_extra_cursors(self) -> None:
        """Remove all extra cursors."""
        if self._extra_cursors:
            self._extra_cursors = []
            self._line_cache.clear()
            self.refresh()
            self.post_message(self.CursorsChanged(self))

    # ── indent / dedent ───────────────────────────────────────────────────────

    def action_indent_line(self) -> None:
        """VS Code style: add indent at start of selected lines, or at cursor."""
        from textual.widgets.text_area import Selection

        if self._extra_cursors:
            return  # on_key else branch will clear extra cursors

        indent = " " * self.indent_width
        sel = self.selection
        start_row, start_col = sel.start
        end_row, end_col = sel.end

        if end_row > start_row:
            # Multi-line selection: indent each selected line
            actual_end_row = end_row - 1 if end_col == 0 else end_row
            lines = self.text.split("\n")
            for row in range(start_row, actual_end_row + 1):
                if row < len(lines):
                    lines[row] = indent + lines[row]
            self.replace("\n".join(lines), self.document.start, self.document.end)
            new_start = (start_row, start_col + self.indent_width)
            new_end = (end_row, end_col + self.indent_width if end_col > 0 else 0)
            self.selection = Selection(start=new_start, end=new_end)
        else:
            # Single line or no selection: insert spaces at cursor
            self.replace(indent, self.cursor_location, self.cursor_location)

    def action_dedent_line(self) -> None:
        """Remove up to tab_width leading spaces from each selected line."""
        from textual.widgets.text_area import Selection

        if self._extra_cursors:
            return  # on_key else branch will clear extra cursors

        n = self.indent_width
        sel = self.selection
        start_row, start_col = sel.start
        end_row, end_col = sel.end
        actual_end_row = (
            end_row - 1 if (end_row > start_row and end_col == 0) else end_row
        )

        lines = self.text.split("\n")
        removed: dict[int, int] = {}
        for row in range(start_row, actual_end_row + 1):
            if row < len(lines):
                spaces = len(lines[row]) - len(lines[row].lstrip(" "))
                remove = min(spaces, n)
                lines[row] = lines[row][remove:]
                removed[row] = remove

        if not any(removed.values()):
            return  # nothing to dedent

        self.replace("\n".join(lines), self.document.start, self.document.end)

        def adjust(row: int, col: int) -> int:
            return max(0, col - removed.get(row, 0))

        new_start = (start_row, adjust(start_row, start_col))
        new_end = (end_row, adjust(end_row, end_col) if end_col > 0 else 0)
        self.selection = Selection(start=new_start, end=new_end)

    # ── rendering ─────────────────────────────────────────────────────────────

    def get_line(self, line_index: int) -> Text:
        """Render extra cursors by stylising their column positions."""
        line = super().get_line(line_index)
        if self._extra_cursors and self._theme:
            cursor_style = self._theme.cursor_style
            for row, col in self._extra_cursors:
                if row == line_index and 0 <= col <= len(line.plain):
                    line.stylize(cursor_style, col, col + 1)
        return line

    # ── copy / cut overrides ──────────────────────────────────────────────────

    def action_copy(self) -> None:
        """Copy selection; copy current line if nothing selected (VS Code)."""
        selected = self.selected_text
        if selected:
            self.app.copy_to_clipboard(selected)
        else:
            row, _ = self.cursor_location
            lines = self.text.split("\n")
            line = lines[row] if row < len(lines) else ""
            self.app.copy_to_clipboard(line + "\n")

    # ── key handling ──────────────────────────────────────────────────────────

    def on_key(self, event: events.Key) -> None:
        """Intercept key events when extra cursors are active."""
        if not self._extra_cursors:
            return  # let TextArea handle everything normally

        if event.key == "escape":
            # Clear extra cursors; consume the key so TextArea does not act on it.
            event.prevent_default()
            event.stop()
            self.clear_extra_cursors()
            return

        if _is_movement_key(event):
            # Clear extra cursors; let TextArea still perform the movement.
            self.clear_extra_cursors()
            return

        if _is_editing_key(event) or event.key == "enter":
            # Handle ourselves; suppress TextArea's default behaviour.
            event.prevent_default()
            event.stop()
            self._apply_to_all_cursors(event)
        else:
            # Complex keys (tab, …): clear extra cursors and delegate.
            self.clear_extra_cursors()

    # ── multi-cursor editing ──────────────────────────────────────────────────

    def _apply_to_all_cursors(self, event: events.Key) -> None:
        """Apply a simple edit to the primary cursor and all extra cursors.

        Edits are applied right-to-left within each row so that earlier
        insertions / deletions do not shift the indices of later ones.

        For cases that would cause row merges / splits (e.g. backspace at
        column 0, delete at end-of-line), extra cursors are cleared and the
        key is delegated to the base TextArea.
        """
        lines = self.text.split("\n")
        primary = self.cursor_location
        extra = list(self._extra_cursors)
        all_cursors: list[tuple[int, int]] = [primary] + extra

        key = event.key
        char = event.character

        if key == "enter":
            self._do_enter(all_cursors, primary, extra)

        elif char is not None and char.isprintable():
            self._do_insert(lines, all_cursors, primary, extra, char)

        elif key == "backspace":
            if all(c == 0 for _, c in all_cursors):
                self._do_backspace_line_merge(all_cursors, primary, extra)
            elif any(c == 0 for _, c in all_cursors):
                # Mixed: some at col 0, some not — clear and delegate.
                self.clear_extra_cursors()
            else:
                self._do_backspace(lines, all_cursors, primary, extra)

        elif key == "delete":
            all_at_eol = all(
                r >= len(lines) or c >= len(lines[r]) for r, c in all_cursors
            )
            any_at_eol = any(
                r >= len(lines) or c >= len(lines[r]) for r, c in all_cursors
            )
            if all_at_eol:
                self._do_delete_line_merge(all_cursors, primary, extra)
            elif any_at_eol:
                # Mixed: some at EOL, some not — clear and delegate.
                self.clear_extra_cursors()
            else:
                self._do_delete(lines, all_cursors, primary, extra)

    # ── per-operation helpers ─────────────────────────────────────────────────

    def _do_enter(
        self,
        all_cursors: list[tuple[int, int]],
        primary: tuple[int, int],
        extra: list[tuple[int, int]],
    ) -> None:
        """Insert a newline at every cursor position.

        Cursors are processed top-to-bottom, left-to-right.  A running
        ``row_offset`` tracks how many rows have been added so far so that
        indices into the (now-mutated) document stay correct.  Within a single
        original row, ``accumulated_col_shift`` tracks how much the column of
        each predecessor has consumed (text to the left of us was moved to the
        new line above, so our effective column shrinks by that amount).
        """
        sorted_cursors = sorted(all_cursors)
        new_positions: dict[tuple[int, int], tuple[int, int]] = {}
        last_orig_row = -1
        accumulated_col_shift = 0

        for row_offset, (orig_row, orig_col) in enumerate(sorted_cursors):
            if orig_row != last_orig_row:
                last_orig_row = orig_row
                accumulated_col_shift = 0

            actual_row = orig_row + row_offset
            actual_col = orig_col - accumulated_col_shift

            self.replace("\n", (actual_row, actual_col), (actual_row, actual_col))

            accumulated_col_shift = orig_col
            new_positions[(orig_row, orig_col)] = (actual_row + 1, 0)

        self.cursor_location = new_positions[primary]
        self._extra_cursors = [new_positions[ec] for ec in extra]
        self.refresh()

    def _do_backspace_line_merge(
        self,
        all_cursors: list[tuple[int, int]],
        primary: tuple[int, int],
        extra: list[tuple[int, int]],
    ) -> None:
        """Merge each cursor's line with the line above (backspace at col 0).

        All cursors must be at column 0.  Cursors on row 0 are left in place.
        Each merge removes one row, so ``actual_row = row - i`` where ``i`` is
        the number of merges already performed above this cursor.
        """
        sorted_cursors = sorted(all_cursors)
        new_positions: dict[tuple[int, int], tuple[int, int]] = {}

        for i, (row, col) in enumerate(sorted_cursors):
            actual_row = row - i
            if actual_row == 0:
                new_positions[(row, col)] = (0, 0)
                continue

            current_lines = self.text.split("\n")
            prev_len = len(current_lines[actual_row - 1])
            self.replace("", (actual_row - 1, prev_len), (actual_row, 0))
            new_positions[(row, col)] = (actual_row - 1, prev_len)

        self.cursor_location = new_positions[primary]
        self._extra_cursors = [new_positions[ec] for ec in extra]
        self.refresh()

    def _do_delete_line_merge(
        self,
        all_cursors: list[tuple[int, int]],
        primary: tuple[int, int],
        extra: list[tuple[int, int]],
    ) -> None:
        """Merge each cursor's line with the line below (delete at EOL).

        All cursors must be at end-of-line.  Cursors on the last line are
        left in place (no next line to merge).  Each merge removes one row,
        so ``actual_row = row - i``.
        """
        sorted_cursors = sorted(all_cursors)
        new_positions: dict[tuple[int, int], tuple[int, int]] = {}

        for i, (row, col) in enumerate(sorted_cursors):
            actual_row = row - i
            current_lines = self.text.split("\n")
            eol_col = (
                len(current_lines[actual_row]) if actual_row < len(current_lines) else 0
            )

            if actual_row >= len(current_lines) - 1:
                new_positions[(row, col)] = (actual_row, eol_col)
                continue

            self.replace("", (actual_row, eol_col), (actual_row + 1, 0))
            new_positions[(row, col)] = (actual_row, eol_col)

        self.cursor_location = new_positions[primary]
        self._extra_cursors = [new_positions[ec] for ec in extra]
        self.refresh()

    def _do_insert(
        self,
        lines: list[str],
        all_cursors: list[tuple[int, int]],
        primary: tuple[int, int],
        extra: list[tuple[int, int]],
        char: str,
    ) -> None:
        row_cols: dict[int, list[int]] = defaultdict(list)
        for row, col in all_cursors:
            row_cols[row].append(col)

        for row, cols in row_cols.items():
            if 0 <= row < len(lines):
                for col in sorted(cols, reverse=True):
                    line = lines[row]
                    lines[row] = line[:col] + char + line[col:]
            else:
                self.clear_extra_cursors()
                return

        new_text = "\n".join(lines)
        self.replace(new_text, self.document.start, self.document.end)

        new_pos = self._new_positions(all_cursors, "insert")
        self.cursor_location = new_pos[primary]
        self._extra_cursors = [new_pos[ec] for ec in extra]
        self.refresh()

    def _do_backspace(
        self,
        lines: list[str],
        all_cursors: list[tuple[int, int]],
        primary: tuple[int, int],
        extra: list[tuple[int, int]],
    ) -> None:
        row_cols: dict[int, list[int]] = defaultdict(list)
        for row, col in all_cursors:
            row_cols[row].append(col)

        for row, cols in row_cols.items():
            if 0 <= row < len(lines):
                for col in sorted(cols, reverse=True):
                    line = lines[row]
                    lines[row] = line[: col - 1] + line[col:]

        new_text = "\n".join(lines)
        self.replace(new_text, self.document.start, self.document.end)

        new_pos = self._new_positions(all_cursors, "backspace")
        self.cursor_location = new_pos[primary]
        self._extra_cursors = [new_pos[ec] for ec in extra]
        self.refresh()

    def _do_delete(
        self,
        lines: list[str],
        all_cursors: list[tuple[int, int]],
        primary: tuple[int, int],
        extra: list[tuple[int, int]],
    ) -> None:
        row_cols: dict[int, list[int]] = defaultdict(list)
        for row, col in all_cursors:
            row_cols[row].append(col)

        for row, cols in row_cols.items():
            if 0 <= row < len(lines):
                for col in sorted(cols, reverse=True):
                    line = lines[row]
                    lines[row] = line[:col] + line[col + 1 :]

        new_text = "\n".join(lines)
        self.replace(new_text, self.document.start, self.document.end)

        new_pos = self._new_positions(all_cursors, "delete")
        self.cursor_location = new_pos[primary]
        self._extra_cursors = [new_pos[ec] for ec in extra]
        self.refresh()

    # ── position maths ────────────────────────────────────────────────────────

    @staticmethod
    def _new_positions(
        all_cursors: list[tuple[int, int]],
        op: str,
    ) -> dict[tuple[int, int], tuple[int, int]]:
        """Compute the new (row, col) for every cursor after *op*.

        Each cursor's column shift depends on how many *other* cursors on the
        same row have a smaller column index (they edit to the left of it,
        shifting its position further).

        *op* is one of ``"insert"``, ``"backspace"``, or ``"delete"``.
        """
        result: dict[tuple[int, int], tuple[int, int]] = {}
        for row, col in all_cursors:
            num_smaller = sum(1 for r, c in all_cursors if r == row and c < col)
            if op == "insert":
                # +1 own insert; +num_smaller for inserts to the left
                new_col = col + 1 + num_smaller
            elif op == "backspace":
                # -1 own delete; -num_smaller for deletes to the left
                new_col = col - 1 - num_smaller
            elif op == "delete":
                # cursor stays but shifts left for each delete to the left
                new_col = col - num_smaller
            else:
                new_col = col
            result[(row, col)] = (row, new_col)
        return result
