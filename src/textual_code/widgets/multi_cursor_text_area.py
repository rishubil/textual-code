"""MultiCursorTextArea — TextArea subclass with multiple simultaneous cursors."""

from collections import defaultdict

from rich.text import Text
from textual import events
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
            self.refresh()
            self.post_message(self.CursorsChanged(self))

    def clear_extra_cursors(self) -> None:
        """Remove all extra cursors."""
        if self._extra_cursors:
            self._extra_cursors = []
            self.refresh()
            self.post_message(self.CursorsChanged(self))

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

        if _is_editing_key(event):
            # Handle ourselves; suppress TextArea's default behaviour.
            event.prevent_default()
            event.stop()
            self._apply_to_all_cursors(event)
        else:
            # Complex keys (enter, tab, …): clear extra cursors and delegate.
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

        if char is not None and char.isprintable():
            self._do_insert(lines, all_cursors, primary, extra, char)

        elif key == "backspace":
            # Abort if any cursor is at the start of a line (row-merge edge case).
            if any(c == 0 for _, c in all_cursors):
                self.clear_extra_cursors()
                return
            self._do_backspace(lines, all_cursors, primary, extra)

        elif key == "delete":
            # Abort if any cursor is at the end of its line (row-merge edge case).
            if any(r >= len(lines) or c >= len(lines[r]) for r, c in all_cursors):
                self.clear_extra_cursors()
                return
            self._do_delete(lines, all_cursors, primary, extra)

    # ── per-operation helpers ─────────────────────────────────────────────────

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
