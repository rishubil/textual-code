"""
Tests for syntax highlighting theme selection.

Covers:
1. ChangeSyntaxThemeModalScreen can be imported
2. Modal has a Select widget with built-in theme names
3. action_change_syntax_theme exists on TextualCode
4. Selecting a theme + Apply → all editors' theme changes
5. Cancel → editor theme unchanged
6. Theme saved to config after Apply
7. New editors load theme from config
8. All already-open editors update immediately when theme changes
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
    AVAILABLE_SYNTAX_THEMES,
    ChangeSyntaxThemeModalResult,
    ChangeSyntaxThemeModalScreen,
)
from textual_code.widgets.code_editor import CodeEditor

from .conftest import make_app

# ---------------------------------------------------------------------------
# Group 1: Import and basic structure
# ---------------------------------------------------------------------------


def test_modal_can_be_imported():
    assert ChangeSyntaxThemeModalScreen is not None
    assert ChangeSyntaxThemeModalResult is not None
    assert AVAILABLE_SYNTAX_THEMES is not None


def test_available_themes_list():
    assert "monokai" in AVAILABLE_SYNTAX_THEMES
    assert "dracula" in AVAILABLE_SYNTAX_THEMES
    assert "github_light" in AVAILABLE_SYNTAX_THEMES
    assert "vscode_dark" in AVAILABLE_SYNTAX_THEMES
    assert len(AVAILABLE_SYNTAX_THEMES) >= 4


# ---------------------------------------------------------------------------
# Group 2: Config
# ---------------------------------------------------------------------------


def test_default_syntax_theme_in_defaults():
    assert "syntax_theme" in DEFAULT_EDITOR_SETTINGS
    assert DEFAULT_EDITOR_SETTINGS["syntax_theme"] == "monokai"


def test_syntax_theme_saved_and_reloaded(tmp_path):
    cfg = tmp_path / "settings.toml"
    save_user_editor_settings(
        {
            "indent_type": "spaces",
            "indent_size": 4,
            "line_ending": "lf",
            "encoding": "utf-8",
            "syntax_theme": "dracula",
        },
        cfg,
    )
    loaded = load_editor_settings(tmp_path / "ws", user_config_path=cfg)
    assert loaded["syntax_theme"] == "dracula"


def test_syntax_theme_unknown_key_ignored(tmp_path):
    """syntax_theme not in EDITOR_KEYS → should be loaded (it IS a valid key)."""
    cfg = tmp_path / "user.toml"
    cfg.write_text('[editor]\nsyntax_theme = "vscode_dark"\n')
    settings = load_editor_settings(tmp_path, user_config_path=cfg)
    assert settings["syntax_theme"] == "vscode_dark"


# ---------------------------------------------------------------------------
# Group 3: App default attribute
# ---------------------------------------------------------------------------


def test_app_has_default_syntax_theme_attr(tmp_path):
    app = TextualCode(workspace_path=tmp_path, with_open_file=None)
    assert hasattr(app, "default_syntax_theme")
    assert app.default_syntax_theme == "monokai"


def test_action_change_syntax_theme_exists(tmp_path):
    app = TextualCode(workspace_path=tmp_path, with_open_file=None)
    assert callable(getattr(app, "action_change_syntax_theme", None))


# ---------------------------------------------------------------------------
# Group 4: New editors inherit syntax theme
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_new_editor_uses_default_syntax_theme(workspace):
    app = make_app(workspace, light=True)
    app.default_syntax_theme = "dracula"
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor()
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.syntax_theme == "dracula"


@pytest.mark.asyncio
async def test_new_editor_default_theme_is_monokai(workspace):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor()
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.syntax_theme == "monokai"


# ---------------------------------------------------------------------------
# Group 5: All open editors update immediately
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_editors_update_when_theme_changes(workspace):
    """Setting app.default_syntax_theme and updating all editors works."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Open two editors
        await app.main_view.action_open_code_editor()
        await pilot.pause()
        await app.main_view.action_open_code_editor()
        await pilot.pause()

        # Simulate what action_change_syntax_theme does
        from textual_code.widgets.code_editor import CodeEditor

        app.default_syntax_theme = "github_light"
        for editor in app.query(CodeEditor):
            editor.syntax_theme = "github_light"

        await pilot.pause()
        for editor in app.query(CodeEditor):
            assert editor.syntax_theme == "github_light"


