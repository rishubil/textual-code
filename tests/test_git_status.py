"""Tests for the git status highlighting feature in the Explorer."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.conftest import init_git_repo, make_app, requires_git
from textual_code.config import (
    DEFAULT_EDITOR_SETTINGS,
    EDITOR_KEYS,
    load_editor_settings,
)
from textual_code.widgets.explorer import (
    FilteredDirectoryTree,
    _parse_git_status_output,
)

# ── Config tests ─────────────────────────────────────────────────────────────


class TestConfig:
    def test_a01_default_setting_is_true(self):
        """show_git_status defaults to True."""
        assert "show_git_status" in DEFAULT_EDITOR_SETTINGS
        assert DEFAULT_EDITOR_SETTINGS["show_git_status"] is True

    def test_a02_editor_keys_contains_show_git_status(self):
        """show_git_status is a valid editor key."""
        assert "show_git_status" in EDITOR_KEYS

    def test_a03_toml_load(self, tmp_path: Path):
        """TOML with show_git_status = false is loaded correctly."""
        config = tmp_path / "settings.toml"
        config.write_text("[editor]\nshow_git_status = false\n")
        ws = tmp_path / "ws"
        ws.mkdir()
        settings = load_editor_settings(ws, user_config_path=config)
        assert settings["show_git_status"] is False

    def test_a04_round_trip(self, tmp_path: Path):
        """save -> load round-trip preserves show_git_status."""
        from textual_code.config import save_user_editor_settings

        config = tmp_path / "settings.toml"
        settings = dict(DEFAULT_EDITOR_SETTINGS)
        settings["show_git_status"] = False
        save_user_editor_settings(settings, config_path=config)
        loaded = load_editor_settings(tmp_path, user_config_path=config)
        assert loaded["show_git_status"] is False


# ── Parser unit tests (pure function, no git needed) ─────────────────────────


class TestParseGitStatusOutput:
    def test_b01_modified_file(self, tmp_path: Path):
        """Modified file is parsed as 'modified'."""
        ws = tmp_path / "ws"
        ws.mkdir()
        # git status --porcelain -z output: " M file.py\0"
        stdout = " M file.py\0"
        result = _parse_git_status_output(stdout, ws)
        assert result.status_map[ws / "file.py"] == "modified"

    def test_b02_untracked_file(self, tmp_path: Path):
        """Untracked file is parsed as 'untracked'."""
        ws = tmp_path / "ws"
        ws.mkdir()
        stdout = "?? newfile.py\0"
        result = _parse_git_status_output(stdout, ws)
        assert result.status_map[ws / "newfile.py"] == "untracked"

    def test_b03_staged_file(self, tmp_path: Path):
        """Staged file (added) is parsed as 'modified'."""
        ws = tmp_path / "ws"
        ws.mkdir()
        stdout = "A  staged.py\0"
        result = _parse_git_status_output(stdout, ws)
        assert result.status_map[ws / "staged.py"] == "modified"

    def test_b04_renamed_file(self, tmp_path: Path):
        """Renamed file is parsed correctly from NUL-separated -z output."""
        ws = tmp_path / "ws"
        ws.mkdir()
        # With -z, renames are: "R  old.py\0new.py\0"
        stdout = "R  old.py\0new.py\0"
        result = _parse_git_status_output(stdout, ws)
        assert result.status_map[ws / "new.py"] == "modified"

    def test_b05_folder_propagation(self, tmp_path: Path):
        """Parent folders inherit status from children."""
        ws = tmp_path / "ws"
        ws.mkdir()
        stdout = " M src/utils/helper.py\0"
        result = _parse_git_status_output(stdout, ws)
        assert result.status_map[ws / "src" / "utils" / "helper.py"] == "modified"
        assert result.status_map[ws / "src" / "utils"] == "modified"
        assert result.status_map[ws / "src"] == "modified"

    def test_b06_folder_propagation_highest_priority(self, tmp_path: Path):
        """Folder gets the highest-priority status among children."""
        ws = tmp_path / "ws"
        ws.mkdir()
        # One untracked, one modified in same dir
        stdout = "?? src/new.py\0 M src/old.py\0"
        result = _parse_git_status_output(stdout, ws)
        # modified > untracked
        assert result.status_map[ws / "src"] == "modified"

    def test_b07_untracked_directory(self, tmp_path: Path):
        """Untracked directory entry (from -unormal) stores dir in untracked_dirs."""
        ws = tmp_path / "ws"
        ws.mkdir()
        # -unormal shows untracked dirs with trailing /
        stdout = "?? newdir/\0"
        result = _parse_git_status_output(stdout, ws)
        assert (ws / "newdir") in result.untracked_dirs

    def test_b08_empty_output(self, tmp_path: Path):
        """Empty output produces empty result."""
        ws = tmp_path / "ws"
        ws.mkdir()
        result = _parse_git_status_output("", ws)
        assert result.status_map == {}
        assert result.untracked_dirs == set()

    def test_b09_unparseable_entry_skipped(self, tmp_path: Path):
        """Entries too short to parse are skipped gracefully."""
        ws = tmp_path / "ws"
        ws.mkdir()
        # "X" is too short (< 4 chars), should be skipped
        stdout = "X\0 M valid.py\0"
        result = _parse_git_status_output(stdout, ws)
        assert ws / "valid.py" in result.status_map
        assert len(result.status_map) == 1  # only valid.py, no garbage

    def test_b10_multiple_statuses(self, tmp_path: Path):
        """Multiple files with different statuses parsed correctly."""
        ws = tmp_path / "ws"
        ws.mkdir()
        stdout = " M modified.py\0?? untracked.py\0A  added.py\0"
        result = _parse_git_status_output(stdout, ws)
        assert result.status_map[ws / "modified.py"] == "modified"
        assert result.status_map[ws / "untracked.py"] == "untracked"
        assert result.status_map[ws / "added.py"] == "modified"

    def test_b11_deleted_file(self, tmp_path: Path):
        """Deleted file is parsed as 'modified' (tracked change)."""
        ws = tmp_path / "ws"
        ws.mkdir()
        stdout = " D deleted.py\0"
        result = _parse_git_status_output(stdout, ws)
        assert result.status_map[ws / "deleted.py"] == "modified"


# ── Integration tests (real git repo) ────────────────────────────────────────


@requires_git
class TestGitStatusIntegration:
    def _make_tree(
        self, ws: Path, *, show_git_status: bool = True
    ) -> FilteredDirectoryTree:
        return FilteredDirectoryTree(ws, show_git_status=show_git_status)

    def test_c01_modified_file_detected(self, tmp_path: Path):
        """_get_git_status returns 'modified' for a modified tracked file."""
        ws = tmp_path / "ws"
        ws.mkdir()
        init_git_repo(ws)
        (ws / "committed.py").write_text("# changed\n")
        tree = self._make_tree(ws)
        assert tree._get_git_status(ws / "committed.py") == "modified"

    def test_c02_untracked_file_detected(self, tmp_path: Path):
        """_get_git_status returns 'untracked' for a new untracked file."""
        ws = tmp_path / "ws"
        ws.mkdir()
        init_git_repo(ws)
        (ws / "newfile.py").write_text("# new\n")
        tree = self._make_tree(ws)
        assert tree._get_git_status(ws / "newfile.py") == "untracked"

    def test_c03_clean_file_returns_none(self, tmp_path: Path):
        """_get_git_status returns None for a clean tracked file."""
        ws = tmp_path / "ws"
        ws.mkdir()
        init_git_repo(ws)
        tree = self._make_tree(ws)
        assert tree._get_git_status(ws / "committed.py") is None

    def test_c04_folder_with_modified_child(self, tmp_path: Path):
        """Folder containing a modified file gets 'modified' status."""
        ws = tmp_path / "ws"
        ws.mkdir()
        init_git_repo(ws)
        subdir = ws / "src"
        subdir.mkdir()
        (subdir / "app.py").write_text("# new file\n")
        subprocess.run(
            ["git", "add", "src/app.py"],
            cwd=ws,
            check=True,
            capture_output=True,
        )
        tree = self._make_tree(ws)
        assert tree._get_git_status(subdir) == "modified"

    def test_c05_no_git_dir_returns_none(self, tmp_path: Path):
        """Without .git directory, all files return None."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "file.py").write_text("# hello\n")
        tree = self._make_tree(ws)
        assert tree._get_git_status(ws / "file.py") is None

    def test_c06_show_git_status_false_returns_none(self, tmp_path: Path):
        """When show_git_status is False, all files return None."""
        ws = tmp_path / "ws"
        ws.mkdir()
        init_git_repo(ws)
        (ws / "committed.py").write_text("# changed\n")
        tree = self._make_tree(ws, show_git_status=False)
        assert tree._get_git_status(ws / "committed.py") is None

    def test_c07_cache_invalidated_on_reload(self, tmp_path: Path):
        """reload() invalidates git status cache."""
        ws = tmp_path / "ws"
        ws.mkdir()
        init_git_repo(ws)
        (ws / "committed.py").write_text("# changed\n")
        tree = self._make_tree(ws)
        # Prime the cache
        tree._get_git_status(ws / "committed.py")
        assert tree._git_result is not None
        # Simulate reload cache clearing
        tree._git_result = None
        # Re-query (will reload)
        assert tree._get_git_status(ws / "committed.py") == "modified"

    def test_c08_untracked_dir_children_detected(self, tmp_path: Path):
        """Files inside an untracked directory are detected as 'untracked'."""
        ws = tmp_path / "ws"
        ws.mkdir()
        init_git_repo(ws)
        newdir = ws / "newdir"
        newdir.mkdir()
        (newdir / "file.py").write_text("# inside untracked dir\n")
        tree = self._make_tree(ws)
        assert tree._get_git_status(newdir / "file.py") == "untracked"


