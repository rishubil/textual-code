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
