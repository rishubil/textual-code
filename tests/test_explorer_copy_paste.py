"""
Explorer copy/cut/paste integration tests.

Tests for the feature: copy/cut/paste files and folders in the sidebar
DirectoryTree using Ctrl+C/X/V or the command palette.
"""

from pathlib import Path

from tests.conftest import make_app
from textual_code.app import _resolve_paste_name
from textual_code.widgets.explorer import Explorer

# ── _resolve_paste_name unit tests ───────────────────────────────────────────


def test_resolve_paste_name_no_conflict(tmp_path: Path):
    """When target does not exist, return it unchanged."""
    result = _resolve_paste_name(tmp_path, "file.py")
    assert result == tmp_path / "file.py"


def test_resolve_paste_name_first_copy(tmp_path: Path):
    """When name exists, append ' copy' before extension."""
    (tmp_path / "file.py").write_text("x")
    result = _resolve_paste_name(tmp_path, "file.py")
    assert result == tmp_path / "file copy.py"


def test_resolve_paste_name_copy_2(tmp_path: Path):
    """When 'name copy' also exists, use 'name copy 2'."""
    (tmp_path / "file.py").write_text("x")
    (tmp_path / "file copy.py").write_text("x")
    result = _resolve_paste_name(tmp_path, "file.py")
    assert result == tmp_path / "file copy 2.py"


def test_resolve_paste_name_copy_n(tmp_path: Path):
    """Skip all existing copy suffixes until a free slot is found."""
    (tmp_path / "file.py").write_text("x")
    (tmp_path / "file copy.py").write_text("x")
    (tmp_path / "file copy 2.py").write_text("x")
    (tmp_path / "file copy 3.py").write_text("x")
    result = _resolve_paste_name(tmp_path, "file.py")
    assert result == tmp_path / "file copy 4.py"


def test_resolve_paste_name_directory(tmp_path: Path):
    """Directories (no extension) get ' copy' suffix."""
    (tmp_path / "mydir").mkdir()
    result = _resolve_paste_name(tmp_path, "mydir")
    assert result == tmp_path / "mydir copy"


def test_resolve_paste_name_directory_copy_2(tmp_path: Path):
    """Directories with existing copy get ' copy 2'."""
    (tmp_path / "mydir").mkdir()
    (tmp_path / "mydir copy").mkdir()
    result = _resolve_paste_name(tmp_path, "mydir")
    assert result == tmp_path / "mydir copy 2"


def test_resolve_paste_name_multi_dot(tmp_path: Path):
    """Multi-dot filenames split on last dot only."""
    (tmp_path / "archive.tar.gz").write_text("x")
    result = _resolve_paste_name(tmp_path, "archive.tar.gz")
    assert result == tmp_path / "archive.tar copy.gz"


# ── Copy message tests ──────────────────────────────────────────────────────


async def test_copy_file_stores_clipboard(workspace: Path, sample_py_file: Path):
    """Posting FileCopyRequested stores ('copy', path) in app clipboard."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileCopyRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()

    assert app._file_clipboard == ("copy", sample_py_file)


async def test_cut_file_stores_clipboard(workspace: Path, sample_py_file: Path):
    """Posting FileCutRequested stores ('cut', path) in app clipboard."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileCutRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()

    assert app._file_clipboard == ("cut", sample_py_file)


async def test_copy_replaces_previous_clipboard(workspace: Path, sample_py_file: Path):
    """A second copy replaces the previous clipboard content."""
    other = workspace / "other.py"
    other.write_text("other\n")
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileCopyRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        assert app._file_clipboard == ("copy", sample_py_file)

        explorer.post_message(Explorer.FileCopyRequested(explorer=explorer, path=other))
        await pilot.pause()

    assert app._file_clipboard == ("copy", other)


# ── Paste copy tests ────────────────────────────────────────────────────────


