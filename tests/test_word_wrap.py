"""
Tests for word wrap toggle feature.

Covers:
- config.py: DEFAULT_EDITOR_SETTINGS has word_wrap
- App default_word_wrap attribute
- CodeEditor.word_wrap reactive
- action_toggle_word_wrap()
- Command palette entries
"""

import pytest

from textual_code.app import TextualCode
from textual_code.config import (
    DEFAULT_EDITOR_SETTINGS,
    load_editor_settings,
    save_user_editor_settings,
)

from .conftest import make_app

# ---------------------------------------------------------------------------
# Group A: config.py unit tests
# ---------------------------------------------------------------------------


def test_a01_default_editor_settings_has_word_wrap():
    assert DEFAULT_EDITOR_SETTINGS["word_wrap"] is True


def test_a02_load_editor_settings_returns_word_wrap_from_user_toml(tmp_path):
    cfg = tmp_path / "user.toml"
    cfg.write_text("[editor]\nword_wrap = true\n")
    settings = load_editor_settings(tmp_path, user_config_path=cfg)
    assert settings["word_wrap"] is True


def test_a03_save_and_reload_word_wrap(tmp_path):
    cfg = tmp_path / "settings.toml"
    save_user_editor_settings({"word_wrap": True}, cfg)
    loaded = load_editor_settings(tmp_path / "ws", user_config_path=cfg)
    assert loaded["word_wrap"] is True


# ---------------------------------------------------------------------------
# Group B: App default attributes
# ---------------------------------------------------------------------------


def test_b01_app_has_default_word_wrap_true(tmp_path):
    app = TextualCode(workspace_path=tmp_path, with_open_file=None)
    assert app.default_word_wrap is True


def test_b02_action_set_default_word_wrap_exists(tmp_path):
    app = TextualCode(workspace_path=tmp_path, with_open_file=None)
    assert hasattr(app, "action_set_default_word_wrap")
    assert callable(app.action_set_default_word_wrap)


# ---------------------------------------------------------------------------
# Group C: CodeEditor reactive
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_c01_code_editor_word_wrap_reactive_exists(workspace):
    from textual_code.widgets.code_editor import CodeEditor

    assert hasattr(CodeEditor, "word_wrap")


@pytest.mark.asyncio
async def test_c02_new_file_uses_default_word_wrap_true(workspace):
    app = make_app(workspace, light=True)
    app.default_word_wrap = True
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_code_editor()
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.word_wrap is True


@pytest.mark.asyncio
async def test_c03_word_wrap_true_sets_soft_wrap(workspace):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_code_editor()
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        editor.word_wrap = False
        await pilot.wait_for_scheduled_animations()
        assert editor.editor.soft_wrap is False
        editor.word_wrap = True
        await pilot.wait_for_scheduled_animations()
        assert editor.editor.soft_wrap is True


# ---------------------------------------------------------------------------
# Group D: Toggle action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_d01_action_toggle_word_wrap_exists(workspace):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_code_editor()
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert hasattr(editor, "action_toggle_word_wrap")
        assert callable(editor.action_toggle_word_wrap)


@pytest.mark.asyncio
async def test_d02_toggle_word_wrap_false_to_true_to_false(workspace):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_code_editor()
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.word_wrap is True
        editor.action_toggle_word_wrap()
        await pilot.wait_for_scheduled_animations()
        assert editor.word_wrap is False
        editor.action_toggle_word_wrap()
        await pilot.wait_for_scheduled_animations()
        assert editor.word_wrap is True


@pytest.mark.asyncio
async def test_d03_command_palette_has_toggle_word_wrap(workspace):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        commands = list(app.get_system_commands(app.screen))
        titles = [c.title for c in commands]
        assert any("word wrap" in t.lower() for t in titles)


# ---------------------------------------------------------------------------
# Group C (continued): on_mount and existing file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_c04_existing_file_default_word_wrap_applied(workspace):
    """Existing file with default_word_wrap=True: editor.editor.soft_wrap is True."""
    f = workspace / "test.py"
    f.write_text("hello\n")
    app = make_app(workspace, open_file=f, light=True)
    app.default_word_wrap = True
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.editor.soft_wrap is True


@pytest.mark.asyncio
async def test_c05_on_mount_applies_word_wrap_false(workspace):
    """New file with default_word_wrap=False → editor.editor.soft_wrap is False."""
    app = make_app(workspace, light=True)
    app.default_word_wrap = False
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await app.main_view.action_open_code_editor()
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.editor.soft_wrap is False
