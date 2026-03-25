"""
Tests for open user/project settings commands.

Covers:
- action_open_user_settings: creates file if missing, opens in editor
- action_open_project_settings: creates file if missing, opens in editor
- Command palette entries
- Error handling for inaccessible paths
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from textual_code.config import get_project_config_path

from .conftest import make_app

# ---------------------------------------------------------------------------
# Group A: open user settings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a01_open_user_settings_creates_file_if_missing(workspace, tmp_path):
    user_cfg = tmp_path / "cfg" / "settings.toml"
    assert not user_cfg.exists()
    app = make_app(workspace, user_config_path=user_cfg, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_open_user_settings()
        await pilot.pause()
        assert user_cfg.exists()


@pytest.mark.asyncio
async def test_a02_open_user_settings_opens_in_editor(workspace, tmp_path):
    user_cfg = tmp_path / "cfg" / "settings.toml"
    app = make_app(workspace, user_config_path=user_cfg, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_open_user_settings()
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.path == user_cfg


# ---------------------------------------------------------------------------
# Group B: open project settings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_b01_open_project_settings_creates_file_if_missing(workspace):
    project_cfg = get_project_config_path(workspace)
    assert not project_cfg.exists()
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_open_project_settings()
        await pilot.pause()
        assert project_cfg.exists()


@pytest.mark.asyncio
async def test_b02_open_project_settings_opens_in_editor(workspace):
    project_cfg = get_project_config_path(workspace)
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_open_project_settings()
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.path == project_cfg


# ---------------------------------------------------------------------------
# Group C: command palette entries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_c01_settings_commands_in_system_commands(workspace):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        commands = list(app.get_system_commands(app.screen))
        titles = [c.title for c in commands]
        assert "Open User Settings" in titles
        assert "Open Project Settings" in titles
        assert "Open Keyboard Shortcuts File" in titles


# ---------------------------------------------------------------------------
# Group D: error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_d01_open_user_settings_survives_oserror(workspace, tmp_path):
    """action_open_user_settings notifies on I/O error instead of crashing."""
    user_cfg = tmp_path / "cfg" / "settings.toml"
    app = make_app(workspace, user_config_path=user_cfg, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        with patch.object(Path, "mkdir", side_effect=OSError("permission denied")):
            app.action_open_user_settings()
            await pilot.pause()
        # Should not crash; no editor opened for this path
        editor = app.main_view.get_active_code_editor()
        assert editor is None or editor.path != user_cfg


@pytest.mark.asyncio
async def test_d02_open_project_settings_survives_oserror(workspace):
    """action_open_project_settings notifies on I/O error instead of crashing."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        with patch.object(Path, "mkdir", side_effect=OSError("permission denied")):
            app.action_open_project_settings()
            await pilot.pause()
        # Should not crash
        editor = app.main_view.get_active_code_editor()
        project_cfg = get_project_config_path(workspace)
        assert editor is None or editor.path != project_cfg


# ---------------------------------------------------------------------------
# Group E: open keybindings file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e01_open_keybindings_creates_file_if_missing(workspace, tmp_path):
    user_cfg = tmp_path / "cfg" / "settings.toml"
    assert not user_cfg.exists()
    app = make_app(workspace, user_config_path=user_cfg, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_open_keyboard_shortcuts_file()
        await pilot.pause()
        kb_path = user_cfg.with_name("keybindings.toml")
        assert kb_path.exists()


@pytest.mark.asyncio
async def test_e02_open_keybindings_opens_in_editor(workspace, tmp_path):
    user_cfg = tmp_path / "cfg" / "settings.toml"
    app = make_app(workspace, user_config_path=user_cfg, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_open_keyboard_shortcuts_file()
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        kb_path = user_cfg.with_name("keybindings.toml")
        assert editor.path == kb_path
