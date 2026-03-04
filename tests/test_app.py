"""
TextualCode app integration tests.

- App startup and component verification
- Automatic tab opening when started with a file argument
- Ctrl+N new editor
- File/directory creation (CreateFileOrDirRequested)
- OpenFileRequested message
- Quit (with/without unsaved changes)
"""

from pathlib import Path

from textual.widgets import Footer

from tests.conftest import make_app
from textual_code.app import MainView, TextualCode
from textual_code.modals import UnsavedChangeQuitModalScreen
from textual_code.widgets.sidebar import Sidebar

# ── App startup ───────────────────────────────────────────────────────────────


async def test_app_composes_with_sidebar_mainview_footer(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one(Sidebar) is not None
        assert app.query_one(MainView) is not None
        assert app.query_one(Footer) is not None


async def test_app_starts_without_open_file(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0


async def test_app_opens_initial_file_on_start(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1


# ── Open file from shortcut (Ctrl+N) ─────────────────────────────────────────


async def test_ctrl_n_opens_new_empty_editor(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0

        await pilot.press("ctrl+n")
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1

        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.title == "<Untitled>"


async def test_ctrl_n_opens_multiple_editors(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+n")
        await pilot.pause()
        await pilot.press("ctrl+n")
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 2


# ── OpenFileRequested ────────────────────────────────────────────────────────


async def test_open_file_requested_opens_editor(workspace: Path, sample_py_file: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0

        app.post_message(TextualCode.OpenFileRequested(path=sample_py_file))
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1


# ── CreateFileOrDirRequested ─────────────────────────────────────────────────


async def test_create_file_creates_on_disk(workspace: Path):
    new_file = workspace / "created.py"
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(
            TextualCode.CreateFileOrDirRequested(path=new_file, is_dir=False)
        )
        await pilot.pause()

    assert new_file.exists()
    assert new_file.is_file()


async def test_create_file_opens_tab(workspace: Path):
    new_file = workspace / "created.py"
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(
            TextualCode.CreateFileOrDirRequested(path=new_file, is_dir=False)
        )
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1


async def test_create_directory_creates_on_disk(workspace: Path):
    new_dir = workspace / "subdir" / "nested"
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(
            TextualCode.CreateFileOrDirRequested(path=new_dir, is_dir=True)
        )
        await pilot.pause()

    assert new_dir.exists()
    assert new_dir.is_dir()


async def test_create_directory_does_not_open_tab(workspace: Path):
    new_dir = workspace / "mydir"
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(
            TextualCode.CreateFileOrDirRequested(path=new_dir, is_dir=True)
        )
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0


async def test_create_existing_file_shows_notification(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace)
    notifications: list[str] = []
    original_notify = app.notify

    def capture_notify(msg, **kwargs):
        notifications.append(msg)
        return original_notify(msg, **kwargs)

    app.notify = capture_notify  # type: ignore[method-assign]

    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(
            TextualCode.CreateFileOrDirRequested(path=sample_py_file, is_dir=False)
        )
        await pilot.pause()

    assert any("already exists" in n for n in notifications)


# ── Quit ────────────────────────────────────────────────────────────────────


async def test_quit_without_unsaved_exits(workspace: Path):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_quit()
        await pilot.pause()


async def test_quit_with_unsaved_shows_modal(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "unsaved change\n"
        await pilot.pause()

        app.action_quit()
        await pilot.pause()
        assert isinstance(app.screen, UnsavedChangeQuitModalScreen)


async def test_quit_with_unsaved_quit_button_exits(
    workspace: Path, sample_py_file: Path
):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.text = "unsaved\n"
        await pilot.pause()

        app.action_quit()
        await pilot.pause()
        await pilot.click("#quit")
        await pilot.pause()


# ── Close all files ──────────────────────────────────────────────────────────


async def test_close_all_files_via_app_action(workspace: Path, sample_py_file: Path):
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 1

        app.action_close_all_files()
        await pilot.pause()
        assert len(app.main_view.opened_pane_ids) == 0
