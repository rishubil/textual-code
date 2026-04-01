"""Tests for binary file detection when opening files."""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.widgets.code_editor import CodeEditor

# ── Unit: is_binary_file ─────────────────────────────────────────────────────


def test_is_binary_file_null_byte(tmp_path: Path):
    """Files with null bytes are binary."""
    from textual_code.utils import is_binary_file

    path = tmp_path / "test_binary.bin"
    path.write_bytes(b"hello\x00world")
    assert is_binary_file(path) is True


def test_is_binary_file_text(tmp_path: Path):
    """Plain text files are not binary."""
    from textual_code.utils import is_binary_file

    path = tmp_path / "test_text.txt"
    path.write_bytes(b"hello world\n")
    assert is_binary_file(path) is False


def test_is_binary_file_empty(tmp_path: Path):
    """Empty files are not binary."""
    from textual_code.utils import is_binary_file

    path = tmp_path / "test_empty.txt"
    path.write_bytes(b"")
    assert is_binary_file(path) is False


def test_is_binary_file_missing_returns_false(tmp_path: Path):
    """Missing files return False (no error)."""
    from textual_code.utils import is_binary_file

    assert is_binary_file(tmp_path / "nonexistent_xyz_abc.bin") is False


# ── Integration: open binary file → binary notice tab ────────────────────────


@pytest.fixture
def binary_file(workspace: Path) -> Path:
    f = workspace / "image.bin"
    f.write_bytes(b"PNG\x00\x01\x02\x03" + b"A" * 100)
    return f


@pytest.fixture
def empty_file(workspace: Path) -> Path:
    f = workspace / "empty.txt"
    f.write_bytes(b"")
    return f


async def test_binary_file_shows_notice(workspace: Path, binary_file: Path):
    """Opening a binary file shows a binary notice Static, not CodeEditor."""
    app = make_app(workspace, open_file=binary_file, light=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.wait_for_scheduled_animations()
        main_view = app.main_view
        pane_ids = list(main_view.opened_pane_ids)
        assert len(pane_ids) == 1

        tc = main_view.tabbed_content
        pane = tc.get_pane(pane_ids[0])

        # Should have a binary-notice Static, not a CodeEditor
        assert len(pane.query(".binary-notice")) == 1
        assert len(pane.query(CodeEditor)) == 0


async def test_binary_file_open_twice_single_tab(workspace: Path, binary_file: Path):
    """Opening the same binary file twice creates only one tab."""
    app = make_app(workspace, light=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.wait_for_scheduled_animations()
        main_view = app.main_view

        await main_view.open_code_editor_pane(binary_file)
        await pilot.wait_for_scheduled_animations()
        count_after_first = len(main_view.opened_pane_ids)

        await main_view.open_code_editor_pane(binary_file)
        await pilot.wait_for_scheduled_animations()
        count_after_second = len(main_view.opened_pane_ids)

        assert count_after_first == count_after_second


async def test_empty_file_opens_as_editor(workspace: Path, empty_file: Path):
    """An empty file (0 bytes) opens as a normal CodeEditor, not binary notice."""
    app = make_app(workspace, open_file=empty_file, light=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.wait_for_scheduled_animations()
        main_view = app.main_view
        pane_ids = list(main_view.opened_pane_ids)
        assert len(pane_ids) == 1

        tc = main_view.tabbed_content
        pane = tc.get_pane(pane_ids[0])

        # Should have a CodeEditor, not a binary notice
        assert len(pane.query(CodeEditor)) == 1
        assert len(pane.query(".binary-notice")) == 0
