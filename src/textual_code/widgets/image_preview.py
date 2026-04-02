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
from textual.worker import get_current_worker

log = logging.getLogger(__name__)

IMAGE_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif"}
)

MAX_IMAGE_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

_RESIZE_DEBOUNCE = 0.15  # seconds


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

    @work(thread=True, exclusive=True)
    def _render_image(self) -> None:
        """Load and render the image in a background thread."""
        from PIL import Image, UnidentifiedImageError
        from rich_pixels import Pixels

        worker = get_current_worker()

        self.app.call_from_thread(self._show_loading, True)

        try:
            log.debug("Loading image: %s", self.source_path)
            with Image.open(self.source_path) as img:
                orig_w, orig_h = img.size

                # width - 4 for border, (height - 4) * 2 for half-cell renderer
                max_w = max(self.size.width - 4, 1)
                max_h = max((self.size.height - 4) * 2, 1)
                target_w, target_h = compute_resize(orig_w, orig_h, max_w, max_h)

                if worker.is_cancelled:
                    return

                pixels = Pixels.from_image(img, resize=(target_w, target_h))

            if worker.is_cancelled:
                return

            log.debug(
                "Image rendered: %s (%dx%d -> %dx%d)",
                self.source_path,
                orig_w,
                orig_h,
                target_w,
                target_h,
            )
            try:
                self.app.call_from_thread(self._update_content, pixels)
            except RuntimeError as exc:
                if "loop" not in str(exc).lower() and "closed" not in str(exc).lower():
                    raise
                log.debug("call_from_thread suppressed (app exiting): %s", exc)

        except (OSError, ValueError, UnidentifiedImageError) as exc:
            log.warning("Could not load image %s: %s", self.source_path, exc)
            if not worker.is_cancelled:
                try:
                    self.app.call_from_thread(
                        self._update_content, "\u26a0  Could not load image"
                    )
                except RuntimeError as rt_exc:
                    if (
                        "loop" not in str(rt_exc).lower()
                        and "closed" not in str(rt_exc).lower()
                    ):
                        raise
                    log.debug("call_from_thread suppressed (app exiting): %s", rt_exc)

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
