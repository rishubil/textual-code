"""
Explorer move integration tests.

Tests for the feature: move files/folders to different destination folders
via the sidebar DirectoryTree and command palette.
The move dialog uses a CommandPalette-based directory picker with fuzzy search.
"""

from pathlib import Path

from textual.command import CommandPalette

from tests.conftest import make_app
from textual_code.app import TextualCode
from textual_code.commands import _read_workspace_directories
from textual_code.widgets.explorer import Explorer

# ── _read_workspace_directories unit tests ────────────────────────────────────


def test_read_workspace_directories_returns_only_dirs(tmp_path: Path):
    """Only directories (+ root) are returned, not files."""
    (tmp_path / "file.py").write_text("x")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x")
    (tmp_path / "lib").mkdir()

    dirs = _read_workspace_directories(tmp_path)
    assert tmp_path in dirs  # root
    assert tmp_path / "src" in dirs
    assert tmp_path / "lib" in dirs
    # Files must NOT be included
    assert tmp_path / "file.py" not in dirs
    assert tmp_path / "src" / "main.py" not in dirs


def test_read_workspace_directories_includes_root(tmp_path: Path):
    """Workspace root is always in results, even with no subdirectories."""
    dirs = _read_workspace_directories(tmp_path)
    assert tmp_path in dirs
    assert len(dirs) == 1  # only root


def test_read_workspace_directories_includes_hidden_dirs(tmp_path: Path):
    """Dot-prefixed directories are included as valid move destinations."""
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "workflows").mkdir()
    (tmp_path / ".vscode").mkdir()
    (tmp_path / "visible").mkdir()

    dirs = _read_workspace_directories(tmp_path)
    assert tmp_path / "visible" in dirs
    assert tmp_path / ".github" in dirs
    assert tmp_path / ".github" / "workflows" in dirs
    assert tmp_path / ".vscode" in dirs


def test_read_workspace_directories_excludes_git_internals(tmp_path: Path):
    """.git directories and their subtrees are excluded at any depth."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "objects").mkdir()
    (tmp_path / ".git" / "refs").mkdir()
    (tmp_path / ".github").mkdir()
    # Nested .git (submodule scenario)
    (tmp_path / "submodule").mkdir()
    (tmp_path / "submodule" / ".git").mkdir()
    (tmp_path / "submodule" / ".git" / "objects").mkdir()

    dirs = _read_workspace_directories(tmp_path)
    # .git and internals excluded
    assert tmp_path / ".git" not in dirs
    assert tmp_path / ".git" / "objects" not in dirs
    assert tmp_path / ".git" / "refs" not in dirs
    # .github is NOT .git — must be included
    assert tmp_path / ".github" in dirs
    # submodule dir included, but its .git excluded
    assert tmp_path / "submodule" in dirs
    assert tmp_path / "submodule" / ".git" not in dirs
    assert tmp_path / "submodule" / ".git" / "objects" not in dirs


# ── FileMoveRequested message → CommandPalette ────────────────────────────────


async def test_file_move_requested_opens_command_palette(
    workspace: Path, sample_py_file: Path
):
    """Posting FileMoveRequested directly → CommandPalette opens (not modal)."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileMoveRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        assert isinstance(app.screen, CommandPalette)


# ── File move via MoveDestinationSelected ─────────────────────────────────────


async def test_move_file_to_directory(workspace: Path, sample_py_file: Path):
    """MoveDestinationSelected → file moved to dest dir keeping original name."""
    dest_dir = workspace / "lib"
    dest_dir.mkdir()
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert sample_py_file.exists()

        app.post_message(
            TextualCode.MoveDestinationSelected(
                source_path=sample_py_file, destination_dir=dest_dir
            )
        )
        await pilot.pause()

    assert not sample_py_file.exists()
    assert (workspace / "lib" / "hello.py").exists()


async def test_move_file_cancel_command_palette(workspace: Path, sample_py_file: Path):
    """Pressing Escape on CommandPalette → file unchanged."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileMoveRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        assert isinstance(app.screen, CommandPalette)

        await pilot.press("escape")
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

        app.post_message(
            TextualCode.MoveDestinationSelected(
                source_path=sample_py_file, destination_dir=dest_dir
            )
        )
        await pilot.pause()

        assert editor.path == workspace / "lib" / "hello.py"
        assert "hello.py" in editor.title


async def test_move_to_existing_shows_error(workspace: Path, sample_py_file: Path):
    """Moving to a directory that already has a file with the same name → error."""
    dest_dir = workspace / "lib"
    dest_dir.mkdir()
    (dest_dir / "hello.py").write_text("existing\n")

    app = make_app(workspace)
    async with app.run_test(notifications=True) as pilot:
        await pilot.pause()

        app.post_message(
            TextualCode.MoveDestinationSelected(
                source_path=sample_py_file, destination_dir=dest_dir
            )
        )
        await pilot.pause()

    assert sample_py_file.exists()
    assert (dest_dir / "hello.py").read_text() == "existing\n"


async def test_move_unchanged_path_noop(workspace: Path, sample_py_file: Path):
    """Selecting the same parent directory → no filesystem change."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Destination dir is the same as source's parent
        app.post_message(
            TextualCode.MoveDestinationSelected(
                source_path=sample_py_file, destination_dir=workspace
            )
        )
        await pilot.pause()

    assert sample_py_file.exists()


