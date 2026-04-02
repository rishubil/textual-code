"""Regression tests for user-settings isolation in tests (#16).

Verifies that the autouse ``_isolate_user_config`` fixture prevents real
user settings from leaking into tests.
"""

import textual_code.config
from textual_code.app import TextualCode
from textual_code.config import (
    DEFAULT_EDITOR_SETTINGS,
    save_user_editor_settings,
)


def test_get_user_config_path_is_isolated(tmp_path):
    """get_user_config_path() returns a path inside tmp_path, not real home."""
    path = textual_code.config.get_user_config_path()
    assert tmp_path in path.parents


def test_defaults_used_when_no_user_config(tmp_path):
    """TextualCode without explicit user_config_path should use defaults."""
    app = TextualCode(workspace_path=tmp_path, with_open_file=None)
    assert app.default_ui_theme == DEFAULT_EDITOR_SETTINGS["ui_theme"]
    assert app.default_syntax_theme == DEFAULT_EDITOR_SETTINGS["syntax_theme"]
    assert app.default_indent_size == DEFAULT_EDITOR_SETTINGS["indent_size"]


def test_isolation_redirects_to_test_path(tmp_path):
    """Settings written to the isolated path should be picked up by the app."""
    save_user_editor_settings({"ui_theme": "nord", "indent_size": 8})
    app = TextualCode(workspace_path=tmp_path, with_open_file=None)
    assert app.default_ui_theme == "nord"
    assert app.default_indent_size == 8
