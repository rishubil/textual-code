"""
Tests for keyboard shortcuts customization (Settings -> Shortcuts).

Covers:
1. Config: get_keybindings_path, load_keybindings, save_keybindings
2. Binding patch: _apply_custom_keybindings patches class BINDINGS
3. Startup: app loads and applies custom keybindings on __init__
4. App attributes: action_show_shortcuts exists, F1 binding present
5. Command palette: "Show keyboard shortcuts" entry
6. ShowShortcutsScreen: has DataTable, rows include known bindings
7. RebindKeyScreen: captures keys, Escape dismisses, Apply returns result
8. Integration: set_keybinding saves to config file
"""

import pytest

from textual_code.app import MainView, TextualCode, _apply_custom_keybindings
from textual_code.config import (
    get_keybindings_path,
    load_keybindings,
    save_keybindings,
)
from textual_code.modals import RebindKeyScreen, RebindResult, ShowShortcutsScreen

from .conftest import make_app

# ---------------------------------------------------------------------------
# Group 1: Config
# ---------------------------------------------------------------------------


def test_load_keybindings_empty_when_no_file(tmp_path):
    kb = tmp_path / "keybindings.toml"
    result = load_keybindings(kb)
    assert result == {}


def test_load_keybindings_reads_custom_binding(tmp_path):
    kb = tmp_path / "keybindings.toml"
    kb.write_text('[bindings]\nsave = "ctrl+alt+s"\n')
    result = load_keybindings(kb)
    assert result["save"] == "ctrl+alt+s"


def test_save_keybindings_writes_toml(tmp_path):
    kb = tmp_path / "keybindings.toml"
    save_keybindings({"save": "ctrl+alt+s"}, kb)
    assert kb.exists()
    text = kb.read_text()
    assert "[bindings]" in text
    assert "ctrl+alt+s" in text


def test_save_keybindings_round_trip(tmp_path):
    kb = tmp_path / "keybindings.toml"
    save_keybindings({"save": "ctrl+alt+s", "new_editor": "ctrl+m"}, kb)
    loaded = load_keybindings(kb)
    assert loaded["save"] == "ctrl+alt+s"
    assert loaded["new_editor"] == "ctrl+m"


def test_get_keybindings_path_uses_same_dir_as_settings(tmp_path):
    settings_path = tmp_path / "settings.toml"
    kb_path = get_keybindings_path(settings_path)
    assert kb_path.parent == tmp_path
    assert kb_path.name == "keybindings.toml"


# ---------------------------------------------------------------------------
# Group 2: Binding patch
# ---------------------------------------------------------------------------


def test_apply_custom_keybindings_patches_mainview(restore_bindings):
    original_key = next(b.key for b in MainView.BINDINGS if b.action == "save")
    assert original_key == "ctrl+s"
    _apply_custom_keybindings({"save": "ctrl+alt+s"})
    new_key = next(b.key for b in MainView.BINDINGS if b.action == "save")
    assert new_key == "ctrl+alt+s"


def test_apply_custom_keybindings_ignores_unknown_action(restore_bindings):
    original = list(MainView.BINDINGS)
    _apply_custom_keybindings({"nonexistent_action": "ctrl+x"})
    assert [b.key for b in MainView.BINDINGS] == [b.key for b in original]


def test_custom_keybinding_applied_on_startup(tmp_path, restore_bindings):
    settings_path = tmp_path / "settings.toml"
    kb_path = get_keybindings_path(settings_path)
    save_keybindings({"save": "ctrl+alt+s"}, kb_path)
    TextualCode(
        workspace_path=tmp_path,
        with_open_file=None,
        user_config_path=settings_path,
    )
    new_key = next(b.key for b in MainView.BINDINGS if b.action == "save")
    assert new_key == "ctrl+alt+s"


# ---------------------------------------------------------------------------
# Group 3: App attributes
# ---------------------------------------------------------------------------


def test_action_show_shortcuts_exists(tmp_path):
    app = TextualCode(workspace_path=tmp_path, with_open_file=None)
    assert callable(getattr(app, "action_show_shortcuts", None))


