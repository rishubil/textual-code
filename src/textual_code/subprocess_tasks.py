"""Lightweight functions designed to run in subprocesses.

Every function in this module is a target for :func:`run_cancellable`.
The module intentionally avoids importing heavyweight dependencies
(Textual, Rich, etc.) so that ``multiprocessing.spawn`` on Windows can
import it quickly without pulling in the entire widget tree.

Heavy dependencies (PIL, rich-pixels) are imported lazily inside
the functions that need them.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import RenderableType

log = logging.getLogger(__name__)


# ── Directory size calculation ───────────────────────────────────────────────


def calc_dir_size(path: Path, threshold: int = 0) -> tuple[int, int]:
    """Calculate total size and file count for a directory.

    Args:
        path: Directory to scan.
        threshold: When > 0, stop scanning once total exceeds this value.

    Returns:
        (total_bytes, file_count) tuple.
    """
    total = 0
    count = 0
    for dirpath, _dirnames, filenames in os.walk(
        path, followlinks=False, onerror=lambda _e: None
    ):
        for fname in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, fname))
            except OSError:
                continue
            count += 1
            if threshold > 0 and total > threshold:
                return total, count
    return total, count


# ── Directory scanning ───────────────────────────────────────────────────────


def scan_directory_sync(
    path: Path, show_hidden_files: bool
) -> tuple[list[Path], dict[Path, bool]]:
    """Scan a directory with os.scandir and return sorted paths + is_dir cache.

    Args:
        path: The directory to scan. Will be resolved to an absolute path.
        show_hidden_files: If False, entries starting with '.' are excluded.

    Returns:
        A tuple of (sorted_paths, is_dir_cache).
    """
    path = path.resolve()
    entries: list[Path] = []
    is_dir_cache: dict[Path, bool] = {}
    try:
        with os.scandir(path) as it:
            for entry in it:
                entry_path = Path(entry.path)
                try:
                    is_dir = entry.is_dir(follow_symlinks=True)
                except OSError:
                    is_dir = False
                is_dir_cache[entry_path] = is_dir
                entries.append(entry_path)
    except OSError:
        pass
    if not show_hidden_files:
        entries = [p for p in entries if not p.name.startswith(".")]
    entries.sort(key=lambda p: (not is_dir_cache.get(p, False), p.name.lower()))
    return entries, is_dir_cache


# ── Image rendering ─────────────────────────────────────────────────────────


def compute_resize(orig_w: int, orig_h: int, max_w: int, max_h: int) -> tuple[int, int]:
    """Compute target (width, height) that fits within *max_w*×*max_h*.

    The image is never enlarged beyond its original pixel size (no upscale).
    Aspect ratio is always preserved.
    """
    if orig_w <= 0 or orig_h <= 0 or max_w <= 0 or max_h <= 0:
        return (1, 1)

    scale = min(max_w / orig_w, max_h / orig_h, 1.0)
    return (max(int(orig_w * scale), 1), max(int(orig_h * scale), 1))


def render_image_sync(source_path: Path, max_w: int, max_h: int) -> RenderableType:
    """Load an image and render it to rich-pixels.

    PIL and rich_pixels are imported lazily to keep this module
    lightweight for subprocess startup.

    Returns a ``Pixels`` renderable (duck-typed as ``object`` to avoid
    importing rich_pixels at module level).
    """
    from PIL import Image
    from rich_pixels import Pixels

    with Image.open(source_path) as img:
        orig_w, orig_h = img.size
        target_w, target_h = compute_resize(orig_w, orig_h, max_w, max_h)
        return Pixels.from_image(img, resize=(target_w, target_h))
