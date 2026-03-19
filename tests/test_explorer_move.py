"""
Explorer move integration tests.

Tests for the feature: move files/folders to different paths
via the sidebar DirectoryTree and command palette.
"""

from pathlib import Path

from textual.widgets import Input

from tests.conftest import make_app
from textual_code.modals import MoveModalScreen
from textual_code.widgets.explorer import Explorer

# ── FileMoveRequested message standalone tests ────────────────────────────────


async def test_file_move_requested_message_posts(workspace: Path, sample_py_file: Path):
    """Posting FileMoveRequested directly → modal opens."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileMoveRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        assert isinstance(app.screen, MoveModalScreen)


# ── File move ─────────────────────────────────────────────────────────────────


async def test_move_file_from_explorer(workspace: Path, sample_py_file: Path):
    """Move confirm → file is moved on disk."""
    dest_dir = workspace / "lib"
    dest_dir.mkdir()
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert sample_py_file.exists()

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileMoveRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        assert isinstance(app.screen, MoveModalScreen)

        inp = app.screen.query_one(Input)
        inp.value = "lib/hello.py"
        await pilot.click("#move")
        await pilot.pause()

    assert not sample_py_file.exists()
    assert (workspace / "lib" / "hello.py").exists()


async def test_move_file_cancel(workspace: Path, sample_py_file: Path):
    """Cancel → file is unchanged."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileMoveRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        assert isinstance(app.screen, MoveModalScreen)

        await pilot.click("#cancel")
        await pilot.pause()

    assert sample_py_file.exists()


async def test_move_open_file_updates_tab(workspace: Path, sample_py_file: Path):
    """Moving an open file → editor.path and tab title update."""
    dest_dir = workspace / "lib"
    dest_dir.mkdir()
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.path == sample_py_file

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileMoveRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        assert isinstance(app.screen, MoveModalScreen)

        inp = app.screen.query_one(Input)
        inp.value = "lib/hello.py"
        await pilot.click("#move")
        await pilot.pause()

        assert editor.path == workspace / "lib" / "hello.py"
        assert "hello.py" in editor.title


async def test_move_to_existing_shows_error(workspace: Path, sample_py_file: Path):
    """Moving to an existing name → error notification, file unchanged."""
    existing = workspace / "existing.py"
    existing.write_text("existing\n")

    app = make_app(workspace)
    async with app.run_test(notifications=True) as pilot:
        await pilot.pause()

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileMoveRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()

        inp = app.screen.query_one(Input)
        inp.value = "existing.py"
        await pilot.click("#move")
        await pilot.pause()

    assert sample_py_file.exists()
    assert existing.read_text() == "existing\n"


async def test_move_unchanged_path_noop(workspace: Path, sample_py_file: Path):
    """Same path → no filesystem change."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileMoveRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()

        # Don't change the input value — keep it as the original path
        await pilot.click("#move")
        await pilot.pause()

    assert sample_py_file.exists()


async def test_move_to_subdirectory(workspace: Path, sample_py_file: Path):
    """Move file into a new subdirectory → creates parent dirs, moves file."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileMoveRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()

        inp = app.screen.query_one(Input)
        inp.value = "new_dir/sub/hello.py"
        await pilot.click("#move")
        await pilot.pause()

    assert not sample_py_file.exists()
    assert (workspace / "new_dir" / "sub" / "hello.py").exists()


# ── Directory move ────────────────────────────────────────────────────────────


async def test_move_directory_from_explorer(workspace: Path):
    """Move directory → old dir gone, new dir exists with contents."""
    subdir = workspace / "subdir"
    subdir.mkdir()
    (subdir / "file.txt").write_text("content")

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileMoveRequested(explorer=explorer, path=subdir)
        )
        await pilot.pause()
        assert isinstance(app.screen, MoveModalScreen)

        inp = app.screen.query_one(Input)
        inp.value = "moved_dir"
        await pilot.click("#move")
        await pilot.pause()

    assert not subdir.exists()
    assert (workspace / "moved_dir").exists()
    assert (workspace / "moved_dir" / "file.txt").read_text() == "content"


