"""
Tests for editor defaults with config file persistence.

Covers:
- config.py unit tests (load/save settings)
- App attribute defaults
- New file uses custom defaults
- Project config loaded on startup
- Existing file ignores app defaults (regression)
- action_set_default_* methods exist
"""

from unittest.mock import patch

import pytest

from textual_code.app import TextualCode
from textual_code.config import (
    DEFAULT_EDITOR_SETTINGS,
    _serialize_editor_settings,
    load_editor_settings,
    load_keybindings,
    save_project_editor_settings,
    save_user_editor_settings,
)

from .conftest import make_app

# ---------------------------------------------------------------------------
# Group 1: config.py unit tests
# ---------------------------------------------------------------------------


def test_default_editor_settings_values():
    assert DEFAULT_EDITOR_SETTINGS["indent_type"] == "spaces"
    assert DEFAULT_EDITOR_SETTINGS["indent_size"] == 4
    assert DEFAULT_EDITOR_SETTINGS["line_ending"] == "lf"
    assert DEFAULT_EDITOR_SETTINGS["encoding"] == "utf-8"


def test_load_editor_settings_no_files(tmp_path):
    settings = load_editor_settings(tmp_path, user_config_path=tmp_path / "no.toml")
    assert settings == DEFAULT_EDITOR_SETTINGS


def test_load_editor_settings_user_config(tmp_path):
    cfg = tmp_path / "user.toml"
    cfg.write_text('[editor]\nindent_type = "tabs"\nindent_size = 2\n')
    settings = load_editor_settings(tmp_path, user_config_path=cfg)
    assert settings["indent_type"] == "tabs"
    assert settings["indent_size"] == 2
    assert settings["line_ending"] == "lf"  # default unchanged


def test_load_editor_settings_project_overrides_user(tmp_path):
    cfg = tmp_path / "user.toml"
    cfg.write_text('[editor]\nindent_type = "tabs"\n')
    proj = tmp_path / ".textual-code.toml"
    proj.write_text('[editor]\nindent_type = "spaces"\n')
    settings = load_editor_settings(tmp_path, user_config_path=cfg)
    assert settings["indent_type"] == "spaces"  # project wins


def test_save_and_reload_user_settings(tmp_path):
    cfg = tmp_path / "settings.toml"
    save_user_editor_settings(
        {
            "indent_type": "tabs",
            "indent_size": 2,
            "line_ending": "crlf",
            "encoding": "latin-1",
        },
        cfg,
    )
    loaded = load_editor_settings(tmp_path / "ws", user_config_path=cfg)
    assert loaded["indent_type"] == "tabs"
    assert loaded["indent_size"] == 2
    assert loaded["line_ending"] == "crlf"
    assert loaded["encoding"] == "latin-1"


def test_save_creates_parent_dirs(tmp_path):
    cfg = tmp_path / "a" / "b" / "settings.toml"
    save_user_editor_settings(DEFAULT_EDITOR_SETTINGS, cfg)
    assert cfg.exists()


def test_invalid_toml_falls_back_to_defaults(tmp_path):
    cfg = tmp_path / "bad.toml"
    cfg.write_text("NOT VALID TOML !!!")
    settings = load_editor_settings(tmp_path, user_config_path=cfg)
    assert settings == DEFAULT_EDITOR_SETTINGS


def test_unknown_keys_ignored(tmp_path):
    cfg = tmp_path / "user.toml"
    cfg.write_text('[editor]\nunknown_key = "value"\n')
    settings = load_editor_settings(tmp_path, user_config_path=cfg)
    assert "unknown_key" not in settings


# ---------------------------------------------------------------------------
# Group 2: App default attributes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "attr,expected",
    [
        ("default_indent_type", "spaces"),
        ("default_indent_size", 4),
        ("default_line_ending", "lf"),
        ("default_encoding", "utf-8"),
    ],
)
def test_app_has_default_attr(tmp_path, attr, expected):
    app = TextualCode(workspace_path=tmp_path, with_open_file=None)
    assert getattr(app, attr) == expected


# ---------------------------------------------------------------------------
# Group 3: New file uses custom defaults
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "attr,value,editor_attr",
    [
        ("default_indent_type", "tabs", "indent_type"),
        ("default_indent_size", 2, "indent_size"),
        ("default_line_ending", "crlf", "line_ending"),
        ("default_encoding", "latin-1", "encoding"),
    ],
)
@pytest.mark.asyncio
async def test_new_file_uses_custom_default(workspace, attr, value, editor_attr):
    app = make_app(workspace, light=True)
    setattr(app, attr, value)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_code_editor()
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert getattr(editor, editor_attr) == value


# ---------------------------------------------------------------------------
# Group 4: Config file loaded on startup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_app_loads_project_config_on_startup(workspace):
    proj = workspace / ".textual-code.toml"
    proj.write_text('[editor]\nline_ending = "crlf"\n')
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert app.default_line_ending == "crlf"


