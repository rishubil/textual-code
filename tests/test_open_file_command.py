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


# ── OSError resilience tests ───────────────────────────────────────────────────


def _rglob_with_oserror(real_rglob):
    """Wrap Path.rglob so it yields one valid entry then raises OSError."""

    def patched_rglob(self, pattern):
        gen = real_rglob(self, pattern)
        # Yield some real entries, then simulate a mid-iteration OSError
        # (as happens on Windows with inaccessible files)
        yield from gen
        raise OSError(22, "The system cannot access the file")

    return patched_rglob


def test_read_workspace_files_survives_oserror(tmp_path: Path) -> None:
    """_read_workspace_files must not crash when rglob raises OSError."""
    (tmp_path / "ok.txt").write_text("visible")

    with patch.object(Path, "rglob", _rglob_with_oserror(Path.rglob)):
        result = _read_workspace_files(tmp_path)

    names = [str(p) for p in result]
    assert "ok.txt" in names


def test_read_workspace_paths_survives_oserror(tmp_path: Path) -> None:
    """_read_workspace_paths must not crash when rglob raises OSError."""
    (tmp_path / "ok.txt").write_text("visible")

    with patch.object(Path, "rglob", _rglob_with_oserror(Path.rglob)):
        result = _read_workspace_paths(tmp_path)

    assert any(str(p).endswith("ok.txt") for p in result)


def test_read_workspace_files_survives_is_file_oserror(tmp_path: Path) -> None:
    """_read_workspace_files must skip entries where is_file() raises OSError."""
    (tmp_path / "ok.txt").write_text("visible")
    (tmp_path / "bad.txt").write_text("inaccessible")

    real_is_file = Path.is_file

    def patched_is_file(self):
        if self.name == "bad.txt":
            raise OSError(22, "The system cannot access the file")
        return real_is_file(self)

    with patch.object(Path, "is_file", patched_is_file):
        result = _read_workspace_files(tmp_path)

    names = [str(p) for p in result]
    assert "ok.txt" in names
    assert "bad.txt" not in names


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
