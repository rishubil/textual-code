"""Tests for image file preview feature (Issue #12)."""

from pathlib import Path

import pytest
from textual.widgets import Static

from tests.conftest import make_app, make_png, wait_for_condition
from textual_code.widgets.code_editor import CodeEditor

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def image_file(workspace: Path) -> Path:
    return make_png(workspace / "test.png")


@pytest.fixture
def uppercase_image_file(workspace: Path) -> Path:
    return make_png(workspace / "TEST.PNG")


# ── Unit: IMAGE_EXTENSIONS ───────────────────────────────────────────────────


def test_image_extensions_recognized():
    """IMAGE_EXTENSIONS contains all expected image formats."""
    from textual_code.widgets.image_preview import IMAGE_EXTENSIONS

    for ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif"):
        assert ext in IMAGE_EXTENSIONS, f"{ext} missing from IMAGE_EXTENSIONS"


# ── Unit: _compute_resize ────────────────────────────────────────────────────


def test_compute_resize_no_upscale():
    """Small images are NOT enlarged beyond 1:1 pixel size."""
    from textual_code.widgets.image_preview import compute_resize

    # 10x10 image in 80x80 pane → stays 10x10
    w, h = compute_resize(orig_w=10, orig_h=10, max_w=80, max_h=80)
    assert w == 10
    assert h == 10


def test_compute_resize_downscale():
    """Large images are downscaled to fit the pane."""
    from textual_code.widgets.image_preview import compute_resize

    # 200x200 image in 40x40 pane → scaled to 40x40
    w, h = compute_resize(orig_w=200, orig_h=200, max_w=40, max_h=40)
    assert w == 40
    assert h == 40


def test_compute_resize_aspect_ratio():
    """Aspect ratio is preserved when downscaling."""
    from textual_code.widgets.image_preview import compute_resize

    # 200x100 image in 40x40 pane → limited by width: 40x20
    w, h = compute_resize(orig_w=200, orig_h=100, max_w=40, max_h=40)
    assert w == 40
    assert h == 20


def test_compute_resize_tall_image():
    """Tall images are limited by max height."""
    from textual_code.widgets.image_preview import compute_resize

    # 100x400 image in 80x80 pane → limited by height: 20x80
    w, h = compute_resize(orig_w=100, orig_h=400, max_w=80, max_h=80)
    assert w == 20
    assert h == 80


# ── Integration: image file opens ImagePreviewPane ───────────────────────────


async def test_image_file_shows_preview(workspace: Path, image_file: Path):
    """Opening an image file shows ImagePreviewPane, not binary notice."""
    from textual_code.widgets.image_preview import ImagePreviewPane

    app = make_app(workspace, open_file=image_file, light=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.wait_for_scheduled_animations()
        main_view = app.main_view
        pane_ids = list(main_view.opened_pane_ids)
        assert len(pane_ids) == 1

        tc = main_view.tabbed_content
        pane = tc.get_pane(pane_ids[0])

        assert len(pane.query(ImagePreviewPane)) == 1
        assert len(pane.query(".binary-notice")) == 0
        assert len(pane.query(CodeEditor)) == 0


async def test_image_file_open_twice_single_tab(workspace: Path, image_file: Path):
    """Opening the same image file twice creates only one tab."""
    app = make_app(workspace, light=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.wait_for_scheduled_animations()
        main_view = app.main_view

        await main_view.open_code_editor_pane(image_file)
        await pilot.wait_for_scheduled_animations()
        count_after_first = len(main_view.opened_pane_ids)

        await main_view.open_code_editor_pane(image_file)
        await pilot.wait_for_scheduled_animations()
        count_after_second = len(main_view.opened_pane_ids)

        assert count_after_first == count_after_second


async def test_uppercase_extension_recognized(
    workspace: Path, uppercase_image_file: Path
):
    """Uppercase extensions like .PNG are recognized as images."""
    from textual_code.widgets.image_preview import ImagePreviewPane

    app = make_app(workspace, open_file=uppercase_image_file, light=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.wait_for_scheduled_animations()
        main_view = app.main_view
        pane_ids = list(main_view.opened_pane_ids)
        tc = main_view.tabbed_content
        pane = tc.get_pane(pane_ids[0])
        assert len(pane.query(ImagePreviewPane)) == 1


# ── Integration: corrupt image fallback ──────────────────────────────────────


async def test_corrupt_image_shows_fallback(workspace: Path):
    """An image extension with non-image content shows error fallback."""
    from textual_code.widgets.image_preview import ImagePreviewPane

    bad = workspace / "bad.png"
    bad.write_bytes(b"this is not a PNG file at all")
    app = make_app(workspace, open_file=bad, light=True)
    async with app.run_test(size=(80, 24)) as pilot:
        preview = app.query_one(ImagePreviewPane)
        # Windows: wait for worker to load and fail
        await wait_for_condition(
            pilot,
            lambda: (
                "Could not load image"
                in str(preview.query_one("#image-content", Static).content)
            ),
            msg="Corrupt image fallback message not shown",
        )


# ── Integration: non-image binary still shows binary notice ──────────────────


async def test_non_image_binary_still_shows_notice(workspace: Path):
    """Non-image binary files still get the binary notice, not image preview."""
    f = workspace / "data.bin"
    f.write_bytes(b"\x00\x01\x02\x03" * 100)
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.wait_for_scheduled_animations()
        main_view = app.main_view
        pane_ids = list(main_view.opened_pane_ids)
        tc = main_view.tabbed_content
        pane = tc.get_pane(pane_ids[0])
        assert len(pane.query(".binary-notice")) == 1


# ── Integration: large image shows "too large" notice ────────────────────────


async def test_large_image_shows_too_large_notice(workspace: Path, monkeypatch):
    """Images exceeding MAX_IMAGE_FILE_SIZE show a 'too large' notice."""
    import textual_code.widgets.image_preview as img_mod
    import textual_code.widgets.main_view as mv_mod

    # Patch MAX to a tiny value so a normal PNG triggers it
    monkeypatch.setattr(img_mod, "MAX_IMAGE_FILE_SIZE", 10)
    monkeypatch.setattr(mv_mod, "MAX_IMAGE_FILE_SIZE", 10)

    png = make_png(workspace / "big.png")
    app = make_app(workspace, open_file=png, light=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.wait_for_scheduled_animations()
        main_view = app.main_view
        pane_ids = list(main_view.opened_pane_ids)
        tc = main_view.tabbed_content
        pane = tc.get_pane(pane_ids[0])
        assert len(pane.query(".binary-notice")) == 1