# ── Directory move ────────────────────────────────────────────────────────────


async def test_move_directory(workspace: Path):
    """Move directory → old dir gone, new location exists with contents."""
    subdir = workspace / "subdir"
    subdir.mkdir()
    (subdir / "file.txt").write_text("content")

    dest_dir = workspace / "dest"
    dest_dir.mkdir()

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        app.post_message(
            TextualCode.MoveDestinationSelected(
                source_path=subdir, destination_dir=dest_dir
            )
        )
        await pilot.pause()

    assert not subdir.exists()
    assert (workspace / "dest" / "subdir").exists()
    assert (workspace / "dest" / "subdir" / "file.txt").read_text() == "content"


async def test_move_dir_updates_open_files(workspace: Path):
    """Moving a directory updates all open tabs under that directory."""
    subdir = workspace / "subdir"
    subdir.mkdir()
    child_file = subdir / "child.py"
    child_file.write_text("print('child')\n")

    dest_dir = workspace / "dest"
    dest_dir.mkdir()

    app = make_app(workspace, open_file=child_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.path == child_file

        app.post_message(
            TextualCode.MoveDestinationSelected(
                source_path=subdir, destination_dir=dest_dir
            )
        )
        await pilot.pause()

        assert editor.path == workspace / "dest" / "subdir" / "child.py"
        assert "child.py" in editor.title


# ── No cursor node ────────────────────────────────────────────────────────────


async def test_move_no_cursor_no_palette(workspace: Path):
    """No cursor node → command palette does not open."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.sidebar.explorer.action_move_node()
        await pilot.pause()
        assert not isinstance(app.screen, CommandPalette)


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

        app.post_message(
            TextualCode.MoveDestinationSelected(
                source_path=sample_py_file, destination_dir=dest_dir
            )
        )
        await pilot.pause()

        # Path updated but content and dirty state preserved
        assert editor.path == workspace / "lib" / "hello.py"
        assert editor.text == "modified content"
        assert editor.text != editor.initial_text


# ── Workspace boundary validation ─────────────────────────────────────────────


async def test_move_outside_workspace_shows_error(
    workspace: Path, sample_py_file: Path
):
    """Destination outside workspace → error notification, file unchanged."""
    outside = workspace.parent / "outside"
    outside.mkdir(exist_ok=True)

    app = make_app(workspace)
    async with app.run_test(notifications=True) as pilot:
        await pilot.pause()

        app.post_message(
            TextualCode.MoveDestinationSelected(
                source_path=sample_py_file, destination_dir=outside
            )
        )
        await pilot.pause()

    assert sample_py_file.exists()


# ── Move to workspace root ───────────────────────────────────────────────────


async def test_move_file_to_workspace_root(workspace: Path):
    """File in subdirectory → move to workspace root."""
    subdir = workspace / "src"
    subdir.mkdir()
    src_file = subdir / "main.py"
    src_file.write_text("print('main')\n")

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        app.post_message(
            TextualCode.MoveDestinationSelected(
                source_path=src_file, destination_dir=workspace
            )
        )
        await pilot.pause()

    assert not src_file.exists()
    assert (workspace / "main.py").exists()
    assert (workspace / "main.py").read_text() == "print('main')\n"


async def test_move_file_already_in_root_noop(workspace: Path, sample_py_file: Path):
    """File already in workspace root → selecting root → no-op."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()

        app.post_message(
            TextualCode.MoveDestinationSelected(
                source_path=sample_py_file, destination_dir=workspace
            )
        )
        await pilot.pause()

    assert sample_py_file.exists()


# ── Defense-in-depth: subtree move ────────────────────────────────────────────


async def test_move_dir_into_own_subtree_shows_error(workspace: Path):
    """Moving a directory into its own subtree → error notification."""
    parent_dir = workspace / "parent"
    parent_dir.mkdir()
    child_dir = parent_dir / "child"
    child_dir.mkdir()

    app = make_app(workspace)
    async with app.run_test(notifications=True) as pilot:
        await pilot.pause()

        app.post_message(
            TextualCode.MoveDestinationSelected(
                source_path=parent_dir, destination_dir=child_dir
            )
        )
        await pilot.pause()

    # Directory should remain unchanged
    assert parent_dir.exists()
    assert child_dir.exists()


# ── Command palette move ──────────────────────────────────────────────────────


async def test_move_via_command_palette(workspace: Path, sample_py_file: Path):
    """MovePathWithPaletteRequested → CommandPalette → select dest → moved."""
    dest_dir = workspace / "lib"
    dest_dir.mkdir()

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Simulate: first palette selected the source file,
        # now _handle_move_path opens second palette for destination.
        app.post_message(TextualCode.MovePathWithPaletteRequested(path=sample_py_file))
        await pilot.pause()
        assert isinstance(app.screen, CommandPalette)

        # Dismiss palette and use MoveDestinationSelected directly
        await pilot.press("escape")
        await pilot.pause()

        app.post_message(
            TextualCode.MoveDestinationSelected(
                source_path=sample_py_file, destination_dir=dest_dir
            )
        )
        await pilot.pause()

    assert not sample_py_file.exists()
    assert (workspace / "lib" / "hello.py").exists()
