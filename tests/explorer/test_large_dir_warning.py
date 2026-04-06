"""
Tests for large directory operation warning modal.

Verifies that a confirmation modal is shown before copying, deleting,
or moving directories that exceed the configured size threshold.
"""

import stat
import sys
from pathlib import Path

import pytest

from tests.conftest import await_workers, make_app, wait_for_condition
from textual_code.app import TextualCode
from textual_code.modals import DeleteFileModalScreen
from textual_code.modals.file_ops import LargeDirWarningModalScreen
from textual_code.widgets.explorer import Explorer

# ── Helpers ────────────────────────────────────────────────────────────


def _make_dir_with_size(workspace: Path, name: str, file_size: int, count: int) -> Path:
    """Create a directory with *count* files each of *file_size* bytes."""
    d = workspace / name
    d.mkdir()
    for i in range(count):
        (d / f"file{i}.dat").write_bytes(b"x" * file_size)
    return d


# ── Unit tests for _calc_dir_size ─────────────────────────────────────


def test_calc_dir_size_basic(tmp_path: Path):
    """Returned (total, count) matches known directory contents."""
    d = _make_dir_with_size(tmp_path, "data", file_size=100, count=5)
    total, count = TextualCode._calc_dir_size(d)
    assert total == 500
    assert count == 5


def test_calc_dir_size_nested(tmp_path: Path):
    """Nested subdirectories are included in the calculation."""
    d = tmp_path / "root"
    d.mkdir()
    (d / "a.txt").write_bytes(b"x" * 50)
    sub = d / "sub"
    sub.mkdir()
    (sub / "b.txt").write_bytes(b"x" * 75)
    total, count = TextualCode._calc_dir_size(d)
    assert total == 125
    assert count == 2


def test_calc_dir_size_early_exit(tmp_path: Path):
    """Early exit when total exceeds threshold."""
    d = _make_dir_with_size(tmp_path, "big", file_size=200, count=10)
    # Total would be 2000 bytes; threshold is 500
    total, count = TextualCode._calc_dir_size(d, threshold=500)
    assert total >= 500
    assert count >= 1


def test_calc_dir_size_followlinks_false(tmp_path: Path):
    """Symlink cycles do not cause infinite loop."""
    d = tmp_path / "linkdir"
    d.mkdir()
    (d / "file.txt").write_bytes(b"x" * 10)
    # Create a symlink cycle: linkdir/loop -> linkdir
    loop = d / "loop"
    loop.symlink_to(d)
    total, count = TextualCode._calc_dir_size(d)
    assert total == 10
    assert count == 1


@pytest.mark.skipif(sys.platform == "win32", reason="chmod not reliable on Windows")
def test_calc_dir_size_permission_error(tmp_path: Path):
    """Inaccessible subdirectories are skipped without error."""
    d = tmp_path / "mixed"
    d.mkdir()
    (d / "ok.txt").write_bytes(b"x" * 50)
    restricted = d / "noaccess"
    restricted.mkdir()
    (restricted / "secret.txt").write_bytes(b"x" * 100)
    # Remove read+execute permission on the subdirectory
    restricted.chmod(0o000)
    try:
        total, count = TextualCode._calc_dir_size(d)
        # Should at least count the accessible file
        assert total >= 50
        assert count >= 1
    finally:
        # Restore permissions for cleanup
        restricted.chmod(stat.S_IRWXU)


def test_calc_dir_size_empty(tmp_path: Path):
    """Empty directory returns (0, 0)."""
    d = tmp_path / "empty"
    d.mkdir()
    total, count = TextualCode._calc_dir_size(d)
    assert total == 0
    assert count == 0


def test_calc_dir_size_threshold_zero_scans_all(tmp_path: Path):
    """Threshold of 0 scans the full directory."""
    d = _make_dir_with_size(tmp_path, "full", file_size=100, count=10)
    total, count = TextualCode._calc_dir_size(d, threshold=0)
    assert total == 1000
    assert count == 10


# ── Integration tests: delete ─────────────────────────────────────────


async def test_large_dir_warning_shown_on_delete(workspace: Path):
    """Warning modal appears when deleting a directory over threshold."""
    bigdir = _make_dir_with_size(workspace, "bigdir", file_size=200, count=5)

    app = make_app(workspace)
    app.default_large_dir_threshold = 100  # Low threshold for testing
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer

        # Trigger delete
        explorer.post_message(
            Explorer.FileDeleteRequested(explorer=explorer, path=bigdir)
        )
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, DeleteFileModalScreen)

        # Confirm delete
        await pilot.click("#delete")
        await wait_for_condition(
            pilot, lambda: isinstance(app.screen, LargeDirWarningModalScreen)
        )
        await await_workers(pilot)

        # Confirm the warning
        await pilot.click("#continue")
        await wait_for_condition(pilot, lambda: not bigdir.exists())

    assert not bigdir.exists()


async def test_small_dir_no_warning_on_delete(workspace: Path):
    """Small directory delete skips the warning modal."""
    smalldir = _make_dir_with_size(workspace, "smalldir", file_size=10, count=2)

    app = make_app(workspace)
    app.default_large_dir_threshold = 100_000  # High threshold
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer

        explorer.post_message(
            Explorer.FileDeleteRequested(explorer=explorer, path=smalldir)
        )
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.click("#delete")
        await wait_for_condition(pilot, lambda: not smalldir.exists())
        await await_workers(pilot)

    assert not smalldir.exists()


