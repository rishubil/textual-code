"""Tests for OpenFileCommandProvider file enumeration (commands.py)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from textual_code.commands import (
    _read_workspace_directories,
    _read_workspace_files,
    _read_workspace_paths,
)


@pytest.fixture
def git_workspace(tmp_path: Path) -> Path:
    """Create a tmp_path with `git init` so ripgrep-rs respects .gitignore."""
    subprocess.run(
        ["git", "init"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    return tmp_path


def test_directories_excluded(tmp_path: Path) -> None:
    """Only files are returned — directories are excluded."""
    (tmp_path / "subdir").mkdir()
    (tmp_path / "file.txt").write_text("content")

    result = _read_workspace_files(tmp_path)
    names = [str(p) for p in result]
    assert "file.txt" in names
    assert "subdir" not in names


def test_hidden_dir_files_excluded(tmp_path: Path) -> None:
    """Files inside hidden directories are excluded when show_hidden_files=False."""
    hidden = tmp_path / ".git"
    hidden.mkdir()
    (hidden / "config").write_text("data")
    (tmp_path / "visible.txt").write_text("data")

    result = _read_workspace_files(tmp_path, show_hidden_files=False)
    names = [str(p) for p in result]
    assert "visible.txt" in names
    assert not any(".git" in n for n in names)


def test_hidden_files_excluded(tmp_path: Path) -> None:
    """Hidden files (dot-prefixed) are excluded when show_hidden_files=False."""
    (tmp_path / ".hidden").write_text("secret")
    (tmp_path / "visible.py").write_text("code")

    result = _read_workspace_files(tmp_path, show_hidden_files=False)
    names = [str(p) for p in result]
    assert "visible.py" in names
    assert ".hidden" not in names


def test_hidden_files_included_when_show_hidden(tmp_path: Path) -> None:
    """Hidden files appear when show_hidden_files=True."""
    (tmp_path / ".env").write_text("SECRET=1")
    (tmp_path / ".gitignore").write_text("*.pyc")
    (tmp_path / "visible.py").write_text("code")

    result = _read_workspace_files(tmp_path, show_hidden_files=True)
    names = [str(p) for p in result]
    assert "visible.py" in names
    assert ".env" in names
    assert ".gitignore" in names


def test_hidden_dirs_included_when_show_hidden(tmp_path: Path) -> None:
    """Files inside hidden directories appear when show_hidden_files=True."""
    github = tmp_path / ".github" / "workflows"
    github.mkdir(parents=True)
    (github / "ci.yml").write_text("name: CI")
    (tmp_path / "visible.py").write_text("code")

    result = _read_workspace_files(tmp_path, show_hidden_files=True)
    names = [str(p) for p in result]
    assert "visible.py" in names
    assert str(Path(".github", "workflows", "ci.yml")) in names


def test_git_dir_always_excluded(tmp_path: Path) -> None:
    """`.git/` directory is always excluded even when show_hidden_files=True."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("data")
    (tmp_path / ".env").write_text("SECRET=1")
    (tmp_path / "visible.py").write_text("code")

    result = _read_workspace_files(tmp_path, show_hidden_files=True)
    names = [str(p) for p in result]
    assert "visible.py" in names
    assert ".env" in names
    assert not any(".git/" in n or n == ".git" for n in names)


def test_git_file_excluded_in_worktree(tmp_path: Path) -> None:
    """.git file (worktree/submodule) is excluded even with show_hidden_files=True."""
    # In git worktrees/submodules, .git is a file, not a directory
    (tmp_path / ".git").write_text("gitdir: /some/path")
    (tmp_path / ".env").write_text("SECRET=1")
    (tmp_path / "visible.py").write_text("code")

    result = _read_workspace_files(tmp_path, show_hidden_files=True)
    names = [str(p) for p in result]
    assert "visible.py" in names
    assert ".env" in names
    assert ".git" not in names


def test_read_workspace_paths_hidden_included_when_show_hidden(tmp_path: Path) -> None:
    """_read_workspace_paths includes hidden files/dirs when show_hidden_files=True."""
    (tmp_path / ".env").write_text("SECRET=1")
    github = tmp_path / ".github"
    github.mkdir()
    (github / "ci.yml").write_text("name: CI")
    (tmp_path / "visible.py").write_text("code")

    result = _read_workspace_paths(tmp_path, show_hidden_files=True)
    rel_names = [str(p.relative_to(tmp_path)) for p in result]
    assert "visible.py" in rel_names
    assert ".env" in rel_names
    assert ".github" in rel_names


