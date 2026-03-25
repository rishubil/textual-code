"""MultiCursorTextArea — TextArea subclass with multiple simultaneous cursors."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar, Literal

from rich.cells import cell_len
from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual import events
from textual.message import Message
from textual.strip import Strip
from textual.widgets import TextArea

from textual_code.command_registry import bindings_for_context as _bindings_for_context

if TYPE_CHECKING:
    from textual_code.widgets.code_editor import LineChangeType

# ── Module-level helpers ───────────────────────────────────────────────────────

_WORD_PATTERN = re.compile(r"(?<=\W)(?=\w)|(?<=\w)(?=\W)")


def _build_offsets(lines: list[str]) -> list[int]:
    """Build prefix sum of line lengths (including newline separator)."""
    result = [0]
    for line in lines:
        result.append(result[-1] + len(line) + 1)
    return result


def _loc_to_offset(lines: list[str], row: int, col: int, offsets: list[int]) -> int:
    """Convert (row, col) to flat text offset using pre-built prefix sum."""
    return offsets[row] + col


def _offset_to_loc(
    offset: int, lines: list[str], offsets: list[int]
) -> tuple[int, int]:
    """Convert flat text offset to (row, col) using pre-built prefix sum."""
    for r in range(len(lines) - 1, -1, -1):
        if offsets[r] <= offset:
            return (r, offset - offsets[r])
    return (0, offset)


# ── Key classification helpers ─────────────────────────────────────────────────


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
        "shift+pageup",
        "shift+pagedown",
        "ctrl+shift+left",
        "ctrl+shift+right",
        "ctrl+shift+home",
        "ctrl+shift+end",
    )


# ── Case transform helpers ────────────────────────────────────────────────────
#
# Ported from VSCode's linesOperations.ts — SnakeCaseAction, CamelCaseAction,
# KebabCaseAction, PascalCaseAction.  Python's ``re`` module does not support
# Unicode property escapes (``\p{Lu}``), so we use character-level
# ``str.isupper()``/``str.islower()`` checks which are fully Unicode-aware.


def _insert_separator_at_case_boundaries(text: str, sep: str) -> str:
    """Insert *sep* at camelCase / acronym boundaries.

    Boundary rules (matching VSCode):
    1. lowercase → uppercase  (e.g. ``parse|HTML``)
    2. (uppercase-or-digit)(uppercase)(lowercase) — last char of an acronym run
       starts a new word  (e.g. ``CSS|Selectors``, ``M4A|To``)
    """
    result: list[str] = []
    n = len(text)
    for i, ch in enumerate(text):
        if i > 0:
            prev = text[i - 1]
            # Rule 1: lowercase → uppercase
            if prev.islower() and ch.isupper():  # noqa: SIM114
                result.append(sep)
            # Rule 2: (upper|digit)(upper)(lower) — insert before the (upper)
            elif (
                (prev.isupper() or prev.isdigit())
                and ch.isupper()
                and i + 1 < n
                and text[i + 1].islower()
            ):
                result.append(sep)
        result.append(ch)
    return "".join(result)


def _to_snake_case(text: str) -> str:
    """Convert *text* to snake_case (VSCode SnakeCaseAction port)."""
    return _insert_separator_at_case_boundaries(text, "_").lower()


def _to_kebab_case(text: str) -> str:
    """Convert *text* to kebab-case (VSCode KebabCaseAction port)."""
    # Step 1: replace underscores between non-whitespace with hyphens
    text = re.sub(r"(\S)_(\S)", r"\1-\2", text)
    # Step 2: insert hyphens at case boundaries
    text = _insert_separator_at_case_boundaries(text, "-")
    return text.lower()


def _to_camel_case(text: str) -> str:
    """Convert *text* to camelCase (VSCode CamelCaseAction port)."""
    # Multiline: split only on _ and - (preserve spaces/tabs/newlines).
    # Single line: also split on whitespace.
    if "\n" in text or "\r" in text:
        boundary = re.compile(r"[_-]+")
    else:
        boundary = re.compile(r"[_\s-]+")

    parts = boundary.split(text)
    if not parts:
        return text

    result_parts: list[str] = []
    for idx, part in enumerate(parts):
        if idx == 0:
            # First word: lowercase start if it begins with single uppercase
            # followed by non-uppercase (e.g. "From" → "from", but "XML" stays "XML")
            if part and part[0].isupper() and len(part) > 1 and not part[1].isupper():
                part = part[0].lower() + part[1:]
            result_parts.append(part)
        else:
            # Subsequent words: capitalize first char
            if part:
                part = part[0].upper() + part[1:]
            result_parts.append(part)

    return "".join(result_parts)


def _to_pascal_case(text: str) -> str:
    """Convert *text* to PascalCase (VSCode PascalCaseAction port)."""
    # Split on word boundaries, preserving dots as join points
    # VSCode: wordBoundary = /[_ \t-]/gm, wordBoundaryToMaintain = /(?<=\.)/gm
    parts_by_dot = re.split(r"(?<=\.)", text)
    words: list[str] = []
    for part in parts_by_dot:
        words.extend(re.split(r"[_ \t-]+", part))

    result_words: list[str] = []
    for word in words:
        if not word:
            continue
        normalized = word[0].upper() + word[1:]
        # If the word is ALL uppercase letters and length > 1, title-case it
        if len(normalized) > 1 and normalized.isalpha() and normalized.isupper():
            normalized = normalized[0] + normalized[1:].lower()
        result_words.append(normalized)

    return "".join(result_words)


class MultiCursorTextArea(TextArea):
    """TextArea with multi-cursor support.

    Extra cursors are stored in ``_extra_cursors`` as a plain list so that
    Textual's reactive system does not interfere (list mutation would not
    trigger a watch).  The widget posts a ``CursorsChanged`` message whenever
    the extra-cursor set changes.

    Each extra cursor has a parallel anchor in ``_extra_anchors``.  When
    anchor == cursor the cursor is collapsed (no selection); otherwise the
    selection spans [min(anchor,cursor), max(anchor,cursor)].
    """

    indent_type: str = "spaces"

    # Tracks clipboard text from a line-copy/cut (no selection).
    # Shared across all instances so line-paste works across tabs.
    _line_copy_text: ClassVar[str | None] = None

    BINDINGS = _bindings_for_context("text_area")

    # ── inner message ─────────────────────────────────────────────────────────

    class CursorsChanged(Message):
        """Posted when the extra-cursor list changes (added or cleared)."""

        def __init__(self, text_area: MultiCursorTextArea) -> None:
            super().__init__()
            self.text_area = text_area

        @property
        def control(self) -> MultiCursorTextArea:
            return self.text_area

    class ClipboardAction(Message):
        """Posted when multiline text is copied, cut, or pasted."""

        def __init__(self, text_area: MultiCursorTextArea) -> None:
            super().__init__()
            self.text_area = text_area

        @property
        def control(self) -> MultiCursorTextArea:
            return self.text_area

    # ── lifecycle ─────────────────────────────────────────────────────────────

    # ── Git gutter indicator styles ──────────────────────────────────────────
    # Colors chosen to match common editor conventions.
    _GUTTER_ADDED_COLOR = "#4EC14E"  # green
    _GUTTER_MODIFIED_COLOR = "#E5C07B"  # yellow
    _GUTTER_DELETED_COLOR = "#E06C75"  # red

    # ── Shared overlay colors (for indentation guides and whitespace markers) ─
    _OVERLAY_COLOR_DARK = "#3E3E3E"
    _OVERLAY_COLOR_LIGHT = "#CCCCCC"

    # ── Indentation guide styles ─────────────────────────────────────────────
    _INDENT_GUIDE_CHAR = "│"

    # ── Whitespace rendering styles ───────────────────────────────────────────
    _WHITESPACE_SPACE_CHAR = "·"
    _WHITESPACE_TAB_CHAR = "→"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._extra_cursors: list[tuple[int, int]] = []
        self._extra_anchors: list[tuple[int, int]] = []
        self._extra_last_x_offsets: list[int] = []
        self._cached_selection_ranges: dict[int, list[tuple[int, int | None]]] = {}
        self._line_changes: dict[int, LineChangeType] = {}
        self._show_indentation_guides: bool = True
        self._render_whitespace: str = "none"

    # ── git gutter API ───────────────────────────────────────────────────────

    def set_line_changes(self, changes: dict[int, LineChangeType]) -> None:
        """Update the git diff gutter indicators.

        Args:
            changes: Mapping of line index → change type.
        """
        if changes == self._line_changes:
            return
        self._line_changes = changes
        self._line_cache.clear()
        self.refresh()

    def _resolve_line_index(self, y: int) -> tuple[int, int] | None:
        """Map visual y-coordinate to (line_index, section_offset).

        Returns None when *y* does not correspond to a document line
        (e.g. beyond end-of-file or an invalid offset).
        """
        _, scroll_y = self.scroll_offset
        y_offset = y + scroll_y
        wrapped_document = self.wrapped_document
        if y_offset >= wrapped_document.height:
            return None
        try:
            line_info = wrapped_document._offset_to_line_info[y_offset]
        except IndexError:
            return None
        return line_info

    # ── theme helper ─────────────────────────────────────────────────────────

    def _is_light_theme(self) -> bool:
        """Return True if the current theme background is light."""
        theme = self._theme
        if theme and theme.base_style and theme.base_style.bgcolor:
            triplet = theme.base_style.bgcolor.triplet
            if triplet is not None:
                r, g, b = triplet
                return 0.299 * r + 0.587 * g + 0.114 * b > 128
        return False

    # ── rendering pipeline ───────────────────────────────────────────────────

    def _render_line(self, y: int) -> Strip:
        """Override TextArea._render_line to layer visual enhancements.

        Pipeline: base render → git gutter → whitespace rendering → indentation guides.
        """
        strip = self._render_line_with_gutter(y)
        if self._render_whitespace != "none":
            strip = self._inject_whitespace_rendering(strip, y)
        if self._show_indentation_guides:
            strip = self._inject_indentation_guides(strip, y)
        return strip

    def _render_line_with_gutter(self, y: int) -> Strip:
        """Inject git diff gutter indicators.

        This overrides TextArea._render_line (private API) to replace the
        last gutter margin cell with a colored indicator character when the
        line has a git change.  The coupling to Textual internals is
        documented and guarded by snapshot tests.
        """
        strip = super()._render_line(y)

        if not self._line_changes or not self.show_line_numbers:
            return strip

        line_info = self._resolve_line_index(y)
        if line_info is None:
            return strip

        line_index, section_offset = line_info

        # Only show indicator on the first section of a wrapped line
        if section_offset != 0:
            return strip

        change = self._line_changes.get(line_index)
        if change is None:
            return strip

        # Determine the indicator character and color.
        # Use .value to avoid importing the Enum class at runtime
        # (circular import: code_editor imports multi_cursor_text_area).
        change_value = change.value
        if change_value == "added":
            char = "▎"
            fg_color = self._GUTTER_ADDED_COLOR
        elif change_value == "modified":
            char = "▎"
            fg_color = self._GUTTER_MODIFIED_COLOR
        elif change_value == "deleted_above":
            char = "▔"
            fg_color = self._GUTTER_DELETED_COLOR
        elif change_value == "deleted_below":
            char = "▁"
            fg_color = self._GUTTER_DELETED_COLOR
        else:
            return strip

        # Determine the gutter background color for this line
        theme = self._theme
        cursor_row = self.selection.end[0]
        is_cursor_line = cursor_row == line_index and self.highlight_cursor_line
        if theme:
            gutter_bg = (
                theme.cursor_line_gutter_style if is_cursor_line else theme.gutter_style
            )
            bg_color = gutter_bg.bgcolor if gutter_bg else None
        else:
            bg_color = None

        indicator_style = Style(color=fg_color, bgcolor=bg_color)

        # Replace the last gutter cell (a margin space) with the indicator
        gutter_width = self.gutter_width
        if gutter_width < 1 or strip.cell_length < gutter_width:
            return strip

        before = strip.crop(0, gutter_width - 1)
        after = strip.crop(gutter_width, strip.cell_length)
        indicator = Strip([Segment(char, indicator_style)], cell_length=1)
        return Strip.join([before, indicator, after])

    def _inject_whitespace_rendering(self, strip: Strip, y: int) -> Strip:
        """Replace whitespace characters with visible markers.

        Modes:
          - "all": replace every space/tab with a visible marker
          - "boundary": replace only leading and trailing whitespace
                        (differs from VS Code's "boundary" which excludes single
                        spaces between words — here we skip ALL middle whitespace)
          - "trailing": replace only trailing whitespace
        """
        mode = self._render_whitespace
        if mode == "none":
            return strip

        line_info = self._resolve_line_index(y)
        if line_info is None:
            return strip

        line_index, section_offset = line_info
        # Only render whitespace on the first section of a wrapped line
        if section_offset != 0:
            return strip

        doc_line = self.document.get_line(line_index)
        if not doc_line:
            return strip

        indent_width = self.indent_width

        # Build visual-column → marker-char map from original doc line.
        # Tabs expand to indent_width columns; the first column gets "→",
        # remaining tab-fill columns get "·".
        ws_map: dict[int, str] = {}
        visual_col = 0
        for ch in doc_line:
            if ch == "\t":
                tab_stop = (
                    indent_width - (visual_col % indent_width)
                    if indent_width > 0
                    else 1
                )
                ws_map[visual_col] = self._WHITESPACE_TAB_CHAR
                for i in range(1, tab_stop):
                    ws_map[visual_col + i] = self._WHITESPACE_SPACE_CHAR
                visual_col += tab_stop
            elif ch == " ":
                ws_map[visual_col] = self._WHITESPACE_SPACE_CHAR
                visual_col += 1
            else:
                visual_col += cell_len(ch)

        if not ws_map:
            return strip

        # Determine which visual columns to render based on mode.
        if mode == "all":
            render_cols = set(ws_map.keys())
        else:
            expanded = doc_line.expandtabs(indent_width)
            stripped = expanded.strip()
            if not stripped:
                # All-whitespace line: render everything for all modes
                render_cols = set(ws_map.keys())
            else:
                leading_count = len(expanded) - len(expanded.lstrip())
                trailing_start = len(expanded.rstrip())
                if mode == "trailing":
                    render_cols = {c for c in ws_map if c >= trailing_start}
                elif mode == "boundary":
                    render_cols = {
                        c for c in ws_map if c < leading_count or c >= trailing_start
                    }
                else:
                    render_cols = set()

        if not render_cols:
            return strip

        gutter_width = self.gutter_width if self.show_line_numbers else 0
        scroll_x = self.scroll_offset.x if not self.soft_wrap else 0
        ws_fg = (
            self._OVERLAY_COLOR_LIGHT
            if self._is_light_theme()
            else self._OVERLAY_COLOR_DARK
        )

        new_segments: list[Segment] = []
        cell_pos = 0
        for seg in strip:
            seg_text = seg.text
            seg_style = seg.style
            seg_len = cell_len(seg_text)

            seg_end = cell_pos + seg_len
            content_start = cell_pos - gutter_width + scroll_x
            content_end = seg_end - gutter_width + scroll_x

            # Fast path: segment entirely outside render region
            if cell_pos < gutter_width or not any(
                content_start <= c < content_end for c in render_cols
            ):
                new_segments.append(seg)
                cell_pos = seg_end
                continue

            # Slow path: some render columns fall within this segment
            existing_bg = seg_style.bgcolor if seg_style else None
            ws_style = Style(color=ws_fg, bgcolor=existing_bg)
            for ch in seg_text:
                content_col = cell_pos - gutter_width + scroll_x
                marker = ws_map.get(content_col)
                if content_col in render_cols and marker is not None:
                    new_segments.append(Segment(marker, ws_style))
                else:
                    new_segments.append(Segment(ch, seg_style))
                cell_pos += cell_len(ch)

        return Strip(new_segments, cell_length=strip.cell_length)

    def _inject_indentation_guides(self, strip: Strip, y: int) -> Strip:
        """Replace leading whitespace at indent-level positions with guide chars.

        Guide characters are placed at every ``indent_width`` multiple within
        the leading whitespace of each line, starting from column 0.
        """
        indent_width = self.indent_width
        if indent_width < 1:
            return strip

        line_info = self._resolve_line_index(y)
        if line_info is None:
            return strip

        line_index, section_offset = line_info
        # Only show guides on the first section of a wrapped line
        if section_offset != 0:
            return strip

        doc_line = self.document.get_line(line_index)
        expanded = doc_line.expandtabs(indent_width)
        leading_spaces = len(expanded) - len(expanded.lstrip())
        if leading_spaces < indent_width:
            return strip

        guide_positions = set(range(0, leading_spaces, indent_width))
        gutter_width = self.gutter_width if self.show_line_numbers else 0
        scroll_x = self.scroll_offset.x if not self.soft_wrap else 0

        guide_fg = (
            self._OVERLAY_COLOR_LIGHT
            if self._is_light_theme()
            else self._OVERLAY_COLOR_DARK
        )

        new_segments: list[Segment] = []
        cell_pos = 0
        for seg in strip:
            seg_text = seg.text
            seg_style = seg.style
            seg_len = cell_len(seg_text)

            # Fast path: segment entirely outside guide region
            seg_end = cell_pos + seg_len
            content_start = cell_pos - gutter_width + scroll_x
            content_end = seg_end - gutter_width + scroll_x

            if cell_pos < gutter_width or not any(
                content_start <= p < content_end for p in guide_positions
            ):
                new_segments.append(seg)
                cell_pos = seg_end
                continue

            # Slow path: guide positions fall within this segment
            # Pre-compute guide style for this segment (bgcolor is constant per segment)
            existing_bg = seg_style.bgcolor if seg_style else None
            guide_style = Style(color=guide_fg, bgcolor=existing_bg)
            for ch in seg_text:
                content_col = cell_pos - gutter_width + scroll_x
                if content_col in guide_positions:
                    new_segments.append(Segment(self._INDENT_GUIDE_CHAR, guide_style))
                else:
                    new_segments.append(Segment(ch, seg_style))
                cell_pos += cell_len(ch)

        return Strip(new_segments, cell_length=strip.cell_length)

    # ── public API ────────────────────────────────────────────────────────────

    @property
    def extra_cursors(self) -> list[tuple[int, int]]:
        """A copy of the extra-cursor list (read-only view)."""
        return list(self._extra_cursors)

    @property
    def extra_anchors(self) -> list[tuple[int, int]]:
        """A copy of the extra-anchor list (read-only view)."""
        return list(self._extra_anchors)

    def _cell_width_at(self, location: tuple[int, int]) -> int:
        """Get the visual (cell) x offset at a document location."""
        x_offset, _ = self.wrapped_document.location_to_offset(location)
        return x_offset

    def add_cursor(
        self, location: tuple[int, int], anchor: tuple[int, int] | None = None
    ) -> None:
        """Add an extra cursor at *location* with optional *anchor*.

        If *anchor* is None, the cursor is collapsed (anchor == location).
        No-op if *location* equals the primary cursor position or is already
        present in the extra-cursor list.
        """
        anchor = anchor if anchor is not None else location
        if location != self.cursor_location and location not in self._extra_cursors:
            self._extra_cursors = self._extra_cursors + [location]
            self._extra_anchors = self._extra_anchors + [anchor]
            self._extra_last_x_offsets = self._extra_last_x_offsets + [
                self._cell_width_at(location)
            ]
            self._recompute_selection_ranges()
            self._line_cache.clear()
            self.refresh()
            self.post_message(self.CursorsChanged(self))

    def action_undo(self) -> None:
        """Block undo in read-only mode to match VSCode behavior."""
        if self.read_only:
            return
        super().action_undo()

    def action_redo(self) -> None:
        """Block redo in read-only mode to match VSCode behavior."""
        if self.read_only:
            return
        super().action_redo()

    def action_select_all(self) -> None:
        """Select all text and clear extra cursors."""
        with self.app.batch_update():
            super().action_select_all()
            self.clear_extra_cursors()

    def clear_extra_cursors(self) -> None:
        """Remove all extra cursors."""
        if self._extra_cursors:
            self._extra_cursors = []
            self._extra_anchors = []
            self._extra_last_x_offsets = []
            self._cached_selection_ranges = {}
            self._line_cache.clear()
            self.refresh()
            self.post_message(self.CursorsChanged(self))

    # ── selection range cache ──────────────────────────────────────────────────

    def _recompute_selection_ranges(self) -> None:
        """Pre-compute selection ranges per line for O(1) get_line() lookup."""
        result: dict[int, list[tuple[int, int | None]]] = {}
        for (row, col), anchor in zip(
            self._extra_cursors, self._extra_anchors, strict=True
        ):
            if anchor == (row, col):
                continue
            sel_start = min(anchor, (row, col))
            sel_end = max(anchor, (row, col))
            s_row, s_col = sel_start
            e_row, e_col = sel_end
            for line_idx in range(s_row, e_row + 1):
                start = s_col if line_idx == s_row else 0
                end: int | None = e_col if line_idx == e_row else None
                result.setdefault(line_idx, []).append((start, end))
        self._cached_selection_ranges = result

    # ── indent / dedent ───────────────────────────────────────────────────────

    @property
    def _use_tabs(self) -> bool:
        return self.indent_type == "tabs"

    def action_indent_line(self) -> None:
        """VS Code style: add indent at start of selected lines, or at cursor."""
        from textual.widgets.text_area import Selection

        use_tabs = self._use_tabs
        indent = "\t" if use_tabs else " " * self.indent_width
        indent_col_width = 1 if use_tabs else self.indent_width
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
            new_start = (start_row, start_col + indent_col_width)
            new_end = (end_row, end_col + indent_col_width if end_col > 0 else 0)
            self.selection = Selection(start=new_start, end=new_end)
        else:
            # Single line or no selection: insert at cursor
            self.replace(indent, self.cursor_location, self.cursor_location)

    def action_outdent_line(self) -> None:
        """Remove up to one indent level of leading whitespace from each line."""
        from textual.widgets.text_area import Selection

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
                if lines[row].startswith("\t"):
                    lines[row] = lines[row][1:]
                    removed[row] = 1
                else:
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

    # ── move line up/down ────────────────────────────────────────────────────

    @staticmethod
    def _row_range(loc_a: tuple[int, int], loc_b: tuple[int, int]) -> tuple[int, int]:
        """Return (top_row, bottom_row) for a cursor/anchor pair.

        If the pair spans multiple rows and the bottom location is at column 0,
        the bottom row is excluded (VS Code / indent-dedent convention).
        """
        top_loc, bot_loc = min(loc_a, loc_b), max(loc_a, loc_b)
        top, bot = top_loc[0], bot_loc[0]
        if bot > top and bot_loc[1] == 0:
            bot -= 1
        return (top, bot)

    def _move_lines(self, direction: int) -> None:
        """Move line(s) at all cursors up (direction=-1) or down (+1)."""
        from textual.widgets.text_area import Selection

        lines = self.text.split("\n")
        num_lines = len(lines)

        # Collect row ranges from primary + extra cursors
        sel = self.selection
        ranges = [self._row_range(sel.start, sel.end)]
        for cursor, anchor in zip(
            self._extra_cursors, self._extra_anchors, strict=True
        ):
            ranges.append(self._row_range(cursor, anchor))

        # Sort and merge overlapping/adjacent ranges
        ranges.sort()
        merged: list[list[int]] = [list(ranges[0])]
        for s, e in ranges[1:]:
            if s <= merged[-1][1] + 1:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])

        # Boundary check: all blocks must be movable
        if direction == 1:  # down
            if any(e >= num_lines - 1 for _, e in merged):
                return
        else:  # up
            if any(s <= 0 for s, _ in merged):
                return

        # Relocate adjacent lines
        if direction == 1:
            for s, e in reversed(merged):
                line_below = lines.pop(e + 1)
                lines.insert(s, line_below)
        else:
            for s, e in merged:
                line_above = lines.pop(s - 1)
                lines.insert(e, line_above)

        self.replace("\n".join(lines), self.document.start, self.document.end)

        # Shift primary selection
        self.selection = Selection(
            start=(sel.start[0] + direction, sel.start[1]),
            end=(sel.end[0] + direction, sel.end[1]),
        )

        # Shift extra cursors and anchors
        if self._extra_cursors:
            self._extra_cursors = [(r + direction, c) for r, c in self._extra_cursors]
            self._extra_anchors = [(r + direction, c) for r, c in self._extra_anchors]
            self._recompute_selection_ranges()
            self._line_cache.clear()
            self.refresh()

    def action_move_line_up(self) -> None:
        """Move selected line(s) up by one row."""
        self._move_lines(-1)

    def action_move_line_down(self) -> None:
        """Move selected line(s) down by one row."""
        self._move_lines(1)

    # ── word deletion ─────────────────────────────────────────────────────────

    def action_delete_word_left(self) -> None:
        """Delete from cursor to previous word boundary (Ctrl+Backspace)."""
        if not self._extra_cursors:
            super().action_delete_word_left()
            return
        self._delete_word_multi("left")

    def action_delete_word_right(self) -> None:
        """Delete from cursor to next word boundary (Ctrl+Delete)."""
        if not self._extra_cursors:
            super().action_delete_word_right()
            return
        self._delete_word_multi("right")

    def _delete_word_multi(self, direction: Literal["left", "right"]) -> None:
        """Delete word at all cursor positions."""
        from textual.widgets.text_area import Selection

        text = self.text
        lines = text.split("\n")
        offsets = _build_offsets(lines)

        primary = self.cursor_location
        primary_anchor = self.selection.start
        extra = list(self._extra_cursors)
        extra_anchors = list(self._extra_anchors)

        all_pairs = [(primary_anchor, primary)] + list(
            zip(extra_anchors, extra, strict=True)
        )

        def to_off(row: int, col: int) -> int:
            return offsets[row] + col

        ops: list[list[int]] = []
        p_start = to_off(*primary)  # default for right direction
        for anchor, cursor in all_pairs:
            if anchor != cursor:
                # Has selection — delete the selection content
                a_off = to_off(*anchor)
                c_off = to_off(*cursor)
                ops.append([min(a_off, c_off), max(a_off, c_off)])
                if cursor == primary:
                    p_start = min(a_off, c_off)
            elif direction == "left":
                row, col = cursor
                target = self._move_location(lines, row, col, "ctrl+left")
                t_off = to_off(*target)
                c_off = to_off(row, col)
                if t_off < c_off:
                    ops.append([t_off, c_off])
                if cursor == primary:
                    p_start = t_off
            else:
                row, col = cursor
                c_off = to_off(row, col)
                line = lines[row] if row < len(lines) else ""
                remaining = line[col:]
                matches = list(_WORD_PATTERN.finditer(remaining))
                if matches:
                    end_off = to_off(row, col + matches[0].end())
                elif row < len(lines) - 1 and col == len(line):
                    end_off = to_off(row + 1, 0)
                else:
                    end_off = to_off(row, len(line))
                if end_off > c_off:
                    ops.append([c_off, end_off])

        if not ops:
            return

        # Sort and merge overlapping ranges
        ops.sort()
        deduped: list[list[int]] = []
        for op in ops:
            if deduped and op[0] <= deduped[-1][1]:
                deduped[-1][1] = max(deduped[-1][1], op[1])
            else:
                deduped.append(list(op))

        # Build new text and track cursor offsets
        parts: list[str] = []
        prev = 0
        new_cursor_offsets: list[int] = []
        accumulated = 0
        for s, e in deduped:
            parts.append(text[prev:s])
            new_cursor_offsets.append(accumulated + (s - prev))
            accumulated += s - prev
            prev = e
        parts.append(text[prev:])
        new_text = "".join(parts)

        self.replace(new_text, self.document.start, self.document.end)

        new_lines = new_text.split("\n")
        new_offsets = _build_offsets(new_lines)
        new_locs = [
            _offset_to_loc(off, new_lines, new_offsets) for off in new_cursor_offsets
        ]

        if not new_locs:
            return

        # Match primary cursor to its deduped range
        primary_idx = 0
        for i, (s, _e) in enumerate(deduped):
            if s <= p_start <= _e:
                primary_idx = i
                break

        new_primary = (
            new_locs[primary_idx] if primary_idx < len(new_locs) else new_locs[0]
        )
        self.selection = Selection(new_primary, new_primary)
        self._extra_cursors = [
            loc for i, loc in enumerate(new_locs) if i != primary_idx
        ]
        self._extra_anchors = list(self._extra_cursors)
        self._extra_last_x_offsets = [0] * len(self._extra_cursors)
        self._recompute_selection_ranges()
        self._line_cache.clear()
        self.refresh()

    # ── sort lines ────────────────────────────────────────────────────────────

    def _sort_lines(self, reverse: bool) -> None:
        """Sort selected line(s) at all cursors alphabetically."""
        from textual.widgets.text_area import Selection

        lines = self.text.split("\n")

        # Collect row ranges from primary + extra cursors
        sel = self.selection
        extra_cursors = list(self._extra_cursors)
        extra_anchors = list(self._extra_anchors)
        ranges = [self._row_range(sel.start, sel.end)]
        for cursor, anchor in zip(extra_cursors, extra_anchors, strict=True):
            ranges.append(self._row_range(cursor, anchor))

        # Sort and merge overlapping/adjacent ranges
        ranges.sort()
        merged: list[list[int]] = [list(ranges[0])]
        for s, e in ranges[1:]:
            if s <= merged[-1][1] + 1:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])

        # Skip if all ranges are single lines (nothing to sort)
        if all(s == e for s, e in merged):
            return

        # Snapshot old lines per range for position tracking
        old_range_lines = {(s, e): lines[s : e + 1] for s, e in merged}

        # Sort lines in each range
        for s, e in merged:
            lines[s : e + 1] = sorted(lines[s : e + 1], reverse=reverse)

        # Snapshot new lines per range
        new_range_lines = {(s, e): lines[s : e + 1] for s, e in merged}

        self.replace("\n".join(lines), self.document.start, self.document.end)

        # Adjust positions via character offset tracking (VSCode behavior):
        # convert (row, col) → char offset in old text → same offset in new text
        # → convert back to (row, col).
        def adjust(pos: tuple[int, int]) -> tuple[int, int]:
            row, col = pos
            for s, e in merged:
                if s <= row <= e:
                    old_ls = old_range_lines[(s, e)]
                    new_ls = new_range_lines[(s, e)]
                    # Character offset in old range text
                    offset = sum(len(old_ls[r - s]) + 1 for r in range(s, row)) + col
                    # Clamp to new range text length
                    total = sum(len(ln) + 1 for ln in new_ls[:-1]) + len(new_ls[-1])
                    offset = min(offset, total)
                    # Convert back to (row, col)
                    remaining = offset
                    for r in range(s, e + 1):
                        line_len = len(new_ls[r - s])
                        if remaining <= line_len:
                            return (r, remaining)
                        remaining -= line_len + 1
                    return (e, len(new_ls[-1]))
            return pos

        self.selection = Selection(start=adjust(sel.start), end=adjust(sel.end))
        if extra_cursors:
            self._extra_cursors = [adjust(c) for c in extra_cursors]
            self._extra_anchors = [adjust(a) for a in extra_anchors]
            self._recompute_selection_ranges()
            self._line_cache.clear()
            self.refresh()

    def action_sort_lines_ascending(self) -> None:
        """Sort selected line(s) in ascending order."""
        self._sort_lines(reverse=False)

    def action_sort_lines_descending(self) -> None:
        """Sort selected line(s) in descending order."""
        self._sort_lines(reverse=True)

    # ── transform case ───────────────────────────────────────────────────────

    @staticmethod
    def _end_location_after_insert(
        start: tuple[int, int], new_text: str
    ) -> tuple[int, int]:
        """Compute end (row, col) after inserting *new_text* at *start*."""
        lines = new_text.split("\n")
        if len(lines) == 1:
            return (start[0], start[1] + len(new_text))
        return (start[0] + len(lines) - 1, len(lines[-1]))

    def _transform_case(self, transform: Callable[[str], str]) -> None:
        """Transform selected text using the given callable (e.g. str.upper).

        When the cursor is collapsed (no selection), auto-selects the word
        under the cursor before transforming, matching VS Code behavior.
        """
        from textual.widgets.text_area import Selection

        if self.read_only:
            return

        text = self.selected_text
        if not text:
            # Auto-select word under cursor (VS Code behavior)
            row, col = self.cursor_location
            bounds = self._word_bounds_at(self.text, row, col)
            if bounds is None:
                return
            start = (row, bounds[0])
            end = (row, bounds[1])
            text = self.document.get_line(row)[bounds[0] : bounds[1]]
        else:
            sel = self.selection
            start, end = sel.start, sel.end

        new_text = transform(text)
        self.replace(new_text, start, end)
        new_end = self._end_location_after_insert(start, new_text)
        self.selection = Selection(start=start, end=new_end)

    def action_transform_uppercase(self) -> None:
        """Transform selected text to uppercase."""
        self._transform_case(str.upper)

    def action_transform_lowercase(self) -> None:
        """Transform selected text to lowercase."""
        self._transform_case(str.lower)

    def action_transform_title_case(self) -> None:
        """Transform selected text to title case."""
        self._transform_case(str.title)

    def action_transform_snake_case(self) -> None:
        """Transform selected text to snake_case."""
        self._transform_case(_to_snake_case)

    def action_transform_camel_case(self) -> None:
        """Transform selected text to camelCase."""
        self._transform_case(_to_camel_case)

    def action_transform_kebab_case(self) -> None:
        """Transform selected text to kebab-case."""
        self._transform_case(_to_kebab_case)

    def action_transform_pascal_case(self) -> None:
        """Transform selected text to PascalCase."""
        self._transform_case(_to_pascal_case)

    # ── scroll viewport ──────────────────────────────────────────────────────

    def action_scroll_up(self) -> None:
        """Scroll viewport one line up without moving cursor."""
        self.scroll_up(animate=False)

    def action_scroll_down(self) -> None:
        """Scroll viewport one line down without moving cursor."""
        self.scroll_down(animate=False)

    # ── shift+page up/down (select while paging) ─────────────────────────────

    def _cursor_page_select(self, direction: int) -> None:
        """Move cursor one page up (-1) or down (+1) while extending selection."""
        if not self.show_cursor:
            if direction < 0:
                self.scroll_page_up()
            else:
                self.scroll_page_down()
            return
        height = max(1, self.content_size.height)
        _, cursor_location = self.selection
        target = self.navigator.get_location_at_y_offset(
            cursor_location,
            direction * height,
        )
        self.scroll_relative(y=direction * height, animate=False)
        self.move_cursor(target, select=True)

    def action_cursor_page_up_select(self) -> None:
        """Move cursor one page up while extending selection."""
        self._cursor_page_select(-1)

    def action_cursor_page_down_select(self) -> None:
        """Move cursor one page down while extending selection."""
        self._cursor_page_select(1)

    def action_cursor_document_start(self, select: bool = False) -> None:
        """Move cursor to the start of the document (ctrl+home)."""
        self.move_cursor((0, 0), select=select)

    def action_cursor_document_end(self, select: bool = False) -> None:
        """Move cursor to the end of the document (ctrl+end)."""
        last_line = self.document.line_count - 1
        last_col = len(self.document[last_line])
        self.move_cursor((last_line, last_col), select=select)

    # ── smart home (VSCode-style) ─────────────────────────────────────────────

    @staticmethod
    def _smart_home_col(line: str, col: int) -> int:
        """Return the target column for VSCode-style smart home.

        Toggles between the first non-whitespace column and column 0.
        """
        first_non_ws = 0
        for i, ch in enumerate(line):
            if not ch.isspace():
                first_non_ws = i
                break
        else:
            return 0
        return 0 if col == first_non_ws else first_non_ws

    def get_cursor_line_start_location(
        self, smart_home: bool = False
    ) -> tuple[int, int]:
        """Override to implement VSCode-style smart home.

        VSCode logic: if cursor is at the first non-whitespace character,
        go to column 0.  Otherwise, go to the first non-whitespace character.
        Textual's default goes to column 0 when cursor is within the indent
        area (between col 0 and first non-WS); VSCode goes to first non-WS.
        """
        if not smart_home:
            return super().get_cursor_line_start_location(smart_home=False)

        row, col = self.cursor_location
        return (row, self._smart_home_col(self.document[row], col))

    # ── rendering ─────────────────────────────────────────────────────────────

    def get_line(self, line_index: int) -> Text:
        """Render extra cursors and their selections."""
        line = super().get_line(line_index)
        if self._extra_cursors and self._theme:
            cursor_style = self._theme.cursor_style
            selection_style = self._theme.selection_style

            # Render selection ranges (pre-computed for O(1) lookup)
            if selection_style:
                for start_col, end_col in self._cached_selection_ranges.get(
                    line_index, []
                ):
                    end = end_col if end_col is not None else len(line.plain)
                    if start_col < end:
                        line.stylize(selection_style, start_col, end)

            # Render cursor positions
            if cursor_style:
                for row, col in self._extra_cursors:
                    if row == line_index and 0 <= col <= len(line.plain):
                        line.stylize(cursor_style, col, col + 1)

        return line

    # ── click handling ────────────────────────────────────────────────────────

    @staticmethod
    def _word_bounds_at(text: str, row: int, col: int) -> tuple[int, int] | None:
        """Return (start_col, end_col) of the word at (row, col), or None.

        Uses \\w+ boundaries.  Returns None if (row, col) is not inside a word
        (whitespace, punctuation, or past end of line).
        """
        lines = text.split("\n")
        if row >= len(lines):
            return None
        line = lines[row]
        if col >= len(line):
            return None
        for m in re.finditer(r"\w+", line):
            if m.start() <= col < m.end():
                return (m.start(), m.end())
        return None

    def on_click(self, event: events.Click) -> None:
        """Handle click for cursor clear and word/line selection."""
        from textual.widgets.text_area import Selection

        if self._extra_cursors:
            self.clear_extra_cursors()

        if event.chain == 1:
            return  # single click: TextArea handles normally

        row, col = self.cursor_location

        if event.chain == 2:
            # Double-click: select word at cursor
            bounds = self._word_bounds_at(self.text, row, col)
            if bounds is not None:
                start, end = bounds
                self.selection = Selection((row, start), (row, end))

        elif event.chain == 3:
            # Triple-click: select entire line
            lines = self.text.split("\n")
            line = lines[row] if row < len(lines) else ""
            self.selection = Selection((row, 0), (row, len(line)))

    # ── copy / cut / paste overrides ────────────────────────────────────────

    def action_copy(self) -> None:
        """Copy selection; copy current line if nothing selected (VS Code)."""
        selected = self.selected_text
        if selected:
            self.app.copy_to_clipboard(selected)
            MultiCursorTextArea._line_copy_text = None
            if "\n" in selected:
                self.post_message(self.ClipboardAction(self))
        else:
            row, _ = self.cursor_location
            line = self.document.get_line(row)
            line_text = line + "\n"
            self.app.copy_to_clipboard(line_text)
            MultiCursorTextArea._line_copy_text = line_text
            self.post_message(self.ClipboardAction(self))

    def action_cut(self) -> None:
        """Cut selection; cut current line if nothing selected (VS Code)."""
        if self.read_only:
            return
        text = self.selected_text
        is_line_cut = not text
        has_newline = "\n" in text if text else True  # no selection → whole line
        super().action_cut()
        MultiCursorTextArea._line_copy_text = (
            self.app.clipboard if is_line_cut else None
        )
        if has_newline:
            self.post_message(self.ClipboardAction(self))

    def action_paste(self) -> None:
        """Paste from clipboard; line-copied text inserts above current line."""
        if self.read_only:
            return
        clipboard = self.app.clipboard
        if not clipboard:
            return
        has_newline = "\n" in clipboard
        start, end = self.selection

        if (
            MultiCursorTextArea._line_copy_text is not None
            and MultiCursorTextArea._line_copy_text == clipboard
            and start == end
        ):
            # VS Code line-paste: insert above current line, cursor follows
            row, col = self.cursor_location
            self._replace_via_keyboard(clipboard, (row, 0), (row, 0))
            inserted_lines = clipboard.count("\n")
            self.move_cursor((row + inserted_lines, col))
        else:
            super().action_paste()

        if has_newline:
            self.post_message(self.ClipboardAction(self))

    async def _on_paste(self, event: events.Paste) -> None:
        """Handle paste from terminal (bracketed paste).

        On Windows Terminal, Ctrl+V sends a Paste event instead of
        triggering the action_paste key binding.  This override
        normalizes CRLF, updates the local clipboard, and delegates
        to action_paste so line-paste logic is applied consistently.
        """
        # Stop the base TextArea._on_paste from also running
        # (Textual dispatches _on_ handlers for every class in the MRO)
        # and prevent bubbling to parent widgets.
        event.prevent_default()
        event.stop()

        if self.read_only:
            return

        text = event.text.replace("\r\n", "\n").replace("\r", "\n")
        if not text:
            return

        # Prefer local clipboard when it matches the pasted text
        # after CRLF normalization (preserves exact whitespace).
        local = self.app.clipboard
        if local != text:
            # Windows Terminal may strip trailing whitespace from each line
            # and/or trailing newlines.  If texts match after stripping,
            # prefer the local clipboard to preserve exact whitespace
            # and line-copy state.
            local_stripped = "\n".join(
                line.rstrip() for line in local.rstrip().split("\n")
            )
            text_stripped = "\n".join(
                line.rstrip() for line in text.rstrip().split("\n")
            )
            if local_stripped != text_stripped:
                self.app.copy_to_clipboard(text)
                MultiCursorTextArea._line_copy_text = None

        self.action_paste()

    # ── cursor movement ────────────────────────────────────────────────────────

    @staticmethod
    def _move_location(
        lines: list[str],
        row: int,
        col: int,
        base_key: str,
        page_height: int = 20,
    ) -> tuple[int, int]:
        """Compute new (row, col) after applying *base_key* movement."""
        last_row = max(0, len(lines) - 1)

        if base_key == "left":
            if col > 0:
                return (row, col - 1)
            if row > 0:
                return (row - 1, len(lines[row - 1]))
            return (row, col)

        elif base_key == "right":
            line_len = len(lines[row]) if row < len(lines) else 0
            if col < line_len:
                return (row, col + 1)
            if row < last_row:
                return (row + 1, 0)
            return (row, col)

        elif base_key == "up":
            if row > 0:
                return (
                    row - 1,
                    min(col, len(lines[row - 1]) if row - 1 < len(lines) else 0),
                )
            return (row, col)

        elif base_key == "down":
            if row < last_row:
                return (
                    row + 1,
                    min(col, len(lines[row + 1]) if row + 1 < len(lines) else 0),
                )
            return (row, col)

        elif base_key == "home":
            line = lines[row] if row < len(lines) else ""
            return (row, MultiCursorTextArea._smart_home_col(line, col))

        elif base_key == "end":
            return (row, len(lines[row]) if row < len(lines) else 0)

        elif base_key == "ctrl+home":
            return (0, 0)

        elif base_key == "ctrl+end":
            last_col = len(lines[last_row]) if last_row < len(lines) else 0
            return (last_row, last_col)

        elif base_key == "ctrl+left":
            if row > 0 and col == 0:
                prev = lines[row - 1]
                if not prev.strip():
                    return (row - 1, 0)
                # Skip trailing whitespace, land on last word boundary
                rstripped = prev.rstrip()
                m = list(_WORD_PATTERN.finditer(rstripped))
                return (row - 1, m[-1].start() if m else 0)
            line = lines[row][:col] if row < len(lines) else ""
            matches = list(_WORD_PATTERN.finditer(line.rstrip()))
            return (row, matches[-1].start() if matches else 0)

        elif base_key == "ctrl+right":
            line = lines[row] if row < len(lines) else ""
            if row < last_row and col == len(line):
                nxt = lines[row + 1]
                if not nxt.strip():
                    return (row + 1, 0)
                # Skip leading whitespace, land on first word boundary
                s = nxt
                off = len(s) - len(s.lstrip())
                s = s.lstrip()
                m = list(_WORD_PATTERN.finditer(s))
                if m:
                    return (row + 1, m[0].start() + off)
                return (row + 1, len(nxt))
            search = line[col:]
            strip_offset = len(search) - len(search.lstrip())
            search = search.lstrip()
            matches = list(_WORD_PATTERN.finditer(search))
            return (
                row,
                col
                + (matches[0].start() + strip_offset if matches else len(line) - col),
            )

        elif base_key == "pageup":
            new_row = max(0, row - page_height)
            return (
                new_row,
                min(col, len(lines[new_row]) if new_row < len(lines) else 0),
            )

        elif base_key == "pagedown":
            new_row = min(last_row, row + page_height)
            return (
                new_row,
                min(col, len(lines[new_row]) if new_row < len(lines) else 0),
            )

        return (row, col)

    def _move_all_cursors(self, key: str) -> None:
        """Move primary and all extra cursors according to *key*.

        For up/down, delegates to DocumentNavigator (handles sticky column
        and boundary conditions). For all other keys, uses _move_location().
        """
        from textual.widgets.text_area import Selection

        is_shift = "shift+" in key
        base_key = key.replace("shift+", "") if is_shift else key
        is_vertical = base_key in ("up", "down")

        nav = self.navigator
        saved_x_offset = nav.last_x_offset

        try:
            if is_vertical:
                # Vertical: delegate to DocumentNavigator which handles sticky
                # column (last_x_offset) and boundary cases (up@first→(0,0),
                # down@last→end-of-line).  We temporarily swap the navigator's
                # last_x_offset per extra cursor to give each its own sticky
                # column, then restore the primary cursor's offset.
                nav_method = (
                    nav.get_location_above
                    if base_key == "up"
                    else nav.get_location_below
                )

                primary = self.cursor_location
                new_primary = nav_method(primary)

                new_extras: list[tuple[int, int]] = []
                new_anchors: list[tuple[int, int]] = []
                new_extra_offsets: list[int] = []
                for i, ((row, col), anchor) in enumerate(
                    zip(self._extra_cursors, self._extra_anchors, strict=True)
                ):
                    nav.last_x_offset = self._extra_last_x_offsets[i]
                    new_pos = nav_method((row, col))
                    new_extras.append(new_pos)
                    new_anchors.append(anchor if is_shift else new_pos)
                    # Preserve stored offset — vertical movement keeps sticky column.
                    new_extra_offsets.append(self._extra_last_x_offsets[i])

                nav.last_x_offset = saved_x_offset
            else:
                # Non-vertical: use _move_location, then update sticky offsets.
                lines = self.document.lines
                try:
                    page_height = max(1, self.scrollable_content_region.height)
                except Exception:
                    page_height = 20

                primary = self.cursor_location
                new_primary = self._move_location(
                    lines, *primary, base_key, page_height
                )
                nav.last_x_offset = self._cell_width_at(new_primary)

                new_extras = []
                new_anchors = []
                new_extra_offsets: list[int] = []
                for (row, col), anchor in zip(
                    self._extra_cursors, self._extra_anchors, strict=True
                ):
                    new_pos = self._move_location(
                        lines, row, col, base_key, page_height
                    )
                    new_extras.append(new_pos)
                    new_anchors.append(anchor if is_shift else new_pos)
                    new_extra_offsets.append(self._cell_width_at(new_pos))
        except Exception:
            nav.last_x_offset = saved_x_offset
            raise

        if is_shift:
            self.selection = Selection(self.selection.start, new_primary)
        else:
            self.selection = Selection(new_primary, new_primary)

        # Deduplicate: remove extras that collide with primary or each other
        deduped_extras: list[tuple[int, int]] = []
        deduped_anchors: list[tuple[int, int]] = []
        deduped_offsets: list[int] = []
        seen = {new_primary}
        for i, (pos, anc) in enumerate(zip(new_extras, new_anchors, strict=True)):
            if pos not in seen:
                seen.add(pos)
                deduped_extras.append(pos)
                deduped_anchors.append(anc)
                deduped_offsets.append(new_extra_offsets[i])

        self._extra_cursors = deduped_extras
        self._extra_anchors = deduped_anchors
        self._extra_last_x_offsets = deduped_offsets
        self._recompute_selection_ranges()
        self._line_cache.clear()
        self.refresh()

    # ── key handling ──────────────────────────────────────────────────────────

    def on_key(self, event: events.Key) -> None:
        """Intercept key events when extra cursors are active."""
        if not self._extra_cursors:
            return  # let TextArea handle everything normally

        if event.key == "escape":
            event.prevent_default()
            event.stop()
            self.clear_extra_cursors()
            return

        if _is_movement_key(event):
            event.prevent_default()
            event.stop()
            self._move_all_cursors(event.key)
            return

        if _is_editing_key(event) or event.key == "enter":
            # Handle ourselves; suppress TextArea's default behaviour.
            event.prevent_default()
            event.stop()
            self._apply_to_all_cursors(event)

        # tab/shift+tab fall through to action_indent_line / action_outdent_line

    # ── multi-cursor editing ──────────────────────────────────────────────────

    def _apply_to_all_cursors(self, event: events.Key) -> None:
        """Apply a simple edit to the primary cursor and all extra cursors.

        Delegates to ``_apply_with_selections`` when any cursor has an active
        selection; otherwise uses the existing per-operation helpers.
        """
        lines = self.text.split("\n")
        primary = self.cursor_location
        primary_anchor = self.selection.start
        extra = list(self._extra_cursors)
        extra_anchors = list(self._extra_anchors)

        has_selections = (primary_anchor != primary) or any(
            a != c for a, c in zip(extra_anchors, extra, strict=True)
        )
        if has_selections:
            self._apply_with_selections(
                event, primary, primary_anchor, extra, extra_anchors
            )
            return

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

    def _apply_with_selections(
        self,
        event: events.Key,
        primary: tuple[int, int],
        primary_anchor: tuple[int, int],
        extra: list[tuple[int, int]],
        extra_anchors: list[tuple[int, int]],
    ) -> None:
        """Replace each selection (or collapsed cursor) with the typed character."""
        from textual.widgets.text_area import Selection

        key = event.key
        char = event.character

        if char is not None and char.isprintable():
            replacement = char
        elif key == "enter":
            replacement = "\n"
        elif key in ("backspace", "delete"):
            replacement = ""
        else:
            self.clear_extra_cursors()
            return

        text = self.text
        lines = text.split("\n")
        offsets = _build_offsets(lines)

        def to_off(row: int, col: int) -> int:
            return offsets[row] + col

        all_cursors_and_anchors = [(primary_anchor, primary)] + list(
            zip(extra_anchors, extra, strict=True)
        )

        ops: list[list[int]] = []
        for anchor, cursor in all_cursors_and_anchors:
            a_off = to_off(*anchor)
            c_off = to_off(*cursor)
            start_off = min(a_off, c_off)
            end_off = max(a_off, c_off)
            # For collapsed cursors, adjust for backspace/delete
            if start_off == end_off:
                if key == "backspace" and start_off > 0:
                    start_off -= 1
                elif key == "delete" and end_off < len(text):
                    end_off += 1
            ops.append([start_off, end_off])

        # Track primary's start offset before sorting
        p_a_off = to_off(*primary_anchor)
        p_c_off = to_off(*primary)
        primary_start = min(p_a_off, p_c_off)
        if primary_anchor == primary and key == "backspace" and primary_start > 0:
            primary_start -= 1

        # Sort and deduplicate overlapping ranges
        ops.sort()
        deduped: list[list[int]] = []
        for op in ops:
            if deduped and op[0] < deduped[-1][1]:
                deduped[-1][1] = max(deduped[-1][1], op[1])
            else:
                deduped.append(list(op))

        # Build new text + track new cursor offsets
        parts: list[str] = []
        prev = 0
        new_cursor_offsets: list[int] = []
        accumulated = 0
        repl_len = len(replacement)
        for s, e in deduped:
            parts.append(text[prev:s])
            new_cursor_offsets.append(accumulated + (s - prev) + repl_len)
            accumulated += (s - prev) + repl_len
            parts.append(replacement)
            prev = e
        parts.append(text[prev:])
        new_text = "".join(parts)

        self.replace(new_text, self.document.start, self.document.end)

        new_lines = new_text.split("\n")
        new_offsets = _build_offsets(new_lines)
        new_locs = [
            _offset_to_loc(off, new_lines, new_offsets) for off in new_cursor_offsets
        ]

        if not new_locs:
            return

        # Find which deduped range corresponds to primary
        primary_idx = 0
        for i, (s, e) in enumerate(deduped):
            if s <= primary_start <= e:
                primary_idx = i
                break

        new_primary = (
            new_locs[primary_idx] if primary_idx < len(new_locs) else new_locs[0]
        )
        self.selection = Selection(new_primary, new_primary)
        self._extra_cursors = [
            loc for i, loc in enumerate(new_locs) if i != primary_idx
        ]
        self._extra_anchors = list(self._extra_cursors)
        self._extra_last_x_offsets = [0] * len(self._extra_cursors)
        self._recompute_selection_ranges()
        self._line_cache.clear()
        self.refresh()

    # ── per-operation helpers ─────────────────────────────────────────────────

    def _do_enter(
        self,
        all_cursors: list[tuple[int, int]],
        primary: tuple[int, int],
        extra: list[tuple[int, int]],
    ) -> None:
        """Insert a newline at every cursor position."""
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
        self._extra_anchors = list(self._extra_cursors)
        self._extra_last_x_offsets = [0] * len(self._extra_cursors)
        self._recompute_selection_ranges()
        self.refresh()

    def _do_backspace_line_merge(
        self,
        all_cursors: list[tuple[int, int]],
        primary: tuple[int, int],
        extra: list[tuple[int, int]],
    ) -> None:
        """Merge each cursor's line with the line above (backspace at col 0)."""
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
        self._extra_anchors = list(self._extra_cursors)
        self._extra_last_x_offsets = [0] * len(self._extra_cursors)
        self._recompute_selection_ranges()
        self.refresh()

    def _do_delete_line_merge(
        self,
        all_cursors: list[tuple[int, int]],
        primary: tuple[int, int],
        extra: list[tuple[int, int]],
    ) -> None:
        """Merge each cursor's line with the line below (delete at EOL)."""
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
        self._extra_anchors = list(self._extra_cursors)
        self._extra_last_x_offsets = [0] * len(self._extra_cursors)
        self._recompute_selection_ranges()
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
        self._extra_anchors = list(self._extra_cursors)
        self._extra_last_x_offsets = [0] * len(self._extra_cursors)
        self._recompute_selection_ranges()
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
        self._extra_anchors = list(self._extra_cursors)
        self._extra_last_x_offsets = [0] * len(self._extra_cursors)
        self._recompute_selection_ranges()
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
        self._extra_anchors = list(self._extra_cursors)
        self._extra_last_x_offsets = [0] * len(self._extra_cursors)
        self._recompute_selection_ranges()
        self.refresh()

    # ── position maths ────────────────────────────────────────────────────────

    @staticmethod
    def _new_positions(
        all_cursors: list[tuple[int, int]],
        op: str,
    ) -> dict[tuple[int, int], tuple[int, int]]:
        """Compute the new (row, col) for every cursor after *op*."""
        result: dict[tuple[int, int], tuple[int, int]] = {}
        for row, col in all_cursors:
            num_smaller = sum(1 for r, c in all_cursors if r == row and c < col)
            if op == "insert":
                new_col = col + 1 + num_smaller
            elif op == "backspace":
                new_col = col - 1 - num_smaller
            elif op == "delete":
                new_col = col - num_smaller
            else:
                new_col = col
            result[(row, col)] = (row, new_col)
        return result