# ---------------------------------------------------------------------------
# Group 6: syntax_theme property on CodeEditor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_code_editor_syntax_theme_property(workspace):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.main_view.action_open_code_editor()
        await pilot.pause()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # getter
        assert editor.syntax_theme == "monokai"
        # setter updates the underlying TextArea theme
        editor.syntax_theme = "dracula"
        assert editor.syntax_theme == "dracula"
        assert editor.editor.theme == "dracula"


# ---------------------------------------------------------------------------
# Group 7: Config loaded on startup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_app_loads_syntax_theme_from_project_config(workspace):
    proj = workspace / ".textual-code.toml"
    proj.write_text('[editor]\nsyntax_theme = "vscode_dark"\n')
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.default_syntax_theme == "vscode_dark"


# ---------------------------------------------------------------------------
# Group 8: Modal result dataclass
# ---------------------------------------------------------------------------


def test_modal_result_not_cancelled():
    result = ChangeSyntaxThemeModalResult(is_cancelled=False, theme="dracula")
    assert not result.is_cancelled
    assert result.theme == "dracula"


def test_modal_result_cancelled():
    result = ChangeSyntaxThemeModalResult(is_cancelled=True, theme=None)
    assert result.is_cancelled
    assert result.theme is None


# ---------------------------------------------------------------------------
# Group 9: save_level support
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_action_change_syntax_theme_save_level_user(workspace):
    cfg = workspace / "settings.toml"
    proj = workspace / ".textual-code.toml"
    app = TextualCode(
        workspace_path=workspace, with_open_file=None, user_config_path=cfg
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_change_syntax_theme()
        await pilot.pause()
        from textual_code.modals import ChangeSyntaxThemeModalScreen

        assert isinstance(app.screen, ChangeSyntaxThemeModalScreen)
        app.screen.dismiss(
            ChangeSyntaxThemeModalResult(
                is_cancelled=False, theme="dracula", save_level="user"
            )
        )
        await pilot.pause()
        assert app.default_syntax_theme == "dracula"
        assert cfg.exists()
        loaded = load_editor_settings(workspace, user_config_path=cfg)
        assert loaded["syntax_theme"] == "dracula"
        assert not proj.exists()


@pytest.mark.asyncio
async def test_action_change_syntax_theme_save_level_project(workspace):
    cfg = workspace / "settings.toml"
    proj = workspace / ".textual-code.toml"
    app = TextualCode(
        workspace_path=workspace, with_open_file=None, user_config_path=cfg
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_change_syntax_theme()
        await pilot.pause()
        from textual_code.modals import ChangeSyntaxThemeModalScreen

        assert isinstance(app.screen, ChangeSyntaxThemeModalScreen)
        app.screen.dismiss(
            ChangeSyntaxThemeModalResult(
                is_cancelled=False, theme="dracula", save_level="project"
            )
        )
        await pilot.pause()
        assert proj.exists()
        loaded = load_editor_settings(workspace, user_config_path=cfg)
        assert loaded["syntax_theme"] == "dracula"


@pytest.mark.asyncio
async def test_action_change_syntax_theme_cancel(workspace):
    cfg = workspace / "settings.toml"
    app = TextualCode(
        workspace_path=workspace, with_open_file=None, user_config_path=cfg
    )
    original = app.default_syntax_theme
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_change_syntax_theme()
        await pilot.pause()
        from textual_code.modals import ChangeSyntaxThemeModalScreen

        assert isinstance(app.screen, ChangeSyntaxThemeModalScreen)
        app.screen.dismiss(ChangeSyntaxThemeModalResult(is_cancelled=True, theme=None))
        await pilot.pause()
        assert app.default_syntax_theme == original
        assert not cfg.exists()


# ---------------------------------------------------------------------------
# Group 10: Live preview
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_syntax_theme_live_preview_on_select_change(workspace):
    """Changing the syntax theme Select immediately previews the theme."""
    (workspace / "hello.py").write_text("print('hello')\n")
    app = make_app(workspace, open_file=workspace / "hello.py", light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        editor = app.query_one(CodeEditor)
        assert editor.syntax_theme == "monokai"
        app.action_change_syntax_theme()
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, ChangeSyntaxThemeModalScreen)
        select = modal.query_one("#theme", Select)
        select.value = "dracula"
        await pilot.pause()
        # All editors should preview the new theme
        for ed in app.query(CodeEditor):
            assert ed.syntax_theme == "dracula"


@pytest.mark.asyncio
async def test_syntax_theme_preview_reverts_on_cancel(workspace):
    """Cancelling after preview reverts editors to the original theme."""
    (workspace / "hello.py").write_text("print('hello')\n")
    app = make_app(workspace, open_file=workspace / "hello.py", light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_change_syntax_theme()
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, ChangeSyntaxThemeModalScreen)
        select = modal.query_one("#theme", Select)
        select.value = "dracula"
        await pilot.pause()
        # Verify preview was applied
        for ed in app.query(CodeEditor):
            assert ed.syntax_theme == "dracula"
        # Cancel should revert (use action_cancel to trigger revert logic)
        modal.action_cancel()
        await pilot.pause()
        for ed in app.query(CodeEditor):
            assert ed.syntax_theme == "monokai"


@pytest.mark.asyncio
async def test_syntax_theme_preview_reverts_on_escape(workspace):
    """Pressing Escape after preview reverts editors to the original theme."""
    (workspace / "hello.py").write_text("print('hello')\n")
    app = make_app(workspace, open_file=workspace / "hello.py", light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_change_syntax_theme()
        await pilot.pause()
        modal = app.screen
        select = modal.query_one("#theme", Select)
        select.value = "dracula"
        await pilot.pause()
        # Verify preview was applied
        for ed in app.query(CodeEditor):
            assert ed.syntax_theme == "dracula"
        # Escape should revert
        await pilot.press("escape")
        await pilot.pause()
        for ed in app.query(CodeEditor):
            assert ed.syntax_theme == "monokai"


@pytest.mark.asyncio
async def test_syntax_theme_preview_then_apply_persists(workspace):
    """Preview followed by Apply keeps the theme and saves config."""
    cfg = workspace / "settings.toml"
    (workspace / "hello.py").write_text("print('hello')\n")
    app = TextualCode(
        workspace_path=workspace,
        with_open_file=workspace / "hello.py",
        user_config_path=cfg,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_change_syntax_theme()
        await pilot.pause()
        modal = app.screen
        select = modal.query_one("#theme", Select)
        select.value = "dracula"
        await pilot.pause()
        # Theme previewed before Apply
        for ed in app.query(CodeEditor):
            assert ed.syntax_theme == "dracula"
        modal.dismiss(
            ChangeSyntaxThemeModalResult(
                is_cancelled=False, theme="dracula", save_level="user"
            )
        )
        await pilot.pause()
        for ed in app.query(CodeEditor):
            assert ed.syntax_theme == "dracula"
        loaded = load_editor_settings(workspace, user_config_path=cfg)
        assert loaded["syntax_theme"] == "dracula"


@pytest.mark.asyncio
async def test_syntax_theme_preview_ignores_blank(workspace):
    """Select.BLANK value should not change the syntax theme."""
    (workspace / "hello.py").write_text("print('hello')\n")
    app = make_app(workspace, open_file=workspace / "hello.py", light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_change_syntax_theme()
        await pilot.pause()
        modal = app.screen
        select = modal.query_one("#theme", Select)
        # Post a Changed message with BLANK directly (can't set via .value)
        select.post_message(Select.Changed(select, Select.BLANK))
        await pilot.pause()
        for ed in app.query(CodeEditor):
            assert ed.syntax_theme == "monokai"
