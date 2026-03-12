from textual import events
from textual.widget import Widget

SPLIT_MIN_SIZE = 10  # matches _parse_split_resize's hardcoded minimum


class SplitResizeHandle(Widget):
    """Drag handle between split_left and split_right for resizing."""

    def __init__(self) -> None:
        super().__init__()
        self._dragging = False

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
        """Resize split_left to the given screen position (clamped to min/max)."""
        container = self.app.query_one("#split_container")
        is_vertical = "split-vertical" in container.classes
        split_left = self.app.query_one("#split_left")

        if is_vertical:
            new_size = screen_y - container.region.y
            max_size = container.size.height - SPLIT_MIN_SIZE
        else:
            new_size = screen_x - container.region.x
            max_size = container.size.width - SPLIT_MIN_SIZE

        clamped = max(SPLIT_MIN_SIZE, min(max_size, new_size))

        if is_vertical:
            split_left.styles.height = clamped
        else:
            split_left.styles.width = clamped
