"""Tests for the sidebar_width setting."""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.config import (
    DEFAULT_EDITOR_SETTINGS,
    EDITOR_KEYS,
    load_editor_settings,
    save_user_editor_settings,
)


class TestConfig:
    """Config layer: defaults, TOML load, round-trip."""

    def test_a01_default_setting_is_28(self):
        assert DEFAULT_EDITOR_SETTINGS["sidebar_width"] == 28

    def test_a02_editor_keys_contains_sidebar_width(self):
        assert "sidebar_width" in EDITOR_KEYS

    def test_a03_toml_load_int(self, tmp_path: Path):
        config = tmp_path / "settings.toml"
        config.write_text("[editor]\nsidebar_width = 40\n")
        ws = tmp_path / "ws"
        ws.mkdir()
        settings = load_editor_settings(ws, user_config_path=config)
        assert settings["sidebar_width"] == 40
        assert isinstance(settings["sidebar_width"], int)

    def test_a04_toml_load_percentage(self, tmp_path: Path):
        config = tmp_path / "settings.toml"
        config.write_text('[editor]\nsidebar_width = "30%"\n')
        ws = tmp_path / "ws"
        ws.mkdir()
        settings = load_editor_settings(ws, user_config_path=config)
        assert settings["sidebar_width"] == "30%"

    def test_a05_round_trip_int(self, tmp_path: Path):
        config = tmp_path / "settings.toml"
        settings = dict(DEFAULT_EDITOR_SETTINGS)
        settings["sidebar_width"] = 40
        save_user_editor_settings(settings, config_path=config)
        loaded = load_editor_settings(tmp_path, user_config_path=config)
        assert loaded["sidebar_width"] == 40

    def test_a06_round_trip_percentage(self, tmp_path: Path):
        config = tmp_path / "settings.toml"
        settings = dict(DEFAULT_EDITOR_SETTINGS)
        settings["sidebar_width"] = "30%"
        save_user_editor_settings(settings, config_path=config)
        loaded = load_editor_settings(tmp_path, user_config_path=config)
        assert loaded["sidebar_width"] == "30%"


class TestValidation:
    """Validation of sidebar_width setting values."""

    def test_b01_valid_int(self):
        from textual_code.app import _validate_sidebar_width_setting

        assert _validate_sidebar_width_setting(28) == 28

    def test_b02_min_boundary(self):
        from textual_code.app import _validate_sidebar_width_setting

        assert _validate_sidebar_width_setting(5) == 5

    def test_b03_below_min(self):
        from textual_code.app import _validate_sidebar_width_setting

        assert _validate_sidebar_width_setting(4) is None

    def test_b04_valid_percentage(self):
        from textual_code.app import _validate_sidebar_width_setting

        assert _validate_sidebar_width_setting("30%") == "30%"

    def test_b05_pct_min_boundary(self):
        from textual_code.app import _validate_sidebar_width_setting

        assert _validate_sidebar_width_setting("1%") == "1%"

    def test_b06_pct_max_boundary(self):
        from textual_code.app import _validate_sidebar_width_setting

        assert _validate_sidebar_width_setting("90%") == "90%"

    def test_b07_pct_zero(self):
        from textual_code.app import _validate_sidebar_width_setting

        assert _validate_sidebar_width_setting("0%") is None

    def test_b08_pct_above_max(self):
        from textual_code.app import _validate_sidebar_width_setting

        assert _validate_sidebar_width_setting("91%") is None

    def test_b09_invalid_string(self):
        from textual_code.app import _validate_sidebar_width_setting

        assert _validate_sidebar_width_setting("abc") is None

    def test_b10_string_number(self):
        from textual_code.app import _validate_sidebar_width_setting

        assert _validate_sidebar_width_setting("30") == 30

    def test_b11_float(self):
        from textual_code.app import _validate_sidebar_width_setting

        assert _validate_sidebar_width_setting(30.5) == 30


class TestAppIntegration:
    """App loads and stores sidebar_width correctly."""

    @pytest.mark.asyncio
    async def test_c01_default_is_28(self, tmp_path: Path):
        config = tmp_path / "settings.toml"
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            assert app.default_sidebar_width == 28

    @pytest.mark.asyncio
    async def test_c02_loads_custom_int(self, tmp_path: Path):
        config = tmp_path / "settings.toml"
        config.write_text("[editor]\nsidebar_width = 40\n")
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            assert app.default_sidebar_width == 40

    @pytest.mark.asyncio
    async def test_c03_loads_percentage(self, tmp_path: Path):
        config = tmp_path / "settings.toml"
        config.write_text('[editor]\nsidebar_width = "30%"\n')
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            assert app.default_sidebar_width == "30%"

    @pytest.mark.asyncio
    async def test_c04_invalid_falls_back(self, tmp_path: Path):
        config = tmp_path / "settings.toml"
        config.write_text("[editor]\nsidebar_width = 3\n")
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test():
            assert app.default_sidebar_width == 28


class TestSidebarWidthApplied:
    """Sidebar actually renders at the configured width."""

    @pytest.mark.asyncio
    async def test_d01_default_is_28_cells(self, tmp_path: Path):
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws)
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.wait_for_scheduled_animations()
            assert app.sidebar is not None
            assert app.sidebar.size.width == 28

    @pytest.mark.asyncio
    async def test_d02_custom_int_applied(self, tmp_path: Path):
        config = tmp_path / "settings.toml"
        config.write_text("[editor]\nsidebar_width = 40\n")
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.wait_for_scheduled_animations()
            assert app.sidebar is not None
            assert app.sidebar.size.width == 40

    @pytest.mark.asyncio
    async def test_d03_percentage_applied(self, tmp_path: Path):
        config = tmp_path / "settings.toml"
        config.write_text('[editor]\nsidebar_width = "30%"\n')
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.wait_for_scheduled_animations()
            # 30% of 120 = 36, allow rounding tolerance
            assert app.sidebar is not None
            assert 34 <= app.sidebar.size.width <= 38

    @pytest.mark.asyncio
    async def test_d04_runtime_resize_after_config(self, tmp_path: Path):
        config = tmp_path / "settings.toml"
        config.write_text("[editor]\nsidebar_width = 40\n")
        ws = tmp_path / "ws"
        ws.mkdir()
        app = make_app(ws, user_config_path=config)
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.wait_for_scheduled_animations()
            assert app.sidebar is not None
            assert app.sidebar.size.width == 40
            # Runtime resize should still work
            assert app.sidebar is not None
            app.sidebar.styles.width = 50
            await pilot.wait_for_scheduled_animations()
            assert app.sidebar is not None
            assert app.sidebar.size.width == 50
