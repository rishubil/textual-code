"""Tests for file I/O error handling across the codebase (issue #9)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from textual_code.config import (
    save_keybindings,
    save_project_editor_settings,
    save_user_editor_settings,
)
from textual_code.widgets.code_editor import (
    _parse_editorconfig_file,
    _read_editorconfig,
)

# ── config save functions ─────────────────────────────────────────────────────


def test_save_keybindings_survives_oserror(tmp_path: Path) -> None:
    """save_keybindings returns False when write_text raises OSError."""
    bad_path = tmp_path / "readonly" / "keybindings.toml"

    with patch.object(Path, "write_text", side_effect=OSError("disk full")):
        result = save_keybindings({"action": "ctrl+s"}, bad_path)

    assert result is False


def test_save_keybindings_succeeds(tmp_path: Path) -> None:
    """save_keybindings returns True on success."""
    path = tmp_path / "keybindings.toml"
    result = save_keybindings({"action": "ctrl+s"}, path)
    assert result is True
    assert path.exists()


def test_save_user_editor_settings_survives_oserror(tmp_path: Path) -> None:
    """save_user_editor_settings returns False on I/O error."""
    bad_path = tmp_path / "readonly" / "settings.toml"

    with patch.object(Path, "write_text", side_effect=OSError("disk full")):
        result = save_user_editor_settings({"indent_size": 4}, bad_path)

    assert result is False


def test_save_user_editor_settings_succeeds(tmp_path: Path) -> None:
    """save_user_editor_settings returns True on success."""
    path = tmp_path / "settings.toml"
    result = save_user_editor_settings({"indent_size": 4}, path)
    assert result is True
    assert path.exists()


def test_save_project_editor_settings_survives_oserror(tmp_path: Path) -> None:
    """save_project_editor_settings returns False on I/O error."""
    with patch.object(Path, "write_text", side_effect=OSError("disk full")):
        result = save_project_editor_settings({"indent_size": 4}, tmp_path)

    assert result is False


def test_save_project_editor_settings_succeeds(tmp_path: Path) -> None:
    """save_project_editor_settings returns True on success."""
    result = save_project_editor_settings({"indent_size": 4}, tmp_path)
    assert result is True


# ── editorconfig error handling ───────────────────────────────────────────────


def test_parse_editorconfig_survives_read_oserror(tmp_path: Path) -> None:
    """_parse_editorconfig_file returns empty when read_text raises OSError."""
    ec_file = tmp_path / ".editorconfig"
    ec_file.write_text("[*]\nindent_size = 4\n")
    target = tmp_path / "test.py"

    with patch.object(Path, "read_text", side_effect=OSError("permission denied")):
        is_root, props = _parse_editorconfig_file(ec_file, target)

    assert is_root is False
    assert props == {}


def test_read_editorconfig_survives_is_file_oserror(tmp_path: Path) -> None:
    """_read_editorconfig skips dirs where is_file() raises OSError."""
    target = tmp_path / "test.py"
    target.write_text("")

    real_is_file = Path.is_file

    def patched_is_file(self):
        if self.name == ".editorconfig":
            raise OSError(22, "cannot access")
        return real_is_file(self)

    with patch.object(Path, "is_file", patched_is_file):
        props, searched_dirs = _read_editorconfig(target)

    # Should return empty props without crashing
    assert props == {}
    assert len(searched_dirs) > 0
