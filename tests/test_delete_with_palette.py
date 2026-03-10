"""
커맨드 팔레트에서 파일/폴더 삭제 통합 테스트.
"""

from pathlib import Path

from textual.command import CommandPalette

from tests.conftest import make_app
from textual_code.app import TextualCode
from textual_code.modals import DeleteFileModalScreen


async def test_delete_palette_file_message_opens_modal(
    workspace: Path, sample_py_file: Path
):
    """DeletePathWithPaletteRequested(파일) 포스트 → DeleteFileModalScreen 열림."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(
            TextualCode.DeletePathWithPaletteRequested(path=sample_py_file)
        )
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)


async def test_delete_palette_directory_message_opens_modal(workspace: Path):
    """DeletePathWithPaletteRequested(디렉토리) 포스트 → DeleteFileModalScreen 열림."""
    subdir = workspace / "subdir"
    subdir.mkdir()

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(TextualCode.DeletePathWithPaletteRequested(path=subdir))
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)


async def test_delete_palette_file_confirm_deletes_file(
    workspace: Path, sample_py_file: Path
):
    """파일 삭제 확인 → 파일 실제 삭제됨."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert sample_py_file.exists()

        app.post_message(
            TextualCode.DeletePathWithPaletteRequested(path=sample_py_file)
        )
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.click("#delete")
        await pilot.pause()

    assert not sample_py_file.exists()


async def test_delete_palette_directory_confirm_deletes_directory(workspace: Path):
    """디렉토리 삭제 확인 → 디렉토리 실제 삭제됨."""
    subdir = workspace / "subdir"
    subdir.mkdir()

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert subdir.exists()

        app.post_message(TextualCode.DeletePathWithPaletteRequested(path=subdir))
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.click("#delete")
        await pilot.pause()

    assert not subdir.exists()


async def test_delete_palette_nonempty_directory_deletes_all_contents(workspace: Path):
    """비어있지 않은 디렉토리 삭제 확인 → 전체 내용 삭제됨."""
    subdir = workspace / "subdir"
    subdir.mkdir()
    (subdir / "file1.txt").write_text("hello")
    (subdir / "nested").mkdir()
    (subdir / "nested" / "file2.txt").write_text("world")

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        app.post_message(TextualCode.DeletePathWithPaletteRequested(path=subdir))
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.click("#delete")
        await pilot.pause()

    assert not subdir.exists()


async def test_delete_palette_cancel_keeps_file(workspace: Path, sample_py_file: Path):
    """취소 → 파일 유지됨."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert sample_py_file.exists()

        app.post_message(
            TextualCode.DeletePathWithPaletteRequested(path=sample_py_file)
        )
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.click("#cancel")
        await pilot.pause()

    assert sample_py_file.exists()


async def test_delete_palette_open_tab_file_closes_tab(
    workspace: Path, sample_py_file: Path
):
    """열린 탭 파일 삭제 → 탭 닫힘."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1

        app.post_message(
            TextualCode.DeletePathWithPaletteRequested(path=sample_py_file)
        )
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.click("#delete")
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0

    assert not sample_py_file.exists()


async def test_get_system_commands_contains_delete_file_or_directory(workspace: Path):
    """get_system_commands()에 'Delete file or directory' 포함."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        commands = list(app.get_system_commands(app.screen))
        titles = [cmd.title for cmd in commands]
        assert "Delete file or directory" in titles


async def test_action_delete_file_or_dir_with_command_palette_opens_palette(
    workspace: Path,
):
    """action_delete_file_or_dir_with_command_palette() → CommandPalette 열림."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_delete_file_or_dir_with_command_palette()
        await pilot.pause()
        assert isinstance(app.screen, CommandPalette)
