"""
Explorer create file/directory validation tests.

Tests that the CreateFileOrDirRequested handler correctly validates
file/directory creation requests — duplicate detection, nested path creation,
and error handling.

VSCode origin: explorerModel.test.ts "Validate File Name (For Create)" and
"Validate Multi-Path File Names" sections.
"""

from pathlib import Path

from tests.conftest import make_app
from textual_code.app import TextualCode

# ── Duplicate detection ─────────────────────────────────────────────────────


async def test_create_duplicate_file_shows_error(workspace: Path, sample_py_file: Path):
    """Creating a file that already exists → error notification, no overwrite.

    VSCode origin: validateFileName (For Create) — 'alles.klar' (existing child)
    returns error.
    """
    original_content = sample_py_file.read_text()

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(
            TextualCode.CreateFileOrDirRequested(path=sample_py_file, is_dir=False)
        )
        await pilot.pause()

    # File still exists with original content (not overwritten)
    assert sample_py_file.exists()
    assert sample_py_file.read_text() == original_content


async def test_create_duplicate_directory_shows_error(workspace: Path):
    """Creating a directory that already exists → error notification.

    VSCode origin: validateFileName (Multi-Path) — existing path returns error.
    """
    subdir = workspace / "existing_dir"
    subdir.mkdir()
    (subdir / "child.txt").write_text("keep me\n")

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(TextualCode.CreateFileOrDirRequested(path=subdir, is_dir=True))
        await pilot.pause()

    # Directory unchanged, child file preserved
    assert subdir.is_dir()
    assert (subdir / "child.txt").read_text() == "keep me\n"


# ── Successful creation ─────────────────────────────────────────────────────


async def test_create_new_file(workspace: Path):
    """Creating a new file → file exists on disk.

    VSCode origin: validateFileName (For Create) — 'foo.bar' returns null (valid).
    """
    new_file = workspace / "new_file.py"
    assert not new_file.exists()

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(
            TextualCode.CreateFileOrDirRequested(path=new_file, is_dir=False)
        )
        await pilot.pause()

    assert new_file.exists()
    assert new_file.is_file()


async def test_create_new_directory(workspace: Path):
    """Creating a new directory → directory exists on disk."""
    new_dir = workspace / "new_dir"
    assert not new_dir.exists()

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(
            TextualCode.CreateFileOrDirRequested(path=new_dir, is_dir=True)
        )
        await pilot.pause()

    assert new_dir.exists()
    assert new_dir.is_dir()


async def test_create_nested_directory(workspace: Path):
    """Creating a nested directory path → all parents created.

    VSCode origin: validateFileName (Multi-Path) — 'foo/bar' returns null (valid).
    Our implementation uses mkdir(parents=True).
    """
    nested = workspace / "a" / "b" / "c"
    assert not nested.exists()
    assert not (workspace / "a").exists()

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(TextualCode.CreateFileOrDirRequested(path=nested, is_dir=True))
        await pilot.pause()

    assert nested.exists()
    assert nested.is_dir()
    assert (workspace / "a" / "b").is_dir()


async def test_create_hidden_file(workspace: Path):
    """Creating a hidden file (.dotfile) → succeeds.

    VSCode origin: validateFileName (For Create) — '.foo' returns null (valid).
    """
    hidden = workspace / ".gitignore"
    assert not hidden.exists()

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(
            TextualCode.CreateFileOrDirRequested(path=hidden, is_dir=False)
        )
        await pilot.pause()

    assert hidden.exists()
    assert hidden.is_file()


async def test_create_file_opens_in_editor(workspace: Path):
    """Creating a new file → file opens in editor tab."""
    new_file = workspace / "opened.py"

    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(
            TextualCode.CreateFileOrDirRequested(path=new_file, is_dir=False)
        )
        await pilot.pause()
        await pilot.pause()

        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.path == new_file


async def test_create_directory_does_not_open_editor(workspace: Path):
    """Creating a directory → no editor tab opened."""
    new_dir = workspace / "no_editor_dir"

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.post_message(
            TextualCode.CreateFileOrDirRequested(path=new_dir, is_dir=True)
        )
        await pilot.pause()

        editor = app.main_view.get_active_code_editor()
        assert editor is None

    assert new_dir.is_dir()
