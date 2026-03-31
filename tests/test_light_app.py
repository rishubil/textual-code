"""Tests for the lightweight app mode (skip_sidebar=True)."""

from pathlib import Path

from tests.conftest import make_app


async def test_light_app_mounts_without_sidebar(workspace: Path, sample_py_file: Path):
    """Light app should mount successfully without a Sidebar widget."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.query("Sidebar")) == 0
        assert app.sidebar is None


async def test_light_app_opens_file(workspace: Path, sample_py_file: Path):
    """Light app should open a file and allow basic editing."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.text == "print('hello')\n"


async def test_light_app_basic_edit(workspace: Path, sample_py_file: Path):
    """Light app should allow typing in the editor."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        await pilot.press("a")
        await pilot.pause()
        assert "a" in editor.text


async def test_light_app_save(workspace: Path, sample_py_file: Path):
    """Light app should save files without crashing (no explorer reload)."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        await pilot.press("a")
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()
        # File should be saved without crash
        assert sample_py_file.read_text(encoding="utf-8").startswith("a")


async def test_full_app_still_has_sidebar(workspace: Path, sample_py_file: Path):
    """Default make_app (light=False) should still have Sidebar."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.query("Sidebar")) == 1
        assert app.sidebar is not None
