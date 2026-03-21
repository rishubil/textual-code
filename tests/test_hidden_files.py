"""Tests for the show_hidden_files feature."""

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
    def test_a01_default_setting_is_true(self):
        """show_hidden_files defaults to True."""
        assert "show_hidden_files" in DEFAULT_EDITOR_SETTINGS
        assert DEFAULT_EDITOR_SETTINGS["show_hidden_files"] is True

    def test_a02_editor_keys_contains_show_hidden_files(self):
        """show_hidden_files is a valid editor key."""
        assert "show_hidden_files" in EDITOR_KEYS

    def test_a03_toml_load(self, tmp_path: Path):
        """TOML with show_hidden_files = true is loaded correctly."""
        config = tmp_path / "settings.toml"
        config.write_text("[editor]\nshow_hidden_files = true\n")
        ws = tmp_path / "ws"
        ws.mkdir()
        settings = load_editor_settings(ws, user_config_path=config)
        assert settings["show_hidden_files"] is True

    def test_a04_round_trip(self, tmp_path: Path):
        """save → load round-trip preserves show_hidden_files."""
        from textual_code.config import save_user_editor_settings

        config = tmp_path / "settings.toml"
        settings = dict(DEFAULT_EDITOR_SETTINGS)
        settings["show_hidden_files"] = True
        save_user_editor_settings(settings, config_path=config)
        loaded = load_editor_settings(tmp_path, user_config_path=config)
        assert loaded["show_hidden_files"] is True


# ── FilteredDirectoryTree tests ──────────────────────────────────────────────


class TestFilteredDirectoryTree:
    def test_b01_filters_dotfiles_when_disabled(self):
        """filter_paths hides dotfiles when show_hidden_files is False."""
        from textual_code.widgets.explorer import FilteredDirectoryTree

        tree = FilteredDirectoryTree("/tmp", show_hidden_files=False)
        paths = [Path("/a/.hidden"), Path("/a/visible.py"), Path("/a/.git")]
        result = tree.filter_paths(paths)
        assert list(result) == [Path("/a/visible.py")]

    def test_b02_shows_all_when_enabled(self):
        """filter_paths returns all paths when show_hidden_files is True."""
        from textual_code.widgets.explorer import FilteredDirectoryTree

        tree = FilteredDirectoryTree("/tmp", show_hidden_files=True)
        paths = [Path("/a/.hidden"), Path("/a/visible.py")]
        result = tree.filter_paths(paths)
        assert list(result) == paths

    def test_b03_edge_cases(self):
        """Edge cases: empty list, double-dot, normal files only."""
        from textual_code.widgets.explorer import FilteredDirectoryTree

        tree = FilteredDirectoryTree("/tmp", show_hidden_files=False)
        # empty list
        assert list(tree.filter_paths([])) == []
        # double-dot prefix is still hidden
        assert list(tree.filter_paths([Path("/a/..hidden")])) == []
        # normal files pass through
        normal = [Path("/a/file.txt"), Path("/a/readme")]
        assert list(tree.filter_paths(normal)) == normal


# ── App integration tests ────────────────────────────────────────────────────


class TestAppIntegration:
    @pytest.mark.asyncio
    async def test_c01_default_show_hidden_files_is_true(self, tmp_path: Path):
        """App defaults show_hidden_files to True."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            assert app.default_show_hidden_files is True

    @pytest.mark.asyncio
    async def test_c02_config_loads_true(self, tmp_path: Path):
        """App loads show_hidden_files = true from config."""
        config = tmp_path / "settings.toml"
        config.write_text("[editor]\nshow_hidden_files = true\n")
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            assert app.default_show_hidden_files is True

    @pytest.mark.asyncio
    async def test_c03_build_editor_settings_includes_key(self, tmp_path: Path):
        """_build_editor_settings includes show_hidden_files."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            settings = app._build_editor_settings()
            assert "show_hidden_files" in settings
            assert settings["show_hidden_files"] is True


class TestToggleCommand:
    @pytest.mark.asyncio
    async def test_d01_system_command_exists(self, tmp_path: Path):
        """Command palette has 'Toggle hidden files' command."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            cmds = list(app.get_system_commands(app.screen))
            titles = [c.title for c in cmds]
            assert "Toggle hidden files" in titles

    @pytest.mark.asyncio
    async def test_d02_toggle_changes_value(self, tmp_path: Path):
        """Toggle flips show_hidden_files and updates explorer."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            assert app.default_show_hidden_files is True
            app._toggle_hidden_files_cmd()
            assert app.default_show_hidden_files is False
            assert app.sidebar.explorer.directory_tree.show_hidden_files is False

    @pytest.mark.asyncio
    async def test_d03_toggle_saves_to_config(self, tmp_path: Path):
        """Toggle persists the new value to user config."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            app._toggle_hidden_files_cmd()
        loaded = load_editor_settings(ws, user_config_path=config)
        assert loaded["show_hidden_files"] is False


class TestExplorerIntegration:
    @pytest.mark.asyncio
    async def test_e01_hidden_file_visibility(self, tmp_path: Path):
        """Hidden files are shown by default, hidden after toggle."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "hello.py").write_text("print('hi')\n")
        (ws / ".hidden").write_text("secret\n")
        config = tmp_path / "settings.toml"

        app = make_app(ws, user_config_path=config)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.sidebar is not None
            tree = app.sidebar.explorer.directory_tree
            assert tree.show_hidden_files is True

            # Toggle off
            app._toggle_hidden_files_cmd()
            await pilot.pause()
            assert tree.show_hidden_files is False