@pytest.mark.asyncio
async def test_app_loads_user_and_project_config_priority(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    # user config says tabs, project config says spaces → project wins
    user_cfg = tmp_path / "user.toml"
    user_cfg.write_text('[editor]\nindent_type = "tabs"\n')
    ws = tmp_path / "ws"
    ws.mkdir()
    proj = ws / ".textual-code.toml"
    proj.write_text('[editor]\nindent_type = "spaces"\n')
    # Patch load_editor_settings via monkeypatching user_config_path
    import textual_code.config as config_module

    original_load = config_module.load_editor_settings

    def patched_load(workspace_path, user_config_path=None):
        return original_load(workspace_path, user_config_path=user_cfg)

    monkeypatch.setattr(config_module, "load_editor_settings", patched_load)
    app = TextualCode(workspace_path=ws, with_open_file=None)
    assert app.default_indent_type == "spaces"  # project overrides user


# ---------------------------------------------------------------------------
# Group 5: Existing file ignores app defaults (regression)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_existing_file_ignores_app_defaults(workspace):
    f = workspace / "file.py"
    f.write_text("content\n")
    proj = workspace / ".textual-code.toml"
    proj.write_text('[editor]\nindent_type = "tabs"\nindent_size = 2\n')
    # The project config changes app defaults, but existing file should use
    # its own detected settings (not app defaults)
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        # file.py has no editorconfig, so detection applies: spaces + 4
        # (default detection from file content, not from app defaults)
        assert editor.indent_type == "spaces"
        assert editor.indent_size == 4


# ---------------------------------------------------------------------------
# Group 6: Changing defaults only affects new files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_changing_defaults_only_affects_new_files(workspace):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_code_editor()
        await pilot.wait_for_scheduled_animations()
        first = app.main_view.get_active_code_editor()
        assert first is not None
        first_indent = first.indent_type  # should be "spaces"

        app.default_indent_type = "tabs"
        await app.main_view.action_open_code_editor()
        await pilot.wait_for_scheduled_animations()
        # get second editor (find one that is tabs)
        second = app.main_view.get_active_code_editor()
        assert second is not None
        assert second.indent_type == "tabs"
        assert first.indent_type == first_indent  # unchanged


# ---------------------------------------------------------------------------
# Group 7: action methods exist
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action",
    [
        "action_set_default_indentation",
        "action_set_default_line_ending",
        "action_set_default_encoding",
    ],
)
def test_action_exists(tmp_path, action):
    app = TextualCode(workspace_path=tmp_path, with_open_file=None)
    assert callable(getattr(app, action, None))


# ---------------------------------------------------------------------------
# Group 8: save_project_editor_settings
# ---------------------------------------------------------------------------


