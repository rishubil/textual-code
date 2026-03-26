"""
Tests for UI theme selection.

Covers:
1. Default ui_theme in config settings
2. App starts with default ui_theme attribute
3. App loads ui_theme from config file
4. action_change_ui_theme opens modal and applies/saves the theme
5. Cancel leaves theme unchanged
6. ChangeUIThemeModalScreen and ChangeUIThemeModalResult can be imported
"""

import pytest
from textual.widgets import Select

from textual_code.app import TextualCode
from textual_code.config import (
    DEFAULT_EDITOR_SETTINGS,
    load_editor_settings,
    save_user_editor_settings,
)
from textual_code.modals import (
    ChangeUIThemeModalResult,
    ChangeUIThemeModalScreen,
)

from .conftest import make_app

# ---------------------------------------------------------------------------
# Group 1: Import and basic structure
# ---------------------------------------------------------------------------


def test_modal_can_be_imported():
    assert ChangeUIThemeModalScreen is not None
    assert ChangeUIThemeModalResult is not None


# ---------------------------------------------------------------------------
# Group 2: Config
# ---------------------------------------------------------------------------


def test_default_ui_theme_in_config():
    assert "ui_theme" in DEFAULT_EDITOR_SETTINGS
    assert DEFAULT_EDITOR_SETTINGS["ui_theme"] == "textual-dark"


def test_ui_theme_saved_and_reloaded(tmp_path):
    cfg = tmp_path / "settings.toml"
    save_user_editor_settings(
        {
            "indent_type": "spaces",
            "indent_size": 4,
            "line_ending": "lf",
            "encoding": "utf-8",
            "syntax_theme": "monokai",
            "word_wrap": False,
            "ui_theme": "nord",
        },
        cfg,
    )
    loaded = load_editor_settings(tmp_path / "ws", user_config_path=cfg)
    assert loaded["ui_theme"] == "nord"


# ---------------------------------------------------------------------------
# Group 3: App default attribute
# ---------------------------------------------------------------------------


def test_app_has_default_ui_theme_attr(tmp_path):
    app = TextualCode(workspace_path=tmp_path, with_open_file=None)
    assert hasattr(app, "default_ui_theme")
    assert app.default_ui_theme == "textual-dark"


def test_action_change_ui_theme_exists(tmp_path):
    app = TextualCode(workspace_path=tmp_path, with_open_file=None)
    assert callable(getattr(app, "action_change_ui_theme", None))


# ---------------------------------------------------------------------------
# Group 4: App applies ui_theme on startup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_app_applies_ui_theme_on_startup(workspace):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == "textual-dark"


