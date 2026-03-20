"""
Explorer delete (Delete key) integration tests.

Tests for the feature: delete files/folders with the Delete key
in the sidebar DirectoryTree
"""

from pathlib import Path

from tests.conftest import make_app
from textual_code.modals import DeleteFileModalScreen
from textual_code.widgets.explorer import Explorer

# ── FileDeleteRequested message standalone tests ──────────────────────────────


async def test_file_delete_requested_message_posts(
    workspace: Path, sample_py_file: Path
):
    """Posting FileDeleteRequested directly → modal opens."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileDeleteRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)


# ── File deletion ─────────────────────────────────────────────────────────────


async def test_delete_file_shows_modal(workspace: Path, sample_py_file: Path):
    """File delete request → DeleteFileModalScreen opens."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileDeleteRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)


async def test_delete_file_confirm_deletes_file(workspace: Path, sample_py_file: Path):
    """Clicking delete confirm → file is actually deleted."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert sample_py_file.exists()

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileDeleteRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.pause()
        await pilot.click("#delete")
        await pilot.pause()

    assert not sample_py_file.exists()


async def test_delete_file_cancel_keeps_file(workspace: Path, sample_py_file: Path):
    """Clicking delete cancel → file is preserved."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert sample_py_file.exists()

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileDeleteRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.pause()
        await pilot.click("#cancel")
        await pilot.pause()

    assert sample_py_file.exists()


async def test_delete_open_file_closes_tab(workspace: Path, sample_py_file: Path):
    """Deleting an open file → its tab is closed."""
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileDeleteRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.pause()
        await pilot.click("#delete")
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0

    assert not sample_py_file.exists()


# ── Directory deletion ────────────────────────────────────────────────────────


async def test_delete_directory_shows_modal(workspace: Path):
    """Directory delete request → DeleteFileModalScreen opens."""
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
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)


async def test_delete_directory_confirm_deletes_directory(workspace: Path):
    """Clicking delete confirm → directory is actually deleted."""
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
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.pause()
        await pilot.click("#delete")
        await pilot.pause()

    assert not subdir.exists()


async def test_delete_nonempty_directory_deletes_all_contents(workspace: Path):
    """Deleting a non-empty directory → all contents are deleted."""
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
        await pilot.pause()
        assert isinstance(app.screen, DeleteFileModalScreen)

        await pilot.pause()
        await pilot.click("#delete")
        await pilot.pause()

    assert not subdir.exists()


# ── No cursor node ────────────────────────────────────────────────────────────


async def test_delete_no_cursor_node_does_nothing(workspace: Path):
    """No cursor node → modal does not open."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        # call action_delete_node directly - should do nothing when cursor_node is None
        app.sidebar.explorer.action_delete_node()
        await pilot.pause()
        assert not isinstance(app.screen, DeleteFileModalScreen)
