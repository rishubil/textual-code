"""Image preview pane using rich-pixels."""

from __future__ import annotations

import logging
from pathlib import Path

from rich.console import RenderableType
from textual import events, work
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.css.query import NoMatches
from textual.timer import Timer
from textual.widgets import LoadingIndicator, Static

from textual_code.cancellable_worker import run_cancellable
from textual_code.subprocess_tasks import compute_resize as compute_resize
from textual_code.subprocess_tasks import render_image_sync

log = logging.getLogger(__name__)

IMAGE_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif"}
)

MAX_IMAGE_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

_RESIZE_DEBOUNCE = 0.15  # seconds


class ImagePreviewPane(VerticalScroll):
    """Displays an image file preview using rich-pixels half-cell rendering."""

    DEFAULT_CSS = """
    ImagePreviewPane {
        height: 1fr;
        border: tall transparent;
    }
    ImagePreviewPane:focus {
        border: tall $accent;
    }
    """

    def __init__(self, source_path: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self.source_path = source_path
        self._resize_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Static(id="image-content")
        yield LoadingIndicator()

    def on_resize(self, event: events.Resize) -> None:
        if self._resize_timer is not None:
            self._resize_timer.stop()
        self._resize_timer = self.set_timer(_RESIZE_DEBOUNCE, self._render_image)

    def on_unmount(self) -> None:
        if self._resize_timer is not None:
            self._resize_timer.stop()
            self._resize_timer = None

    @work(exclusive=True)
    async def _render_image(self) -> None:
        """Load and render the image in a subprocess."""
        self._show_loading(True)

        try:
            pixels = await run_cancellable(
                render_image_sync,
                self.source_path,
                max(self.size.width - 4, 1),
                max((self.size.height - 4) * 2, 1),
            )
            self._update_content(pixels)
        except TimeoutError:
            return
        except (OSError, ValueError) as exc:
            log.warning("Could not load image %s: %s", self.source_path, exc)
            self._update_content("\u26a0  Could not load image")

    def _show_loading(self, show: bool) -> None:
        """Toggle loading indicator and image content visibility."""
        try:
            static = self.query_one("#image-content", Static)
            loader = self.query_one(LoadingIndicator)
        except NoMatches:
            return
        static.display = not show
        loader.display = show

    def _update_content(self, content: RenderableType) -> None:
        """Update the static widget with rendered pixels or error message."""
        try:
            static = self.query_one("#image-content", Static)
        except NoMatches:
            return
        static.update(content)
        self._show_loading(False)
