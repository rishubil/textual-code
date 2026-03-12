"""
Tests for open user/project settings commands.

Covers:
- action_open_user_settings: creates file if missing, opens in editor
- action_open_project_settings: creates file if missing, opens in editor
- Command palette entries
"""

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
    app = make_app(workspace, user_config_path=user_cfg)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_open_user_settings()
        await pilot.pause()
        assert user_cfg.exists()


@pytest.mark.asyncio
async def test_a02_open_user_settings_opens_in_editor(workspace, tmp_path):
    user_cfg = tmp_path / "cfg" / "settings.toml"
    app = make_app(workspace, user_config_path=user_cfg)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_open_user_settings()
        await pilot.pause()
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
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_open_project_settings()
        await pilot.pause()
        assert project_cfg.exists()


@pytest.mark.asyncio
async def test_b02_open_project_settings_opens_in_editor(workspace):
    project_cfg = get_project_config_path(workspace)
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_open_project_settings()
        await pilot.pause()
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.path == project_cfg


# ---------------------------------------------------------------------------
# Group C: command palette entries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_c01_settings_commands_in_system_commands(workspace):
    app = make_app(workspace)
    async with app.run_test() as pilot:
        await pilot.pause()
        commands = list(app.get_system_commands(app.screen))
        titles = [c.title for c in commands]
        assert "Open user settings" in titles
        assert "Open project settings" in titles
