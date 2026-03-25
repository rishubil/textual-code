"""Tests for the dim_hidden_files feature."""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.config import (
    DEFAULT_EDITOR_SETTINGS,
    EDITOR_KEYS,
    load_editor_settings,
)

# ── Config tests ─────────────────────────────────────────────────────────────


class TestConfig:
    def test_a01_default_setting_is_false(self):
        """dim_hidden_files defaults to False."""
        assert "dim_hidden_files" in DEFAULT_EDITOR_SETTINGS
        assert DEFAULT_EDITOR_SETTINGS["dim_hidden_files"] is False

    def test_a02_editor_keys_contains_dim_hidden_files(self):
        """dim_hidden_files is a valid editor key."""
        assert "dim_hidden_files" in EDITOR_KEYS

    def test_a03_toml_load(self, tmp_path: Path):
        """TOML with dim_hidden_files = true is loaded correctly."""
        config = tmp_path / "settings.toml"
        config.write_text("[editor]\ndim_hidden_files = true\n")
        ws = tmp_path / "ws"
        ws.mkdir()
        settings = load_editor_settings(ws, user_config_path=config)
        assert settings["dim_hidden_files"] is True

    def test_a04_round_trip(self, tmp_path: Path):
        """save → load round-trip preserves dim_hidden_files."""
        from textual_code.config import save_user_editor_settings

        config = tmp_path / "settings.toml"
        settings = dict(DEFAULT_EDITOR_SETTINGS)
        settings["dim_hidden_files"] = True
        save_user_editor_settings(settings, config_path=config)
        loaded = load_editor_settings(tmp_path, user_config_path=config)
        assert loaded["dim_hidden_files"] is True


# ── App integration tests ────────────────────────────────────────────────────


class TestAppIntegration:
    @pytest.mark.asyncio
    async def test_c01_default_dim_hidden_files_is_false(self, tmp_path: Path):
        """App defaults dim_hidden_files to False."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            assert app.default_dim_hidden_files is False

    @pytest.mark.asyncio
    async def test_c02_config_loads_true(self, tmp_path: Path):
        """App loads dim_hidden_files = true from config."""
        config = tmp_path / "settings.toml"
        config.write_text("[editor]\ndim_hidden_files = true\n")
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            assert app.default_dim_hidden_files is True

    @pytest.mark.asyncio
    async def test_c03_build_editor_settings_includes_key(self, tmp_path: Path):
        """_build_editor_settings includes dim_hidden_files."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            settings = app._build_editor_settings()
            assert "dim_hidden_files" in settings
            assert settings["dim_hidden_files"] is False


# ── Toggle command tests ─────────────────────────────────────────────────────


class TestToggleCommand:
    @pytest.mark.asyncio
    async def test_d01_system_command_exists(self, tmp_path: Path):
        """Command palette has 'Toggle dim hidden files' command."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            cmds = list(app.get_system_commands(app.screen))
            titles = [c.title for c in cmds]
            assert "Toggle Dim Hidden Files" in titles

    @pytest.mark.asyncio
    async def test_d02_toggle_changes_value(self, tmp_path: Path):
        """Toggle flips dim_hidden_files and updates explorer."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            assert app.default_dim_hidden_files is False
            app.action_toggle_dim_hidden_files()
            assert app.default_dim_hidden_files is True
            assert app.sidebar.explorer.directory_tree.dim_hidden_files is True

    @pytest.mark.asyncio
    async def test_d03_toggle_saves_to_config(self, tmp_path: Path):
        """Toggle persists the new value to user config."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            app.action_toggle_dim_hidden_files()
        loaded = load_editor_settings(ws, user_config_path=config)
        assert loaded["dim_hidden_files"] is True


# ── Feature interaction test ─────────────────────────────────────────────────


class TestFeatureInteraction:
    @pytest.mark.asyncio
    async def test_e01_dim_hidden_and_gitignored_coexist(self, tmp_path: Path):
        """Both dim_hidden_files and dim_gitignored can be active.

        Dotfiles should be dimmed via directory-tree--hidden only,
        not via directory-tree--gitignored (dotfiles are exempt from gitignore dimming).
        """
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".gitignore").write_text("*.log\n")
        (ws / ".hidden_file").write_text("hidden\n")
        (ws / "debug.log").write_text("log\n")
        config = tmp_path / "settings.toml"
        config.write_text("[editor]\ndim_hidden_files = true\ndim_gitignored = true\n")
        app = make_app(ws, user_config_path=config)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.sidebar is not None
            tree = app.sidebar.explorer.directory_tree
            # Dotfile is NOT gitignored (exempt)
            assert tree._is_gitignored(ws / ".hidden_file") is False
            # But it IS a hidden file that should be dimmed
            assert tree.dim_hidden_files is True
            # Regular gitignored file is still gitignored
            assert tree._is_gitignored(ws / "debug.log") is True
