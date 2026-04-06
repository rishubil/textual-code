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

log = logging.getLogger(__name__)

IMAGE_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif"}
)

MAX_IMAGE_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

_RESIZE_DEBOUNCE = 0.15  # seconds


def render_image_sync(source_path: Path, max_w: int, max_h: int) -> RenderableType:
    """Load an image and render it to rich-pixels in a subprocess.

    This is a module-level function so it can be pickled for
    ``run_cancellable()``.
    """
    from PIL import Image
    from rich_pixels import Pixels

    with Image.open(source_path) as img:
        orig_w, orig_h = img.size
        target_w, target_h = compute_resize(orig_w, orig_h, max_w, max_h)
        return Pixels.from_image(img, resize=(target_w, target_h))


def compute_resize(orig_w: int, orig_h: int, max_w: int, max_h: int) -> tuple[int, int]:
    """Compute target (width, height) that fits within *max_w*×*max_h*.

    The image is never enlarged beyond its original pixel size (no upscale).
    Aspect ratio is always preserved.
    """
    if orig_w <= 0 or orig_h <= 0 or max_w <= 0 or max_h <= 0:
        return (1, 1)

    scale = min(max_w / orig_w, max_h / orig_h, 1.0)
    return (max(int(orig_w * scale), 1), max(int(orig_h * scale), 1))


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
