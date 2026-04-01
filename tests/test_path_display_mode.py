"""
Tests for path_display_mode setting (absolute/relative toggle).

Covers:
- Config: default value, EDITOR_KEYS, TOML round-trip, invalid value fallback
- Footer: display mode changes, tab switch preserves mode
- Toggle command: system command exists, saves to config
"""

from pathlib import Path

import pytest

from textual_code.config import (
    DEFAULT_EDITOR_SETTINGS,
    EDITOR_KEYS,
    load_editor_settings,
    save_user_editor_settings,
)
from textual_code.widgets.code_editor import CodeEditorFooter

from .conftest import make_app

# ---------------------------------------------------------------------------
# Group A: Config (sync)
# ---------------------------------------------------------------------------


def test_a01_default_is_absolute():
    assert DEFAULT_EDITOR_SETTINGS["path_display_mode"] == "absolute"


def test_a02_editor_keys_contains_key():
    assert "path_display_mode" in EDITOR_KEYS


def test_a03_toml_round_trip(tmp_path):
    config_path = tmp_path / "settings.toml"
    save_user_editor_settings({"path_display_mode": "relative"}, config_path)
    settings = load_editor_settings(tmp_path, user_config_path=config_path)
    assert settings["path_display_mode"] == "relative"


def test_a04_invalid_value_defaults_to_absolute(tmp_path):
    config_path = tmp_path / "settings.toml"
    config_path.write_text('[editor]\npath_display_mode = "foo"\n')
    app = make_app(tmp_path, user_config_path=config_path, light=True)
    assert app.default_path_display_mode == "absolute"


# ---------------------------------------------------------------------------
# Group B: Footer display (async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_b01_footer_absolute_by_default(workspace, sample_py_file):
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        footer = app.main_view.query_one(CodeEditorFooter)
        assert footer.path_display_mode == "absolute"
        assert str(sample_py_file) in footer.path_view._raw


@pytest.mark.asyncio
async def test_b02_toggle_to_relative(workspace, sample_py_file):
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        footer = app.main_view.query_one(CodeEditorFooter)
        footer.path_display_mode = "relative"
        await pilot.wait_for_scheduled_animations()
        assert footer.path_view._raw == "hello.py"


@pytest.mark.asyncio
async def test_b03_toggle_back_to_absolute(workspace, sample_py_file):
    app = make_app(workspace, open_file=sample_py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        footer = app.main_view.query_one(CodeEditorFooter)
        footer.path_display_mode = "relative"
        await pilot.wait_for_scheduled_animations()
        footer.path_display_mode = "absolute"
        await pilot.wait_for_scheduled_animations()
        assert footer.path_view._raw == str(sample_py_file)


@pytest.mark.asyncio
async def test_b04_relative_outside_workspace_fallback(workspace):
    import tempfile

    with tempfile.TemporaryDirectory() as other_dir:
        outside_file = Path(other_dir) / "outside.py"
        outside_file.write_text("# outside\n")
        app = make_app(workspace, open_file=outside_file, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            footer = app.main_view.query_one(CodeEditorFooter)
            footer.path_display_mode = "relative"
            await pilot.wait_for_scheduled_animations()
            # Falls back to absolute since file is outside workspace
            assert footer.path_view._raw == str(outside_file)


@pytest.mark.asyncio
async def test_b05_config_loads_relative_mode(tmp_path):
    config_path = tmp_path / "settings.toml"
    save_user_editor_settings({"path_display_mode": "relative"}, config_path)
    sample = tmp_path / "test.py"
    sample.write_text("# test\n")
    app = make_app(tmp_path, open_file=sample, user_config_path=config_path, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        footer = app.main_view.query_one(CodeEditorFooter)
        assert footer.path_display_mode == "relative"
        assert footer.path_view._raw == "test.py"


@pytest.mark.asyncio
async def test_b06_tab_switch_preserves_mode(workspace):
    file1 = workspace / "a.py"
    file1.write_text("# a\n")
    file2 = workspace / "b.py"
    file2.write_text("# b\n")
    app = make_app(workspace, open_file=file1, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        footer = app.main_view.query_one(CodeEditorFooter)
        footer.path_display_mode = "relative"
        app.default_path_display_mode = "relative"
        await pilot.wait_for_scheduled_animations()
        assert footer.path_view._raw == "a.py"
        # Open second file
        await app.main_view.action_open_code_editor(path=file2, focus=True)
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        assert footer.path_display_mode == "relative"
        assert footer.path_view._raw == "b.py"


# ---------------------------------------------------------------------------
# Group C: Toggle command (async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_c01_system_command_exists(workspace):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        commands = list(app.get_system_commands(app.screen))
        titles = [c.title for c in commands]
        assert "Toggle Path Display Mode" in titles


@pytest.mark.asyncio
async def test_c02_toggle_saves_to_config(tmp_path):
    config_path = tmp_path / "settings.toml"
    app = make_app(tmp_path, user_config_path=config_path, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        assert app.default_path_display_mode == "absolute"
        app.action_toggle_path_display_mode()
        await pilot.wait_for_scheduled_animations()
        assert app.default_path_display_mode == "relative"
        # Verify saved to config
        settings = load_editor_settings(tmp_path, user_config_path=config_path)
        assert settings["path_display_mode"] == "relative"
