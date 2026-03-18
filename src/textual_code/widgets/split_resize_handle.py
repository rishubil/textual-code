from __future__ import annotations

from rich.align import Align
from rich.rule import Rule
from rich.text import Text
from textual import events
from textual.widget import Widget

SPLIT_MIN_SIZE = 10  # matches _parse_split_resize's hardcoded minimum


class SplitResizeHandle(Widget):
    """Drag handle between split panels for resizing.

    When used inside a SplitContainer, child_index indicates which pair of
    children this handle separates (children[child_index] and
    children[child_index+1]).
    """

    def __init__(self, child_index: int = 0) -> None:
        super().__init__()
        self._dragging = False
        self._child_index = child_index

    @property
    def child_index(self) -> int:
        return self._child_index

    def _is_vertical(self) -> bool:
        """Return True if the parent container uses vertical layout."""
        from textual_code.widgets.split_container import SplitContainer

        if isinstance(self.parent, SplitContainer):
            return self.parent.direction == "vertical"
        # Legacy: check parent classes
        try:
            return self.parent is not None and "split-vertical" in self.parent.classes
        except Exception:
            return False

    def render(self):
        if self._is_vertical():
            return Rule(style="dim")
        return Align.center(Text("│", style="dim"), vertical="middle")

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self._dragging = True
        self.capture_mouse()
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._dragging:
            self.resize_split_to(event.screen_x, event.screen_y)

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._dragging:
            self._dragging = False
            self.release_mouse()

    def resize_split_to(self, screen_x: int, screen_y: int) -> None:
        """Resize the child at child_index to the given screen position."""
        self._resize_in_split_container(screen_x, screen_y)

    def _resize_in_split_container(self, screen_x: int, screen_y: int) -> None:
        """Resize within a SplitContainer (new system)."""
        from textual_code.widgets.split_container import SplitContainer

        container = self.parent
        assert isinstance(container, SplitContainer)

        # Get the non-handle children in order
        non_handle_children = [
            c for c in container.children if not isinstance(c, SplitResizeHandle)
        ]
        if self._child_index + 1 >= len(non_handle_children):
            return

        left_child = non_handle_children[self._child_index]
        is_vertical = container.direction == "vertical"

        if is_vertical:
            new_size = screen_y - container.region.y
            max_size = container.size.height - SPLIT_MIN_SIZE
        else:
            new_size = screen_x - container.region.x
            max_size = container.size.width - SPLIT_MIN_SIZE

        # Account for preceding children's size
        for i in range(self._child_index):
            child = non_handle_children[i]
            if is_vertical:
                new_size -= child.size.height
            else:
                new_size -= child.size.width
        # Account for handles
        handle_count = self._child_index  # handles before this one
        if not is_vertical:
            new_size -= handle_count  # each handle is 1 cell wide
        else:
            new_size -= handle_count  # each handle is 1 cell tall

        clamped = max(SPLIT_MIN_SIZE, min(max_size, new_size))

        if is_vertical:
            left_child.styles.height = clamped
        else:
            left_child.styles.width = clamped