async def test_large_dir_warning_cancel_aborts_delete(workspace: Path):
    """Cancelling the warning modal keeps the directory intact."""
    bigdir = _make_dir_with_size(workspace, "bigdir", file_size=200, count=5)

    app = make_app(workspace)
    app.default_large_dir_threshold = 100
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer

        explorer.post_message(
            Explorer.FileDeleteRequested(explorer=explorer, path=bigdir)
        )
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.click("#delete")
        await wait_for_condition(
            pilot, lambda: isinstance(app.screen, LargeDirWarningModalScreen)
        )
        await await_workers(pilot)

        # Cancel the warning
        await pilot.click("#cancel")
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

    assert bigdir.exists()


async def test_threshold_zero_disables_warning(workspace: Path):
    """Threshold of 0 disables the warning entirely."""
    bigdir = _make_dir_with_size(workspace, "bigdir", file_size=200, count=5)

    app = make_app(workspace)
    app.default_large_dir_threshold = 0
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer

        explorer.post_message(
            Explorer.FileDeleteRequested(explorer=explorer, path=bigdir)
        )
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.click("#delete")
        await wait_for_condition(pilot, lambda: not bigdir.exists())
        await await_workers(pilot)

    assert not bigdir.exists()


# ── Integration tests: move ───────────────────────────────────────────


async def test_large_dir_warning_shown_on_move(workspace: Path):
    """Warning modal appears when moving a directory over threshold."""
    src = _make_dir_with_size(workspace, "source", file_size=200, count=5)
    dest_dir = workspace / "dest"
    dest_dir.mkdir()

    app = make_app(workspace)
    app.default_large_dir_threshold = 100
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()

        app.post_message(
            TextualCode.MoveDestinationSelected(
                source_path=src, destination_dir=dest_dir
            )
        )
        await wait_for_condition(
            pilot, lambda: isinstance(app.screen, LargeDirWarningModalScreen)
        )
        await await_workers(pilot)

        # Confirm
        await pilot.click("#continue")
        await wait_for_condition(pilot, lambda: (dest_dir / "source").exists())

    assert (dest_dir / "source").exists()
    assert not src.exists()


# ── Integration tests: copy-paste ─────────────────────────────────────


async def test_large_dir_warning_shown_on_copy_paste(workspace: Path):
    """Warning modal appears when copy-pasting a directory over threshold."""
    src = _make_dir_with_size(workspace, "original", file_size=200, count=5)
    target_dir = workspace / "target"
    target_dir.mkdir()

    app = make_app(workspace)
    app.default_large_dir_threshold = 100
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer

        # Copy
        explorer.post_message(Explorer.FileCopyRequested(explorer=explorer, path=src))
        await pilot.wait_for_scheduled_animations()

        # Paste
        explorer.post_message(
            Explorer.FilePasteRequested(explorer=explorer, target_dir=target_dir)
        )
        await wait_for_condition(
            pilot, lambda: isinstance(app.screen, LargeDirWarningModalScreen)
        )
        await await_workers(pilot)

        # Confirm
        await pilot.click("#continue")
        await wait_for_condition(pilot, lambda: (target_dir / "original").exists())

    assert (target_dir / "original").exists()
    assert src.exists()  # Source preserved (copy)


async def test_large_dir_warning_shown_on_cut_paste(workspace: Path):
    """Warning modal appears when cut-pasting a directory over threshold.

    Clipboard should not be cleared until after confirmation.
    """
    src = _make_dir_with_size(workspace, "cutdir", file_size=200, count=5)
    target_dir = workspace / "target"
    target_dir.mkdir()

    app = make_app(workspace)
    app.default_large_dir_threshold = 100
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer

        # Cut
        explorer.post_message(Explorer.FileCutRequested(explorer=explorer, path=src))
        await pilot.wait_for_scheduled_animations()

        # Paste
        explorer.post_message(
            Explorer.FilePasteRequested(explorer=explorer, target_dir=target_dir)
        )
        await wait_for_condition(
            pilot, lambda: isinstance(app.screen, LargeDirWarningModalScreen)
        )
        await await_workers(pilot)

        # Clipboard should NOT be cleared yet (modal still showing)
        assert app._file_clipboard is not None

        # Confirm
        await pilot.click("#continue")
        await wait_for_condition(pilot, lambda: (target_dir / "cutdir").exists())

    assert (target_dir / "cutdir").exists()
    assert not src.exists()


# ── Edge case: directory removed before size calc ─────────────────────


async def test_dir_removed_during_size_calc(workspace: Path):
    """Graceful handling when directory disappears before size check."""
    ghost = workspace / "ghost"
    ghost.mkdir()
    (ghost / "file.txt").write_bytes(b"x" * 200)

    app = make_app(workspace)
    app.default_large_dir_threshold = 100
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer

        explorer.post_message(
            Explorer.FileDeleteRequested(explorer=explorer, path=ghost)
        )
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, DeleteFileModalScreen)

        # Remove the directory before confirming delete
        import shutil

        shutil.rmtree(ghost)

        await pilot.click("#delete")
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await await_workers(pilot)

    # Should not crash — directory was already gone
    assert not ghost.exists()