def test_save_project_editor_settings_writes_toml(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    save_project_editor_settings({"indent_type": "tabs", "indent_size": 2}, ws)
    config_path = ws / ".textual-code.toml"
    assert config_path.exists()
    content = config_path.read_text()
    assert "[editor]" in content
    assert 'indent_type = "tabs"' in content
    assert "indent_size = 2" in content


def test_serialize_editor_settings_bool_lowercase(tmp_path):
    result = _serialize_editor_settings({"word_wrap": True, "word_wrap2": False})
    assert "word_wrap = true" in result
    assert "word_wrap2 = false" in result


def test_warn_line_ending_default_true(tmp_path):
    """warn_line_ending defaults to True when absent from config."""
    settings = load_editor_settings(tmp_path, user_config_path=tmp_path / "no.toml")
    assert settings["warn_line_ending"] is True


def test_warn_line_ending_false_from_config(tmp_path):
    """TOML with warn_line_ending = false → load_editor_settings returns False."""
    cfg = tmp_path / "user.toml"
    cfg.write_text("[editor]\nwarn_line_ending = false\n")
    settings = load_editor_settings(tmp_path, user_config_path=cfg)
    assert settings["warn_line_ending"] is False


@pytest.mark.asyncio
async def test_action_set_default_indentation_saves_to_project(workspace):
    """Selecting 'Project' save level → .textual-code.toml is written."""
    from textual.widgets import Input, Select

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.action_set_default_indentation()
        await pilot.wait_for_scheduled_animations()

        app.screen.query_one("#indent_type", Select).value = "tabs"
        app.screen.query_one("#indent_size", Input).value = "2"
        app.screen.query_one("#save_level", Select).value = "project"
        await pilot.click("#apply")
        await pilot.wait_for_scheduled_animations()

    proj_cfg = workspace / ".textual-code.toml"
    assert proj_cfg.exists()
    content = proj_cfg.read_text()
    assert 'indent_type = "tabs"' in content


# ---------------------------------------------------------------------------
# Group 9: Config parse error warnings (#67)
# ---------------------------------------------------------------------------


def test_invalid_toml_collects_warning(tmp_path):
    """Invalid user TOML appends a parse-error warning to the list."""
    cfg = tmp_path / "bad.toml"
    cfg.write_text("NOT VALID TOML !!!")
    warnings: list[str] = []
    load_editor_settings(tmp_path, user_config_path=cfg, warnings=warnings)
    assert len(warnings) == 1
    assert "parse error" in warnings[0].lower()


# ---------------------------------------------------------------------------
# Group 10: Partial save — only changed keys persisted (#132)
# ---------------------------------------------------------------------------


def test_save_user_settings_preserves_existing_and_adds_only_new(tmp_path):
    """Saving a new key preserves pre-existing overrides without adding defaults."""
    cfg = tmp_path / "settings.toml"
    # Pre-existing config with only one explicit override
    cfg.write_text('[editor]\nsyntax_theme = "dracula"\n')

    # Save only word_wrap change
    save_user_editor_settings({"word_wrap": False}, cfg)

    content = cfg.read_text()
    # The new key should be present
    assert "word_wrap = false" in content
    # The pre-existing override should be preserved
    assert 'syntax_theme = "dracula"' in content
    # Default-valued keys should NOT be written
    assert "indent_size" not in content
    assert "indent_type" not in content
    assert "ui_theme" not in content
    assert "show_hidden_files" not in content


def test_save_project_settings_preserves_existing_and_adds_only_new(tmp_path):
    """Project config save should also use read-modify-write pattern."""
    ws = tmp_path / "ws"
    ws.mkdir()
    proj_cfg = ws / ".textual-code.toml"
    proj_cfg.write_text("[editor]\nindent_size = 2\n")

    # Save only word_wrap change
    save_project_editor_settings({"word_wrap": False}, ws)

    content = proj_cfg.read_text()
    assert "word_wrap = false" in content
    assert "indent_size = 2" in content
    # Should NOT contain other default keys
    assert "ui_theme" not in content
    assert "syntax_theme" not in content


def test_save_user_settings_overwrites_existing_key(tmp_path):
    """Saving a key that already exists should update its value."""
    cfg = tmp_path / "settings.toml"
    cfg.write_text('[editor]\nsyntax_theme = "dracula"\nindent_size = 2\n')

    save_user_editor_settings({"syntax_theme": "monokai"}, cfg)

    content = cfg.read_text()
    assert 'syntax_theme = "monokai"' in content
    assert "indent_size = 2" in content
    # Should NOT have dracula anymore
    assert "dracula" not in content


def test_invalid_project_config_collects_warning(tmp_path):
    """Invalid project .textual-code.toml appends a parse-error warning."""
    ws = tmp_path / "ws"
    ws.mkdir()
    proj = ws / ".textual-code.toml"
    proj.write_text("NOT VALID TOML !!!")
    warnings: list[str] = []
    load_editor_settings(ws, user_config_path=tmp_path / "no.toml", warnings=warnings)
    assert len(warnings) == 1
    assert "parse error" in warnings[0].lower()
    assert "project" in warnings[0].lower()


def test_permission_error_collects_warning(tmp_path):
    """PermissionError appends a permission-denied warning."""
    cfg = tmp_path / "user.toml"
    cfg.write_text("[editor]\nindent_size = 2\n")
    warnings: list[str] = []
    with patch("builtins.open", side_effect=PermissionError("nope")):
        load_editor_settings(tmp_path, user_config_path=cfg, warnings=warnings)
    assert len(warnings) >= 1
    assert "permission" in warnings[0].lower()


def test_missing_file_no_warning(tmp_path):
    """Missing config file does not produce a warning."""
    warnings: list[str] = []
    load_editor_settings(
        tmp_path, user_config_path=tmp_path / "no.toml", warnings=warnings
    )
    assert warnings == []


def test_invalid_keybindings_collects_warning(tmp_path):
    """Invalid keybindings.toml appends a parse-error warning."""
    kb = tmp_path / "keybindings.toml"
    kb.write_text("NOT VALID TOML !!!")
    warnings: list[str] = []
    load_keybindings(kb, warnings=warnings)
    assert len(warnings) == 1
    assert "parse error" in warnings[0].lower()


@pytest.mark.asyncio
async def test_app_shows_toast_on_invalid_config(tmp_path):
    """App shows warning toast when user config has parse errors."""
    cfg = tmp_path / "user.toml"
    cfg.write_text("NOT VALID TOML !!!")
    ws = tmp_path / "ws"
    ws.mkdir()
    app = make_app(ws, user_config_path=cfg, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        warning_notifications = [
            n
            for n in app._notifications
            if n.severity == "warning" and "parse error" in n.message.lower()
        ]
        assert len(warning_notifications) >= 1
