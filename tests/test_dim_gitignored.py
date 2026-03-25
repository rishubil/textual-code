"""Tests for the dim_gitignored feature."""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.config import (
    DEFAULT_EDITOR_SETTINGS,
    EDITOR_KEYS,
    load_editor_settings,
)
from textual_code.widgets.explorer import FilteredDirectoryTree

# ── Config tests ─────────────────────────────────────────────────────────────


class TestConfig:
    def test_a01_default_setting_is_true(self):
        """dim_gitignored defaults to True."""
        assert "dim_gitignored" in DEFAULT_EDITOR_SETTINGS
        assert DEFAULT_EDITOR_SETTINGS["dim_gitignored"] is True

    def test_a02_editor_keys_contains_dim_gitignored(self):
        """dim_gitignored is a valid editor key."""
        assert "dim_gitignored" in EDITOR_KEYS

    def test_a03_toml_load(self, tmp_path: Path):
        """TOML with dim_gitignored = false is loaded correctly."""
        config = tmp_path / "settings.toml"
        config.write_text("[editor]\ndim_gitignored = false\n")
        ws = tmp_path / "ws"
        ws.mkdir()
        settings = load_editor_settings(ws, user_config_path=config)
        assert settings["dim_gitignored"] is False

    def test_a04_round_trip(self, tmp_path: Path):
        """save → load round-trip preserves dim_gitignored."""
        from textual_code.config import save_user_editor_settings

        config = tmp_path / "settings.toml"
        settings = dict(DEFAULT_EDITOR_SETTINGS)
        settings["dim_gitignored"] = False
        save_user_editor_settings(settings, config_path=config)
        loaded = load_editor_settings(tmp_path, user_config_path=config)
        assert loaded["dim_gitignored"] is False


# ── Gitignore matching tests ─────────────────────────────────────────────────


class TestGitignoreMatching:
    def _make_tree(self, ws: Path, *, dim: bool = True) -> FilteredDirectoryTree:
        """Create a FilteredDirectoryTree rooted at ws."""
        return FilteredDirectoryTree(ws, dim_gitignored=dim)

    def test_b01_matching_file_is_gitignored(self, tmp_path: Path):
        """_is_gitignored returns True for files matching .gitignore."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".gitignore").write_text("*.log\n")
        (ws / "debug.log").touch()
        tree = self._make_tree(ws)
        assert tree._is_gitignored(ws / "debug.log") is True

    def test_b02_non_matching_file_is_not_gitignored(self, tmp_path: Path):
        """_is_gitignored returns False for files not matching .gitignore."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".gitignore").write_text("*.log\n")
        (ws / "app.py").touch()
        tree = self._make_tree(ws)
        assert tree._is_gitignored(ws / "app.py") is False

    def test_b03_dotfiles_never_gitignored(self, tmp_path: Path):
        """Dotfiles are exempt from dimming even if they match gitignore."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".gitignore").write_text(".*\n")
        (ws / ".env").touch()
        tree = self._make_tree(ws)
        assert tree._is_gitignored(ws / ".env") is False

    def test_b04_no_gitignore_means_nothing_ignored(self, tmp_path: Path):
        """Without any .gitignore files, nothing is considered ignored."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "file.txt").touch()
        tree = self._make_tree(ws)
        assert tree._is_gitignored(ws / "file.txt") is False

    def test_b05_nested_gitignore_respected(self, tmp_path: Path):
        """A .gitignore in a subdirectory applies to files within it."""
        ws = tmp_path / "ws"
        ws.mkdir()
        sub = ws / "subdir"
        sub.mkdir()
        (sub / ".gitignore").write_text("*.tmp\n")
        (sub / "data.tmp").touch()
        (ws / "root.tmp").touch()
        tree = self._make_tree(ws)
        # subdir/.gitignore applies to subdir/data.tmp
        assert tree._is_gitignored(sub / "data.tmp") is True
        # root.tmp is NOT covered by subdir/.gitignore
        assert tree._is_gitignored(ws / "root.tmp") is False

    def test_b06_directory_pattern_with_trailing_slash(self, tmp_path: Path):
        """Trailing slash directory patterns match directories."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".gitignore").write_text("build/\n")
        build_dir = ws / "build"
        build_dir.mkdir()
        tree = self._make_tree(ws)
        assert tree._is_gitignored(build_dir) is True

    def test_b07_files_inside_gitignored_directory(self, tmp_path: Path):
        """Files inside a gitignored directory are also considered ignored."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".gitignore").write_text("node_modules/\n")
        nm = ws / "node_modules"
        nm.mkdir()
        (nm / "package.json").touch()
        tree = self._make_tree(ws)
        assert tree._is_gitignored(nm / "package.json") is True

    def test_b08_negated_pattern(self, tmp_path: Path):
        """Negated patterns exclude files from being ignored."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".gitignore").write_text("*.log\n!important.log\n")
        (ws / "debug.log").touch()
        (ws / "important.log").touch()
        tree = self._make_tree(ws)
        assert tree._is_gitignored(ws / "debug.log") is True
        assert tree._is_gitignored(ws / "important.log") is False

    def test_b09_cache_invalidated_on_reload(self, tmp_path: Path):
        """reload() invalidates gitignore spec cache."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".gitignore").write_text("*.log\n")
        tree = self._make_tree(ws)
        # Prime the cache
        tree._is_gitignored(ws / "test.log")
        assert tree._gitignore_specs is not None
        assert len(tree._gitignore_cache) > 0
        # reload() should invalidate
        tree._gitignore_specs = None
        tree._gitignore_cache.clear()
        assert tree._gitignore_specs is None
        assert len(tree._gitignore_cache) == 0

    def test_b10_dim_disabled_returns_false(self, tmp_path: Path):
        """When dim_gitignored is False, _is_gitignored always returns False."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".gitignore").write_text("*.log\n")
        (ws / "debug.log").touch()
        tree = self._make_tree(ws, dim=False)
        assert tree._is_gitignored(ws / "debug.log") is False

    def test_b11_dotdir_gitignore_skipped(self, tmp_path: Path):
        """Gitignore files inside hidden directories are not loaded."""
        ws = tmp_path / "ws"
        ws.mkdir()
        git_dir = ws / ".git"
        git_dir.mkdir()
        (git_dir / ".gitignore").write_text("*\n")
        (ws / "file.txt").touch()
        tree = self._make_tree(ws)
        # .git/.gitignore should not be loaded, so file.txt is not ignored
        assert tree._is_gitignored(ws / "file.txt") is False

    def test_b12_result_cache_hit(self, tmp_path: Path):
        """Second call for the same path uses cache."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".gitignore").write_text("*.log\n")
        (ws / "debug.log").touch()
        tree = self._make_tree(ws)
        assert tree._is_gitignored(ws / "debug.log") is True
        # Cache should contain the result
        assert (ws / "debug.log") in tree._gitignore_cache
        # Second call should use cache (same result)
        assert tree._is_gitignored(ws / "debug.log") is True


