"""Tests for load_file_for_editor helper function."""

from __future__ import annotations

from pathlib import Path

from textual_code.widgets.code_editor_helpers import (
    FileLoadResult,
    load_file_for_editor,
)


def test_load_file_for_editor_utf8(tmp_path: Path) -> None:
    """Reads UTF-8 file and returns correct text/encoding."""
    f = tmp_path / "hello.py"
    f.write_text("print('hello')\n", encoding="utf-8")

    result = load_file_for_editor(f)

    assert isinstance(result, FileLoadResult)
    assert result.text == "print('hello')\n"
    assert result.encoding == "utf-8"
    assert result.line_ending == "lf"
    assert result.file_mtime is not None
    assert result.error is None


def test_load_file_for_editor_crlf(tmp_path: Path) -> None:
    """Detects CRLF line endings and normalizes text."""
    f = tmp_path / "win.txt"
    f.write_bytes(b"line1\r\nline2\r\n")

    result = load_file_for_editor(f)

    assert result.line_ending == "crlf"
    assert result.text == "line1\nline2\n"  # normalized to LF


def test_load_file_for_editor_editorconfig(tmp_path: Path) -> None:
    """Picks up EditorConfig settings."""
    ec = tmp_path / ".editorconfig"
    ec.write_text("[*.py]\nindent_style = tab\nindent_size = 2\nroot = true\n")
    f = tmp_path / "test.py"
    f.write_text("x = 1\n")

    result = load_file_for_editor(f)

    assert result.editorconfig.get("indent_style") == "tab"
    assert result.editorconfig.get("indent_size") == "2"


def test_load_file_for_editor_bom_removed(tmp_path: Path) -> None:
    """BOM character is stripped from the text."""
    f = tmp_path / "bom.txt"
    f.write_bytes(b"\xef\xbb\xbfhello\n")

    result = load_file_for_editor(f)

    assert not result.text.startswith("\ufeff")
    assert result.text == "hello\n"


def test_load_file_for_editor_read_error(tmp_path: Path) -> None:
    """Non-existent file returns error string and empty text."""
    f = tmp_path / "nonexistent.txt"

    result = load_file_for_editor(f)

    assert result.error is not None
    assert result.text == ""