# ── App integration tests ────────────────────────────────────────────────────


@requires_git
class TestAppIntegration:
    @pytest.mark.asyncio
    async def test_d01_default_show_git_status_is_true(self, tmp_path: Path):
        """App defaults show_git_status to True."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            assert app.default_show_git_status is True

    @pytest.mark.asyncio
    async def test_d02_config_loads_false(self, tmp_path: Path):
        """App loads show_git_status = false from config."""
        config = tmp_path / "settings.toml"
        config.write_text("[editor]\nshow_git_status = false\n")
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            assert app.default_show_git_status is False

    @pytest.mark.asyncio
    async def test_d03_build_editor_settings_includes_key(self, tmp_path: Path):
        """_build_editor_settings includes show_git_status."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            settings = app._build_editor_settings()
            assert "show_git_status" in settings
            assert settings["show_git_status"] is True

    @pytest.mark.asyncio
    async def test_d04_tree_receives_show_git_status(self, tmp_path: Path):
        """FilteredDirectoryTree receives show_git_status from app."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            tree = app.sidebar.explorer.directory_tree
            assert tree.show_git_status is True

    @pytest.mark.asyncio
    async def test_d05_system_command_exists(self, tmp_path: Path):
        """Command palette has 'Toggle git status highlighting' command."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            cmds = list(app.get_system_commands(app.screen))
            titles = [c.title for c in cmds]
            assert "Toggle git status highlighting" in titles

    @pytest.mark.asyncio
    async def test_d06_toggle_changes_value(self, tmp_path: Path):
        """Toggle flips show_git_status and updates explorer."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            assert app.default_show_git_status is True
            app._toggle_show_git_status_cmd()
            assert app.default_show_git_status is False
            assert app.sidebar.explorer.directory_tree.show_git_status is False

    @pytest.mark.asyncio
    async def test_d07_toggle_saves_to_config(self, tmp_path: Path):
        """Toggle persists the new value to user config."""
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            app._toggle_show_git_status_cmd()
        loaded = load_editor_settings(ws, user_config_path=config)
        assert loaded["show_git_status"] is False
