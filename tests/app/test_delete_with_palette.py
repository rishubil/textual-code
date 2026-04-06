"""
Integration tests for deleting files/folders from the command palette.
"""

from pathlib import Path

from tests.conftest import await_workers, make_app
from textual_code.app import TextualCode
from textual_code.modals import DeleteFileModalScreen, PathSearchModal


async def test_delete_palette_file_message_opens_modal(
    workspace: Path, sample_py_file: Path
):
    """Posting DeletePathWithPaletteRequested(file) → DeleteFileModalScreen opens."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.post_message(
            TextualCode.DeletePathWithPaletteRequested(path=sample_py_file)
        )
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, DeleteFileModalScreen)


async def test_delete_palette_directory_message_opens_modal(workspace: Path):
    """Posting DeletePathWithPaletteRequested(directory) opens DeleteFileModalScreen."""
    subdir = workspace / "subdir"
    subdir.mkdir()

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.post_message(TextualCode.DeletePathWithPaletteRequested(path=subdir))
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, DeleteFileModalScreen)


async def test_delete_palette_file_confirm_deletes_file(
    workspace: Path, sample_py_file: Path
):
    """Confirming file deletion → file is actually deleted."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert sample_py_file.exists()

        app.post_message(
            TextualCode.DeletePathWithPaletteRequested(path=sample_py_file)
        )
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.click("#delete")
        await pilot.wait_for_scheduled_animations()

    assert not sample_py_file.exists()


async def test_delete_palette_directory_confirm_deletes_directory(workspace: Path):
    """Confirming directory deletion → directory is actually deleted."""
    subdir = workspace / "subdir"
    subdir.mkdir()

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert subdir.exists()

        app.post_message(TextualCode.DeletePathWithPaletteRequested(path=subdir))
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.click("#delete")
        await pilot.wait_for_scheduled_animations()
        await await_workers(pilot)

    assert not subdir.exists()


async def test_delete_palette_nonempty_directory_deletes_all_contents(workspace: Path):
    """Confirming deletion of non-empty directory → all contents deleted."""
    subdir = workspace / "subdir"
    subdir.mkdir()
    (subdir / "file1.txt").write_text("hello")
    (subdir / "nested").mkdir()
    (subdir / "nested" / "file2.txt").write_text("world")

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()

        app.post_message(TextualCode.DeletePathWithPaletteRequested(path=subdir))
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.click("#delete")
        await pilot.wait_for_scheduled_animations()
        await await_workers(pilot)

    assert not subdir.exists()


async def test_delete_palette_cancel_keeps_file(workspace: Path, sample_py_file: Path):
    """Cancel → file is preserved."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert sample_py_file.exists()

        app.post_message(
            TextualCode.DeletePathWithPaletteRequested(path=sample_py_file)
        )
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.click("#cancel")
        await pilot.wait_for_scheduled_animations()

    assert sample_py_file.exists()


async def test_delete_palette_open_tab_file_closes_tab(
    workspace: Path, sample_py_file: Path
):
    """Deleting an open tab's file → tab is closed."""
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert len(app.main_view.opened_pane_ids) == 1

        app.post_message(
            TextualCode.DeletePathWithPaletteRequested(path=sample_py_file)
        )
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.click("#delete")
        await pilot.wait_for_scheduled_animations()
        assert len(app.main_view.opened_pane_ids) == 0

    assert not sample_py_file.exists()


async def test_get_system_commands_contains_delete_file_or_directory(workspace: Path):
    """get_system_commands() includes 'Delete file or directory'."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        commands = list(app.get_system_commands(app.screen))
        titles = [cmd.title for cmd in commands]
        assert "Delete File or Directory" in titles


async def test_action_delete_file_or_directory_opens_palette(
    workspace: Path,
):
    """action_delete_file_or_directory() → CommandPalette opens."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.action_delete_file_or_directory()
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, PathSearchModal)