async def test_move_dir_updates_open_files(workspace: Path):
    """Moving a directory updates all open tabs under that directory."""
    subdir = workspace / "subdir"
    subdir.mkdir()
    child_file = subdir / "child.py"
    child_file.write_text("print('child')\n")

    app = make_app(workspace, open_file=child_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.path == child_file

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileMoveRequested(explorer=explorer, path=subdir)
        )
        await pilot.pause()

        inp = app.screen.query_one(Input)
        inp.value = "newdir"
        await pilot.click("#move")
        await pilot.pause()

        assert editor.path == workspace / "newdir" / "child.py"
        assert "child.py" in editor.title


# ── No cursor node ────────────────────────────────────────────────────────────


async def test_move_no_cursor_no_modal(workspace: Path):
    """No cursor node → modal does not open."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.sidebar.explorer.action_move_node()
        await pilot.pause()
        assert not isinstance(app.screen, MoveModalScreen)


# ── Unsaved changes preservation ──────────────────────────────────────────────


async def test_move_file_preserves_unsaved_changes(
    workspace: Path, sample_py_file: Path
):
    """Moving preserves unsaved (dirty) editor state."""
    dest_dir = workspace / "lib"
    dest_dir.mkdir()
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None

        # Make the editor dirty
        editor.text = "modified content"
        await pilot.pause()

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileMoveRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()

        inp = app.screen.query_one(Input)
        inp.value = "lib/hello.py"
        await pilot.click("#move")
        await pilot.pause()

        # Path updated but content and dirty state preserved
        assert editor.path == workspace / "lib" / "hello.py"
        assert editor.text == "modified content"
        assert editor.text != editor.initial_text


# ── Workspace boundary validation ─────────────────────────────────────────────


async def test_move_outside_workspace_shows_error(
    workspace: Path, sample_py_file: Path
):
    """Path outside workspace → error notification, file unchanged."""
    app = make_app(workspace)
    async with app.run_test(notifications=True) as pilot:
        await pilot.pause()

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileMoveRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()

        inp = app.screen.query_one(Input)
        inp.value = "../../etc/passwd"
        await pilot.click("#move")
        await pilot.pause()

    assert sample_py_file.exists()


async def test_move_with_dot_dot_within_workspace(
    workspace: Path, sample_py_file: Path
):
    """Relative path with .. that resolves within workspace → success."""
    subdir = workspace / "src"
    subdir.mkdir()
    lib_dir = workspace / "lib"
    lib_dir.mkdir()

    # Move hello.py into src/../lib/hello.py which resolves to lib/hello.py
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileMoveRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()

        inp = app.screen.query_one(Input)
        inp.value = "src/../lib/hello.py"
        await pilot.click("#move")
        await pilot.pause()

    assert not sample_py_file.exists()
    assert (workspace / "lib" / "hello.py").exists()


async def test_move_with_dot_dot_escaping_workspace(
    workspace: Path, sample_py_file: Path
):
    """Relative path with .. that escapes workspace → error."""
    app = make_app(workspace)
    async with app.run_test(notifications=True) as pilot:
        await pilot.pause()

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileMoveRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()

        inp = app.screen.query_one(Input)
        inp.value = "../outside/hello.py"
        await pilot.click("#move")
        await pilot.pause()

    assert sample_py_file.exists()


# ── Command palette move ──────────────────────────────────────────────────────


async def test_move_via_command_palette(workspace: Path, sample_py_file: Path):
    """MovePathWithPaletteRequested → modal → confirm → moved."""
    from textual_code.app import TextualCode

    dest_dir = workspace / "lib"
    dest_dir.mkdir()

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(TextualCode.MovePathWithPaletteRequested(path=sample_py_file))
        await pilot.pause()
        assert isinstance(app.screen, MoveModalScreen)

        inp = app.screen.query_one(Input)
        inp.value = "lib/hello.py"
        await pilot.click("#move")
        await pilot.pause()

    assert not sample_py_file.exists()
    assert (workspace / "lib" / "hello.py").exists()
