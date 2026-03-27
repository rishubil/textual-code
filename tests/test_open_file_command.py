"""Tests for OpenFileCommandProvider file enumeration (commands.py)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from textual_code.commands import (
    _read_workspace_directories,
    _read_workspace_files,
    _read_workspace_paths,
)


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


# ── OSError resilience tests ───────────────────────────────────────────────────


def test_read_workspace_files_survives_walk_onerror(tmp_path: Path) -> None:
    """_read_workspace_files must not crash when os.walk encounters errors."""
    (tmp_path / "ok.txt").write_text("visible")

    real_walk = __import__("os").walk

    def walk_with_onerror(path, **kwargs):
        onerror = kwargs.get("onerror")
        yield from real_walk(path, **kwargs)
        if onerror:
            onerror(OSError(13, "Permission denied"))

    with patch("os.walk", walk_with_onerror):
        result = _read_workspace_files(tmp_path)

    names = [str(p) for p in result]
    assert "ok.txt" in names


def test_read_workspace_paths_survives_walk_onerror(tmp_path: Path) -> None:
    """_read_workspace_paths must not crash when os.walk encounters errors."""
    (tmp_path / "ok.txt").write_text("visible")

    real_walk = __import__("os").walk

    def walk_with_onerror(path, **kwargs):
        onerror = kwargs.get("onerror")
        yield from real_walk(path, **kwargs)
        if onerror:
            onerror(OSError(13, "Permission denied"))

    with patch("os.walk", walk_with_onerror):
        result = _read_workspace_paths(tmp_path)

    assert any(str(p).endswith("ok.txt") for p in result)


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