@pytest.mark.asyncio
async def test_app_loads_ui_theme_from_config(workspace):
    cfg = workspace / "settings.toml"
    save_user_editor_settings(
        {
            "indent_type": "spaces",
            "indent_size": 4,
            "line_ending": "lf",
            "encoding": "utf-8",
            "syntax_theme": "monokai",
            "word_wrap": False,
            "ui_theme": "nord",
        },
        cfg,
    )
    app = TextualCode(
        workspace_path=workspace, with_open_file=None, user_config_path=cfg
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.default_ui_theme == "nord"
        assert app.theme == "nord"


# ---------------------------------------------------------------------------
# Group 5: action_change_ui_theme applies and saves
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_action_change_ui_theme_applies_and_saves(workspace):
    cfg = workspace / "settings.toml"
    app = TextualCode(
        workspace_path=workspace, with_open_file=None, user_config_path=cfg
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_change_ui_theme()
        await pilot.pause()
        assert isinstance(app.screen, ChangeUIThemeModalScreen)
        app.screen.dismiss(
            ChangeUIThemeModalResult(
                is_cancelled=False, theme="nord", save_level="user"
            )
        )
        await pilot.pause()
        assert app.theme == "nord"
        assert app.default_ui_theme == "nord"
        loaded = load_editor_settings(workspace, user_config_path=cfg)
        assert loaded["ui_theme"] == "nord"


@pytest.mark.asyncio
async def test_action_change_ui_theme_save_level_user(workspace):
    cfg = workspace / "settings.toml"
    proj = workspace / ".textual-code.toml"
    app = TextualCode(
        workspace_path=workspace, with_open_file=None, user_config_path=cfg
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_change_ui_theme()
        await pilot.pause()
        app.screen.dismiss(
            ChangeUIThemeModalResult(
                is_cancelled=False, theme="nord", save_level="user"
            )
        )
        await pilot.pause()
        assert cfg.exists()
        loaded = load_editor_settings(workspace, user_config_path=cfg)
        assert loaded["ui_theme"] == "nord"
        # project config should NOT have been created
        assert not proj.exists()


@pytest.mark.asyncio
async def test_action_change_ui_theme_save_level_project(workspace):
    cfg = workspace / "settings.toml"
    proj = workspace / ".textual-code.toml"
    app = TextualCode(
        workspace_path=workspace, with_open_file=None, user_config_path=cfg
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_change_ui_theme()
        await pilot.pause()
        app.screen.dismiss(
            ChangeUIThemeModalResult(
                is_cancelled=False, theme="nord", save_level="project"
            )
        )
        await pilot.pause()
        assert proj.exists()
        loaded = load_editor_settings(workspace, user_config_path=cfg)
        assert loaded["ui_theme"] == "nord"


@pytest.mark.asyncio
async def test_builtin_theme_command_removed(workspace):
    app = TextualCode(workspace_path=workspace, with_open_file=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = list(app.get_system_commands(app.screen))
        titles = [c.title for c in cmds]
        assert "Theme" not in titles


@pytest.mark.asyncio
async def test_action_change_ui_theme_cancel_leaves_theme(workspace):
    cfg = workspace / "settings.toml"
    app = TextualCode(
        workspace_path=workspace, with_open_file=None, user_config_path=cfg
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        original_theme = app.theme
        app.action_change_ui_theme()
        await pilot.pause()
        assert isinstance(app.screen, ChangeUIThemeModalScreen)
        app.screen.dismiss(ChangeUIThemeModalResult(is_cancelled=True, theme=None))
        await pilot.pause()
        assert app.theme == original_theme


# ---------------------------------------------------------------------------
# Group 6: Modal result dataclass
# ---------------------------------------------------------------------------


def test_modal_result_not_cancelled():
    result = ChangeUIThemeModalResult(is_cancelled=False, theme="nord")
    assert not result.is_cancelled
    assert result.theme == "nord"


def test_modal_result_cancelled():
    result = ChangeUIThemeModalResult(is_cancelled=True, theme=None)
    assert result.is_cancelled
    assert result.theme is None


# ---------------------------------------------------------------------------
# Group 7: Live preview
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ui_theme_live_preview_on_select_change(workspace):
    """Changing the theme Select immediately previews the theme."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == "textual-dark"
        app.action_change_ui_theme()
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, ChangeUIThemeModalScreen)
        # Simulate selecting a different theme
        select = modal.query_one("#theme", Select)
        select.value = "nord"
        await pilot.pause()
        # Theme should be applied immediately as a preview
        assert app.theme == "nord"


@pytest.mark.asyncio
async def test_ui_theme_preview_reverts_on_cancel(workspace):
    """Cancelling after preview reverts to the original theme."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == "textual-dark"
        app.action_change_ui_theme()
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, ChangeUIThemeModalScreen)
        select = modal.query_one("#theme", Select)
        select.value = "nord"
        await pilot.pause()
        assert app.theme == "nord"
        # Cancel should revert (use action_cancel to trigger revert logic)
        modal.action_cancel()
        await pilot.pause()
        assert app.theme == "textual-dark"


@pytest.mark.asyncio
async def test_ui_theme_preview_reverts_on_escape(workspace):
    """Pressing Escape after preview reverts to the original theme."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == "textual-dark"
        app.action_change_ui_theme()
        await pilot.pause()
        modal = app.screen
        select = modal.query_one("#theme", Select)
        select.value = "nord"
        await pilot.pause()
        assert app.theme == "nord"
        # Escape should revert
        await pilot.press("escape")
        await pilot.pause()
        assert app.theme == "textual-dark"


@pytest.mark.asyncio
async def test_ui_theme_preview_then_apply_persists(workspace):
    """Preview followed by Apply keeps the theme and saves config."""
    cfg = workspace / "settings.toml"
    app = TextualCode(
        workspace_path=workspace, with_open_file=None, user_config_path=cfg
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_change_ui_theme()
        await pilot.pause()
        modal = app.screen
        select = modal.query_one("#theme", Select)
        select.value = "nord"
        await pilot.pause()
        # Theme previewed before Apply
        assert app.theme == "nord"
        modal.dismiss(
            ChangeUIThemeModalResult(
                is_cancelled=False, theme="nord", save_level="user"
            )
        )
        await pilot.pause()
        assert app.theme == "nord"
        loaded = load_editor_settings(workspace, user_config_path=cfg)
        assert loaded["ui_theme"] == "nord"


@pytest.mark.asyncio
async def test_ui_theme_preview_ignores_blank(workspace):
    """Select.BLANK value should not change the theme."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        original = app.theme
        app.action_change_ui_theme()
        await pilot.pause()
        modal = app.screen
        select = modal.query_one("#theme", Select)
        # Post a Changed message with BLANK directly (can't set via .value)
        select.post_message(Select.Changed(select, Select.BLANK))
        await pilot.pause()
        assert app.theme == original