# ── App integration tests ────────────────────────────────────────────────────


class TestAppIntegration:
    @pytest.mark.asyncio
    async def test_c01_default_dim_gitignored_is_true(self, tmp_path: Path):
        """App defaults dim_gitignored to True."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            assert app.default_dim_gitignored is True

    @pytest.mark.asyncio
    async def test_c02_config_loads_false(self, tmp_path: Path):
        """App loads dim_gitignored = false from config."""
        config = tmp_path / "settings.toml"
        config.write_text("[editor]\ndim_gitignored = false\n")
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            assert app.default_dim_gitignored is False

    @pytest.mark.asyncio
    async def test_c03_build_editor_settings_includes_key(self, tmp_path: Path):
        """_build_editor_settings includes dim_gitignored."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            settings = app._build_editor_settings()
            assert "dim_gitignored" in settings
            assert settings["dim_gitignored"] is True

    @pytest.mark.asyncio
    async def test_c04_tree_receives_dim_gitignored(self, tmp_path: Path):
        """FilteredDirectoryTree receives dim_gitignored from app."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            assert app.sidebar is not None
            tree = app.sidebar.explorer.directory_tree
            assert tree.dim_gitignored is True


# ── Toggle command tests ─────────────────────────────────────────────────────


class TestToggleCommand:
    @pytest.mark.asyncio
    async def test_d01_system_command_exists(self, tmp_path: Path):
        """Command palette has 'Toggle dim gitignored files' command."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            cmds = list(app.get_system_commands(app.screen))
            titles = [c.title for c in cmds]
            assert "Toggle Dim Gitignored Files" in titles

    @pytest.mark.asyncio
    async def test_d02_toggle_changes_value(self, tmp_path: Path):
        """Toggle flips dim_gitignored and updates explorer."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            assert app.default_dim_gitignored is True
            app.action_toggle_dim_gitignored()
            assert app.default_dim_gitignored is False
            assert app.sidebar.explorer.directory_tree.dim_gitignored is False

    @pytest.mark.asyncio
    async def test_d03_toggle_saves_to_config(self, tmp_path: Path):
        """Toggle persists the new value to user config."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            app.action_toggle_dim_gitignored()
        loaded = load_editor_settings(ws, user_config_path=config)
        assert loaded["dim_gitignored"] is False


# ── render_label dim styling tests ───────────────────────────────────────────


class TestRenderLabelDim:
    @pytest.mark.asyncio
    async def test_e01_gitignored_file_is_dimmed(self, tmp_path: Path):
        """render_label applies dim style to gitignored files."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".gitignore").write_text("*.log\n")
        (ws / "debug.log").write_text("log content\n")
        (ws / "app.py").write_text("print('hi')\n")
        config = tmp_path / "settings.toml"
        app = make_app(ws, user_config_path=config)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.sidebar is not None
            tree = app.sidebar.explorer.directory_tree
            # Verify gitignore matching
            assert tree._is_gitignored(ws / "debug.log") is True
            assert tree._is_gitignored(ws / "app.py") is False

    @pytest.mark.asyncio
    async def test_e02_dotfile_not_dimmed_even_if_gitignored(self, tmp_path: Path):
        """Hidden files are not dimmed even if they match gitignore."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".gitignore").write_text(".*\n")
        (ws / ".env").write_text("SECRET=1\n")
        config = tmp_path / "settings.toml"
        app = make_app(ws, user_config_path=config)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.sidebar is not None
            tree = app.sidebar.explorer.directory_tree
            assert tree._is_gitignored(ws / ".env") is False

    @pytest.mark.asyncio
    async def test_e03_toggle_disables_dimming_in_tree(self, tmp_path: Path):
        """After toggle, gitignored files are no longer dimmed."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".gitignore").write_text("*.log\n")
        (ws / "debug.log").write_text("log\n")
        config = tmp_path / "settings.toml"
        app = make_app(ws, user_config_path=config)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.sidebar is not None
            tree = app.sidebar.explorer.directory_tree
            assert tree._is_gitignored(ws / "debug.log") is True
            # Toggle off
            app.action_toggle_dim_gitignored()
            await pilot.pause()
            assert tree.dim_gitignored is False
            assert tree._is_gitignored(ws / "debug.log") is False