def test_read_workspace_paths_git_always_excluded(tmp_path: Path) -> None:
    """_read_workspace_paths always excludes .git even with show_hidden_files=True."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("data")
    (tmp_path / ".env").write_text("SECRET=1")

    result = _read_workspace_paths(tmp_path, show_hidden_files=True)
    rel_names = [str(p.relative_to(tmp_path)) for p in result]
    assert ".env" in rel_names
    assert not any(".git" in n for n in rel_names)


def test_read_workspace_paths_hidden_excluded_when_false(tmp_path: Path) -> None:
    """_read_workspace_paths excludes hidden files/dirs when show_hidden_files=False."""
    (tmp_path / ".env").write_text("SECRET=1")
    github = tmp_path / ".github"
    github.mkdir()
    (github / "ci.yml").write_text("name: CI")
    (tmp_path / "visible.py").write_text("code")

    result = _read_workspace_paths(tmp_path, show_hidden_files=False)
    rel_names = [str(p.relative_to(tmp_path)) for p in result]
    assert "visible.py" in rel_names
    assert ".env" not in rel_names
    assert ".github" not in rel_names


def test_relative_paths_returned(tmp_path: Path) -> None:
    """Returned paths are relative to workspace_path, not absolute."""
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "main.py").write_text("code")

    result = _read_workspace_files(tmp_path)
    assert all(not p.is_absolute() for p in result)
    assert Path("src/main.py") in result


def test_nested_files_included(tmp_path: Path) -> None:
    """Files nested in non-hidden subdirectories are included."""
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "deep.txt").write_text("content")

    result = _read_workspace_files(tmp_path)
    assert Path("a/b/deep.txt") in result


def test_empty_workspace_returns_empty(tmp_path: Path) -> None:
    """Empty workspace returns empty list."""
    result = _read_workspace_files(tmp_path)
    assert result == []


# ── Gitignore filtering tests (ripgrep-rs) ─────────────────────────────────────


def test_gitignored_files_excluded(git_workspace: Path) -> None:
    """Files matching .gitignore patterns are excluded with respect_gitignore=True."""
    (git_workspace / ".gitignore").write_text("*.log\n")
    (git_workspace / "app.py").write_text("code")
    (git_workspace / "debug.log").write_text("log data")

    result = _read_workspace_files(git_workspace, respect_gitignore=True)
    names = [str(p) for p in result]
    assert "app.py" in names
    assert "debug.log" not in names


def test_gitignored_dir_pruned(git_workspace: Path) -> None:
    """Directories matching .gitignore patterns are fully pruned."""
    (git_workspace / ".gitignore").write_text("build/\n")
    (git_workspace / "src").mkdir()
    (git_workspace / "src" / "main.py").write_text("code")
    build = git_workspace / "build" / "output"
    build.mkdir(parents=True)
    (build / "bundle.js").write_text("js")

    result = _read_workspace_files(git_workspace, respect_gitignore=True)
    names = [str(p) for p in result]
    assert "src/main.py" in names or str(Path("src/main.py")) in names
    assert not any("build" in n for n in names)


def test_gitignore_disabled_includes_all(git_workspace: Path) -> None:
    """With respect_gitignore=False, gitignored files are included."""
    (git_workspace / ".gitignore").write_text("*.log\n")
    (git_workspace / "app.py").write_text("code")
    (git_workspace / "debug.log").write_text("log data")

    result = _read_workspace_files(git_workspace, respect_gitignore=False)
    names = [str(p) for p in result]
    assert "app.py" in names
    assert "debug.log" in names


def test_nested_gitignore(git_workspace: Path) -> None:
    """Nested .gitignore files are respected."""
    (git_workspace / ".gitignore").write_text("*.log\n")
    src = git_workspace / "src"
    src.mkdir()
    (src / ".gitignore").write_text("*.tmp\n")
    (git_workspace / "app.py").write_text("code")
    (git_workspace / "debug.log").write_text("log")
    (src / "main.py").write_text("code")
    (src / "cache.tmp").write_text("temp")

    result = _read_workspace_files(git_workspace, respect_gitignore=True)
    names = [str(p) for p in result]
    assert "app.py" in names
    assert "debug.log" not in names
    assert str(Path("src/main.py")) in names
    assert str(Path("src/cache.tmp")) not in names


def test_respect_gitignore_without_gitignore_file(git_workspace: Path) -> None:
    """With respect_gitignore=True but no .gitignore, all files are returned."""
    (git_workspace / "app.py").write_text("code")
    (git_workspace / "data.txt").write_text("data")

    result = _read_workspace_files(git_workspace, respect_gitignore=True)
    names = [str(p) for p in result]
    assert "app.py" in names
    assert "data.txt" in names


def test_hidden_files_included_with_gitignore(git_workspace: Path) -> None:
    """Dotfiles are included when show_hidden_files=True even with gitignore."""
    (git_workspace / ".gitignore").write_text("*.log\n")
    (git_workspace / ".env").write_text("SECRET=1")
    (git_workspace / "app.py").write_text("code")
    (git_workspace / "debug.log").write_text("log")

    result = _read_workspace_files(
        git_workspace, show_hidden_files=True, respect_gitignore=True
    )
    names = [str(p) for p in result]
    assert ".env" in names
    assert "app.py" in names
    assert "debug.log" not in names


def test_gitignore_file_count_regression(git_workspace: Path) -> None:
    """Gitignore must reduce file count — regression guard."""
    (git_workspace / ".gitignore").write_text("generated/\n")
    gen = git_workspace / "generated"
    gen.mkdir()
    for i in range(50):
        (gen / f"file_{i}.txt").write_text(f"data {i}")
    (git_workspace / "src").mkdir()
    for i in range(5):
        (git_workspace / "src" / f"mod_{i}.py").write_text("code")

    with_gitignore = _read_workspace_files(git_workspace, respect_gitignore=True)
    without_gitignore = _read_workspace_files(git_workspace, respect_gitignore=False)

    assert len(with_gitignore) < len(without_gitignore)
    # generated/ files should be excluded
    assert not any("generated" in str(p) for p in with_gitignore)
    # src/ files should be present
    assert any("src" in str(p) for p in with_gitignore)


def test_read_workspace_paths_gitignore(git_workspace: Path) -> None:
    """_read_workspace_paths respects gitignore when enabled."""
    (git_workspace / ".gitignore").write_text("build/\n")
    (git_workspace / "src").mkdir()
    (git_workspace / "src" / "main.py").write_text("code")
    build = git_workspace / "build"
    build.mkdir()
    (build / "out.js").write_text("js")

    result = _read_workspace_paths(git_workspace, respect_gitignore=True)
    rel_names = [str(p.relative_to(git_workspace)) for p in result]
    assert "src" in rel_names or str(Path("src/main.py")) in [
        str(p.relative_to(git_workspace)) for p in result
    ]
    assert not any("build" in n for n in rel_names)


# ── OSError resilience tests ───────────────────────────────────────────────────


def test_read_workspace_directories_survives_oserror(tmp_path: Path) -> None:
    """_read_workspace_directories must not crash when os.walk raises OSError."""
    (tmp_path / "visible_dir").mkdir()

    real_walk = __import__("os").walk

    def walk_with_error(path, **kwargs):
        yield from real_walk(path, **kwargs)
        raise OSError(22, "The system cannot access the file")

    with patch("os.walk", walk_with_error):
        result = _read_workspace_directories(tmp_path)

    assert tmp_path in result
    assert tmp_path / "visible_dir" in result


def test_read_workspace_directories_onerror_suppresses(tmp_path: Path) -> None:
    """os.walk onerror callback should suppress per-directory errors."""
    (tmp_path / "ok_dir").mkdir()

    real_walk = __import__("os").walk

    def walk_with_onerror(path, **kwargs):
        onerror = kwargs.get("onerror")
        yield from real_walk(path)
        # Simulate a per-directory error via the onerror callback
        if onerror:
            onerror(OSError(13, "Permission denied"))

    with patch("os.walk", walk_with_onerror):
        result = _read_workspace_directories(tmp_path)

    assert tmp_path in result
    assert tmp_path / "ok_dir" in result


# ── Provider factory tests (commands.py lines 184-361) ───────────────────────


def test_create_file_command_provider_properties(tmp_path: Path) -> None:
    """create_create_file_or_dir_command_provider returns a correct Provider."""
    from textual.command import Provider

    from textual_code.commands import create_create_file_or_dir_command_provider

    def _noop(p: Path) -> None:
        pass

    callback = _noop
    file_cls = create_create_file_or_dir_command_provider(tmp_path, False, callback)
    dir_cls = create_create_file_or_dir_command_provider(tmp_path, True, callback)
    assert issubclass(file_cls, Provider)
    assert issubclass(dir_cls, Provider)
    # Verify the subclass defines is_dir property (from BaseCreatePathCommandProvider)
    assert hasattr(file_cls, "is_dir")
    assert hasattr(dir_cls, "is_dir")


def test_rg_scan_absolute_paths(tmp_path: Path) -> None:
    """_rg_scan with absolute=True returns absolute paths."""
    from textual_code.commands import _rg_scan

    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")
    result = _rg_scan(tmp_path, absolute=True)
    assert len(result) >= 1
    assert all(p.is_absolute() for p in result)


def test_rg_scan_include_dirs(tmp_path: Path) -> None:
    """_rg_scan with include_dirs=True includes directories."""
    from textual_code.commands import _rg_scan

    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "file.txt").write_text("hello", encoding="utf-8")
    result = _rg_scan(tmp_path, include_dirs=True, relative_to=str(tmp_path))
    names = [str(p) for p in result]
    assert "subdir" in names


def test_read_workspace_paths_returns_absolute(tmp_path: Path) -> None:
    """_read_workspace_paths returns absolute paths including directories."""
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "file.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "root.txt").write_text("root", encoding="utf-8")
    result = _read_workspace_paths(tmp_path)
    assert len(result) >= 2
    assert all(p.is_absolute() for p in result)
    # Should include directories
    dir_paths = [p for p in result if p.is_dir()]
    assert len(dir_paths) >= 1


# ── Provider integration tests via app actions ───────────────────────────────


async def test_new_file_palette_triggers_create_provider(tmp_path: Path) -> None:
    """action_new_file opens CommandPalette with CreatePathCommandProvider.

    Typing a filename triggers the provider's search() method, which covers
    BaseCreatePathCommandProvider.search (commands.py lines 322-333).
    """
    from textual.command import CommandPalette

    from tests.conftest import make_app

    (tmp_path / "existing.py").write_text("x = 1\n", encoding="utf-8")
    app = make_app(tmp_path, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.action_new_file()
        await pilot.wait_for_scheduled_animations()
        # CommandPalette should be the current screen
        assert isinstance(app.screen, CommandPalette)
        # Type a filename to trigger CreatePathCommandProvider.search()
        await pilot.press("t", "e", "s", "t", ".", "p", "y")
        await pilot.wait_for_scheduled_animations()


async def test_new_folder_palette_triggers_create_provider(tmp_path: Path) -> None:
    """action_new_folder opens CommandPalette with is_dir=True provider."""
    from textual.command import CommandPalette

    from tests.conftest import make_app

    app = make_app(tmp_path, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.action_new_folder()
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, CommandPalette)
        await pilot.press("n", "e", "w", "d", "i", "r")
        await pilot.wait_for_scheduled_animations()


async def test_delete_file_palette_opens_path_search(tmp_path: Path) -> None:
    """action_delete_file_or_directory opens PathSearchModal, triggering
    the PathActionCommandProvider via _push_path_search.
    """
    from tests.conftest import make_app, wait_for_condition
    from textual_code.modals import PathSearchModal

    (tmp_path / "target.py").write_text("x = 1\n", encoding="utf-8")
    app = make_app(tmp_path, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.action_delete_file_or_directory()
        await pilot.wait_for_scheduled_animations()
        # PathSearchModal should open
        await wait_for_condition(
            pilot,
            lambda: isinstance(app.screen, PathSearchModal),
            msg="PathSearchModal did not open",
        )


async def test_rename_file_palette_opens_path_search(tmp_path: Path) -> None:
    """action_rename_file_or_directory opens PathSearchModal."""
    from tests.conftest import make_app, wait_for_condition
    from textual_code.modals import PathSearchModal

    (tmp_path / "target.py").write_text("x = 1\n", encoding="utf-8")
    app = make_app(tmp_path, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.action_rename_file_or_directory()
        await pilot.wait_for_scheduled_animations()
        await wait_for_condition(
            pilot,
            lambda: isinstance(app.screen, PathSearchModal),
            msg="PathSearchModal did not open",
        )


async def test_move_file_palette_opens_path_search(tmp_path: Path) -> None:
    """action_move_file_or_directory opens PathSearchModal."""
    from tests.conftest import make_app, wait_for_condition
    from textual_code.modals import PathSearchModal

    (tmp_path / "target.py").write_text("x = 1\n", encoding="utf-8")
    app = make_app(tmp_path, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.action_move_file_or_directory()
        await pilot.wait_for_scheduled_animations()
        await wait_for_condition(
            pilot,
            lambda: isinstance(app.screen, PathSearchModal),
            msg="PathSearchModal did not open",
        )