def test_set_keybinding_method_exists(tmp_path):
    app = TextualCode(workspace_path=tmp_path, with_open_file=None)
    assert callable(getattr(app, "set_keybinding", None))


def test_f1_binding_in_textualcode_bindings():
    keys = [b.key for b in TextualCode.BINDINGS]
    assert "f1" in keys


# ---------------------------------------------------------------------------
# Group 4: Command palette
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_command_palette_has_show_shortcuts(workspace):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        commands = list(app.get_system_commands(app.screen))
        titles = [c.title for c in commands]
        assert "Show keyboard shortcuts" in titles


# ---------------------------------------------------------------------------
# Group 5: ShowShortcutsScreen
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_show_shortcuts_screen_has_datatable(workspace):
    from textual.widgets import DataTable

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_show_shortcuts()
        await pilot.pause()
        assert isinstance(app.screen, ShowShortcutsScreen)
        table = app.screen.query_one(DataTable)
        assert len(table.rows) > 0


@pytest.mark.asyncio
async def test_show_shortcuts_screen_rows_include_save(workspace):
    from textual.widgets import DataTable

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_show_shortcuts()
        await pilot.pause()
        table = app.screen.query_one(DataTable)
        row_keys = {str(rk.value) for rk in table.rows}
        assert "save" in row_keys


# ---------------------------------------------------------------------------
# Group 6: RebindKeyScreen
# ---------------------------------------------------------------------------


def test_rebind_result_dataclass():
    result = RebindResult(is_cancelled=False, action_name="save", new_key="ctrl+alt+s")
    assert not result.is_cancelled
    assert result.action_name == "save"
    assert result.new_key == "ctrl+alt+s"


def test_rebind_result_cancelled():
    result = RebindResult(is_cancelled=True, action_name=None, new_key=None)
    assert result.is_cancelled
    assert result.new_key is None


@pytest.mark.asyncio
async def test_rebind_screen_apply_disabled_until_key_pressed(workspace):
    from textual.widgets import Button

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(RebindKeyScreen("save", "Save", "ctrl+s"))
        await pilot.pause()
        assert isinstance(app.screen, RebindKeyScreen)
        btn = app.screen.query_one("#apply", Button)
        assert btn.disabled


@pytest.mark.asyncio
async def test_rebind_screen_captures_key(workspace):
    from textual.widgets import Button, Label

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(RebindKeyScreen("save", "Save", "ctrl+s"))
        await pilot.pause()
        await pilot.press("ctrl+k")
        await pilot.pause()
        btn = app.screen.query_one("#apply", Button)
        assert not btn.disabled
        label = app.screen.query_one("#captured_key", Label)
        assert "ctrl+k" in str(label.content)


@pytest.mark.asyncio
async def test_rebind_screen_escape_dismisses_screen(workspace):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(RebindKeyScreen("save", "Save", "ctrl+s"))
        await pilot.pause()
        assert isinstance(app.screen, RebindKeyScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, RebindKeyScreen)


@pytest.mark.asyncio
async def test_rebind_screen_dismiss_returns_result(workspace):
    """Directly dismissing with a result works correctly."""
    results = []
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            RebindKeyScreen("save", "Save", "ctrl+s"),
            callback=results.append,
        )
        await pilot.pause()
        app.screen.dismiss(
            RebindResult(is_cancelled=False, action_name="save", new_key="ctrl+k")
        )
        await pilot.pause()
        assert len(results) == 1
        assert not results[0].is_cancelled
        assert results[0].new_key == "ctrl+k"
        assert results[0].action_name == "save"


# ---------------------------------------------------------------------------
# Group 7: Integration — set_keybinding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_keybinding_saves_to_config(workspace, tmp_path, restore_bindings):
    settings_path = tmp_path / "settings.toml"
    app = TextualCode(
        workspace_path=workspace,
        with_open_file=None,
        user_config_path=settings_path,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        app.set_keybinding("save", "ctrl+alt+s")
        await pilot.pause()
        kb_path = get_keybindings_path(settings_path)
        assert kb_path.exists()
        loaded = load_keybindings(kb_path)
        assert loaded["save"] == "ctrl+alt+s"