async def test_paste_copied_file(workspace: Path, sample_py_file: Path):
    """Copy then paste a file into a different directory."""
    dest_dir = workspace / "lib"
    dest_dir.mkdir()
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        # Copy
        explorer.post_message(
            Explorer.FileCopyRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        # Paste
        explorer.post_message(
            Explorer.FilePasteRequested(explorer=explorer, target_dir=dest_dir)
        )
        await pilot.pause()

    # Source still exists (copy, not cut)
    assert sample_py_file.exists()
    # Destination exists with same name
    assert (dest_dir / "hello.py").exists()


async def test_paste_copied_file_content_preserved(
    workspace: Path, sample_py_file: Path
):
    """Copied file content matches the original."""
    dest_dir = workspace / "lib"
    dest_dir.mkdir()
    original_content = sample_py_file.read_text()
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileCopyRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        explorer.post_message(
            Explorer.FilePasteRequested(explorer=explorer, target_dir=dest_dir)
        )
        await pilot.pause()

    assert (dest_dir / "hello.py").read_text() == original_content


async def test_paste_copied_file_same_dir(workspace: Path, sample_py_file: Path):
    """Copy-paste in same directory creates 'name copy.ext'."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileCopyRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        explorer.post_message(
            Explorer.FilePasteRequested(explorer=explorer, target_dir=workspace)
        )
        await pilot.pause()

    assert sample_py_file.exists()
    assert (workspace / "hello copy.py").exists()


async def test_paste_copied_file_preserves_clipboard(
    workspace: Path, sample_py_file: Path
):
    """After copy-paste, clipboard is still set (can paste again)."""
    dest_dir = workspace / "lib"
    dest_dir.mkdir()
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileCopyRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        explorer.post_message(
            Explorer.FilePasteRequested(explorer=explorer, target_dir=dest_dir)
        )
        await pilot.pause()

    assert app._file_clipboard == ("copy", sample_py_file)


async def test_paste_copied_file_twice(workspace: Path, sample_py_file: Path):
    """Copy once, paste twice in same dir → 'copy' then 'copy 2'."""
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileCopyRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        # First paste
        explorer.post_message(
            Explorer.FilePasteRequested(explorer=explorer, target_dir=workspace)
        )
        await pilot.pause()
        # Second paste
        explorer.post_message(
            Explorer.FilePasteRequested(explorer=explorer, target_dir=workspace)
        )
        await pilot.pause()

    assert (workspace / "hello copy.py").exists()
    assert (workspace / "hello copy 2.py").exists()


async def test_paste_copied_directory(workspace: Path):
    """Copy-paste a directory duplicates the entire tree."""
    src = workspace / "src"
    src.mkdir()
    (src / "main.py").write_text("main\n")
    (src / "util.py").write_text("util\n")
    dest_dir = workspace / "backup"
    dest_dir.mkdir()

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(Explorer.FileCopyRequested(explorer=explorer, path=src))
        await pilot.pause()
        explorer.post_message(
            Explorer.FilePasteRequested(explorer=explorer, target_dir=dest_dir)
        )
        await pilot.pause()

    assert src.exists()  # source preserved
    assert (dest_dir / "src" / "main.py").exists()
    assert (dest_dir / "src" / "util.py").exists()
    assert (dest_dir / "src" / "main.py").read_text() == "main\n"


# ── Paste cut tests ─────────────────────────────────────────────────────────


async def test_paste_cut_file(workspace: Path, sample_py_file: Path):
    """Cut then paste a file → source removed, dest created."""
    dest_dir = workspace / "lib"
    dest_dir.mkdir()
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileCutRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        explorer.post_message(
            Explorer.FilePasteRequested(explorer=explorer, target_dir=dest_dir)
        )
        await pilot.pause()

    assert not sample_py_file.exists()
    assert (dest_dir / "hello.py").exists()


async def test_paste_cut_file_updates_tab(workspace: Path, sample_py_file: Path):
    """Cutting an open file and pasting → editor.path and tab title update."""
    dest_dir = workspace / "lib"
    dest_dir.mkdir()
    app = make_app(workspace, open_file=sample_py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.path == sample_py_file

        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileCutRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        explorer.post_message(
            Explorer.FilePasteRequested(explorer=explorer, target_dir=dest_dir)
        )
        await pilot.pause()

    expected = dest_dir / "hello.py"
    assert editor.path == expected


async def test_paste_cut_directory_updates_open_files(workspace: Path):
    """Cutting a dir with open files → tab paths updated."""
    src = workspace / "src"
    src.mkdir()
    main_py = src / "main.py"
    main_py.write_text("main\n")
    dest_dir = workspace / "lib"
    dest_dir.mkdir()

    app = make_app(workspace, open_file=main_py)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.path == main_py

        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(Explorer.FileCutRequested(explorer=explorer, path=src))
        await pilot.pause()
        explorer.post_message(
            Explorer.FilePasteRequested(explorer=explorer, target_dir=dest_dir)
        )
        await pilot.pause()

    assert editor.path == dest_dir / "src" / "main.py"


async def test_paste_cut_clears_clipboard(workspace: Path, sample_py_file: Path):
    """After cut-paste, clipboard is cleared."""
    dest_dir = workspace / "lib"
    dest_dir.mkdir()
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileCutRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        explorer.post_message(
            Explorer.FilePasteRequested(explorer=explorer, target_dir=dest_dir)
        )
        await pilot.pause()

    assert app._file_clipboard is None


# ── Edge case tests ──────────────────────────────────────────────────────────


async def test_paste_empty_clipboard(workspace: Path):
    """Paste with empty clipboard → warning notification."""
    app = make_app(workspace)
    async with app.run_test(notifications=True) as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FilePasteRequested(explorer=explorer, target_dir=workspace)
        )
        await pilot.pause()

    assert any("Nothing to paste" in str(n.message) for n in app._notifications)


async def test_paste_source_deleted(workspace: Path, sample_py_file: Path):
    """Paste when source no longer exists → error, clipboard cleared."""
    app = make_app(workspace)
    async with app.run_test(notifications=True) as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(
            Explorer.FileCopyRequested(explorer=explorer, path=sample_py_file)
        )
        await pilot.pause()
        # Delete the source between copy and paste
        sample_py_file.unlink()
        explorer.post_message(
            Explorer.FilePasteRequested(explorer=explorer, target_dir=workspace)
        )
        await pilot.pause()

    assert app._file_clipboard is None
    assert any("no longer exists" in str(n.message) for n in app._notifications)


async def test_paste_dir_into_itself(workspace: Path):
    """Cannot paste a directory into itself."""
    src = workspace / "mydir"
    src.mkdir()
    app = make_app(workspace)
    async with app.run_test(notifications=True) as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(Explorer.FileCopyRequested(explorer=explorer, path=src))
        await pilot.pause()
        explorer.post_message(
            Explorer.FilePasteRequested(explorer=explorer, target_dir=src)
        )
        await pilot.pause()

    assert any("Cannot paste" in str(n.message) for n in app._notifications)


async def test_paste_target_is_file_uses_parent(workspace: Path, sample_py_file: Path):
    """FilePasteRequested from _get_paste_target_dir uses parent for files.

    This test directly verifies the target_dir logic by posting
    FilePasteRequested with the parent of the selected file.
    """
    other = workspace / "other.py"
    other.write_text("other\n")
    dest_dir = workspace / "lib"
    dest_dir.mkdir()
    (dest_dir / "inner.py").write_text("inner\n")

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.sidebar is not None
        explorer = app.sidebar.explorer
        explorer.post_message(Explorer.FileCopyRequested(explorer=explorer, path=other))
        await pilot.pause()
        # Paste with target_dir = lib (as if a file inside lib was selected)
        explorer.post_message(
            Explorer.FilePasteRequested(explorer=explorer, target_dir=dest_dir)
        )
        await pilot.pause()

    assert (dest_dir / "other.py").exists()
