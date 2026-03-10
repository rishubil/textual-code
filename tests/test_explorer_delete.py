"""
Explorer delete (Delete key) integration tests.

Tests for the feature: sidebar DirectoryTree 에서 Delete 키로 파일/폴더 삭제
"""

from pathlib import Path

from tests.conftest import make_app
from textual_code.modals import DeleteFileModalScreen
from textual_code.widgets.explorer import Explorer

# ── FileDeleteRequested 메시지 단독 테스트 ─────────────────────────────────────


async def test_file_delete_requested_message_posts(
    workspace: Path, sample_py_file: Path
):
    """FileDeleteRequested 메시지가 직접 post되면 모달이 열린다."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileDeleteRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)


# ── 파일 삭제 ──────────────────────────────────────────────────────────────────


async def test_delete_file_shows_modal(workspace: Path, sample_py_file: Path):
    """파일 삭제 요청 시 DeleteFileModalScreen이 열린다."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileDeleteRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)


async def test_delete_file_confirm_deletes_file(workspace: Path, sample_py_file: Path):
    """삭제 확인 클릭 시 파일이 실제로 삭제된다."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert sample_py_file.exists()

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileDeleteRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.click("#delete")
        await pilot.pause()

    assert not sample_py_file.exists()


async def test_delete_file_cancel_keeps_file(workspace: Path, sample_py_file: Path):
    """삭제 취소 클릭 시 파일이 유지된다."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert sample_py_file.exists()

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileDeleteRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.click("#cancel")
        await pilot.pause()

    assert sample_py_file.exists()


async def test_delete_open_file_closes_tab(workspace: Path, sample_py_file: Path):
    """열려있는 파일을 삭제하면 해당 탭이 닫힌다."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileDeleteRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.click("#delete")
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0

    assert not sample_py_file.exists()


# ── 디렉토리 삭제 ──────────────────────────────────────────────────────────────


async def test_delete_directory_shows_modal(workspace: Path):
    """디렉토리 삭제 요청 시 DeleteFileModalScreen이 열린다."""
    subdir = workspace / "subdir"
    subdir.mkdir()

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileDeleteRequested(explorer=explorer, path=subdir)
        )
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)


async def test_delete_directory_confirm_deletes_directory(workspace: Path):
    """디렉토리 삭제 확인 클릭 시 디렉토리가 실제로 삭제된다."""
    subdir = workspace / "subdir"
    subdir.mkdir()

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert subdir.exists()

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileDeleteRequested(explorer=explorer, path=subdir)
        )
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.click("#delete")
        await pilot.pause()

    assert not subdir.exists()


async def test_delete_nonempty_directory_deletes_all_contents(workspace: Path):
    """비어있지 않은 디렉토리 삭제 시 전체 내용이 삭제된다."""
    subdir = workspace / "subdir"
    subdir.mkdir()
    (subdir / "file1.txt").write_text("hello")
    (subdir / "nested").mkdir()
    (subdir / "nested" / "file2.txt").write_text("world")

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileDeleteRequested(explorer=explorer, path=subdir)
        )
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.click("#delete")
        await pilot.pause()

    assert not subdir.exists()


# ── 선택 노드 없음 ─────────────────────────────────────────────────────────────


async def test_delete_no_cursor_node_does_nothing(workspace: Path):
    """커서 노드가 없으면 모달이 열리지 않는다."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        # action_delete_node 직접 호출 - cursor_node가 None이면 아무 일도 없어야 함
        app.sidebar.explorer.action_delete_node()
        await pilot.pause()
        assert not isinstance(app.screen, DeleteFileModalScreen)
