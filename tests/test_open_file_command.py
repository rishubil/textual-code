"""Tests for OpenFileCommandProvider file enumeration (commands.py)."""

from __future__ import annotations

from pathlib import Path

from textual_code.commands import _read_workspace_files


def test_directories_excluded(tmp_path: Path) -> None:
    """Only files are returned — directories are excluded."""
    (tmp_path / "subdir").mkdir()
    (tmp_path / "file.txt").write_text("content")

    result = _read_workspace_files(tmp_path)
    names = [str(p) for p in result]
    assert "file.txt" in names
    assert "subdir" not in names


def test_hidden_dir_files_excluded(tmp_path: Path) -> None:
    """Files inside hidden directories are excluded."""
    hidden = tmp_path / ".git"
    hidden.mkdir()
    (hidden / "config").write_text("data")
    (tmp_path / "visible.txt").write_text("data")

    result = _read_workspace_files(tmp_path)
    names = [str(p) for p in result]
    assert "visible.txt" in names
    assert not any(".git" in n for n in names)


def test_hidden_files_excluded(tmp_path: Path) -> None:
    """Hidden files (dot-prefixed) are excluded."""
    (tmp_path / ".hidden").write_text("secret")
    (tmp_path / "visible.py").write_text("code")

    result = _read_workspace_files(tmp_path)
    names = [str(p) for p in result]
    assert "visible.py" in names
    assert ".hidden" not in names


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
