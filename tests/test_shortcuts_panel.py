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
9. ShortcutDisplay config: load_shortcut_display, save_keybindings_file
10. ShortcutSettingsScreen: checkboxes, validation, result
11. Display settings integration: footer/palette visibility, footer priority
"""

import pytest

from textual_code.app import MainView, TextualCode, _apply_custom_keybindings
from textual_code.config import (
    FooterOrders,
    ShortcutDisplayEntry,
    get_keybindings_path,
    load_footer_orders,
    load_keybindings,
    load_shortcut_display,
    save_keybindings,
    save_keybindings_file,
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
# Group 1b: Shortcut display config
# ---------------------------------------------------------------------------


def test_load_shortcut_display_empty_when_no_file(tmp_path):
    kb = tmp_path / "keybindings.toml"
    result = load_shortcut_display(kb)
    assert result == {}


def test_load_shortcut_display_reads_entries(tmp_path):
    kb = tmp_path / "keybindings.toml"
    kb.write_text("[display.save]\npalette = false\n")
    result = load_shortcut_display(kb)
    assert "save" in result
    assert result["save"].palette is False


def test_load_shortcut_display_backward_compat_no_display(tmp_path):
    kb = tmp_path / "keybindings.toml"
    kb.write_text('[bindings]\nsave = "ctrl+alt+s"\n')
    result = load_shortcut_display(kb)
    assert result == {}


def test_save_keybindings_file_writes_display_section(tmp_path):
    kb = tmp_path / "keybindings.toml"
    display = {"save": ShortcutDisplayEntry(palette=False)}
    save_keybindings_file({"save": "ctrl+s"}, display, kb)
    assert kb.exists()
    text = kb.read_text()
    assert "[bindings]" in text
    assert "ctrl+s" in text
    assert "[display.save]" in text
    assert "palette = false" in text


def test_save_keybindings_file_round_trip(tmp_path):
    kb = tmp_path / "keybindings.toml"
    display = {
        "save": ShortcutDisplayEntry(palette=True),
        "find": ShortcutDisplayEntry(palette=False),
    }
    save_keybindings_file({"save": "ctrl+s"}, display, kb)
    loaded_bindings = load_keybindings(kb)
    loaded_display = load_shortcut_display(kb)
    assert loaded_bindings["save"] == "ctrl+s"
    assert loaded_display["save"].palette is True
    assert loaded_display["find"].palette is False


def test_save_keybindings_preserves_display_section(tmp_path):
    """save_keybindings should preserve existing [display] sections."""
    kb = tmp_path / "keybindings.toml"
    display = {"save": ShortcutDisplayEntry(palette=False)}
    save_keybindings_file({"save": "ctrl+s"}, display, kb)
    save_keybindings({"save": "ctrl+alt+s"}, kb)
    loaded_display = load_shortcut_display(kb)
    assert loaded_display["save"].palette is False


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
# Group 6b: ShortcutSettingsScreen
# ---------------------------------------------------------------------------


def test_shortcut_settings_result_dataclass():
    from textual_code.modals import ShortcutSettingsResult

    result = ShortcutSettingsResult(
        is_cancelled=False,
        action_name="save",
        new_key="ctrl+alt+s",
        palette_visible=False,
    )
    assert not result.is_cancelled
    assert result.action_name == "save"
    assert result.new_key == "ctrl+alt+s"
    assert result.palette_visible is False


def test_shortcut_settings_result_cancelled():
    from textual_code.modals import ShortcutSettingsResult

    result = ShortcutSettingsResult(is_cancelled=True)
    assert result.is_cancelled
    assert result.new_key is None


@pytest.mark.asyncio
async def test_shortcut_settings_screen_renders(workspace):
    from textual.widgets import Button, Checkbox

    from textual_code.modals import ShortcutSettingsScreen

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            ShortcutSettingsScreen(
                action_name="save",
                description="Save",
                current_key="ctrl+s",
                palette_visible=True,
            )
        )
        await pilot.pause()
        assert isinstance(app.screen, ShortcutSettingsScreen)
        palette_cb = app.screen.query_one("#palette_visible", Checkbox)
        assert palette_cb.value is True
        app.screen.query_one("#save", Button)
        app.screen.query_one("#cancel", Button)


@pytest.mark.asyncio
async def test_shortcut_settings_screen_save_returns_result(workspace):
    from textual.widgets import Button

    from textual_code.modals import ShortcutSettingsResult, ShortcutSettingsScreen

    results = []
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            ShortcutSettingsScreen(
                action_name="save",
                description="Save",
                current_key="ctrl+s",
                palette_visible=True,
            ),
            callback=results.append,
        )
        await pilot.pause()
        save_btn = app.screen.query_one("#save", Button)
        save_btn.press()
        await pilot.pause()
        assert len(results) == 1
        r = results[0]
        assert isinstance(r, ShortcutSettingsResult)
        assert not r.is_cancelled
        assert r.palette_visible is True


@pytest.mark.asyncio
async def test_shortcut_settings_screen_cancel(workspace):
    from textual.widgets import Button

    from textual_code.modals import ShortcutSettingsScreen

    results = []
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            ShortcutSettingsScreen(
                action_name="save",
                description="Save",
                current_key="ctrl+s",
                palette_visible=True,
            ),
            callback=results.append,
        )
        await pilot.pause()
        cancel_btn = app.screen.query_one("#cancel", Button)
        cancel_btn.press()
        await pilot.pause()
        assert len(results) == 1
        assert results[0].is_cancelled


# ---------------------------------------------------------------------------
# Group 6c: ShowShortcutsScreen opens ShortcutSettingsScreen
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_show_shortcuts_row_click_opens_settings_screen(workspace):
    from textual.widgets import DataTable

    from textual_code.modals import ShortcutSettingsScreen

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_show_shortcuts()
        await pilot.pause()
        assert isinstance(app.screen, ShowShortcutsScreen)
        table = app.screen.query_one(DataTable)
        # Simulate row selection on "save"
        table.move_cursor(row=0)
        table.action_select_cursor()
        await pilot.pause()
        assert isinstance(app.screen, ShortcutSettingsScreen)


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


# ---------------------------------------------------------------------------
# Group 8: Integration — palette display config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_palette_hides_command_when_palette_false(
    workspace, tmp_path, restore_bindings
):
    settings_path = tmp_path / "settings.toml"
    app = TextualCode(
        workspace_path=workspace,
        with_open_file=None,
        user_config_path=settings_path,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        app.set_shortcut_display(
            "save",
            ShortcutDisplayEntry(palette=False),
        )
        await pilot.pause()
        commands = list(app.get_system_commands(app.screen))
        titles = [c.title for c in commands]
        assert "Save file" not in titles


@pytest.mark.asyncio
async def test_palette_shows_command_by_default(workspace):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        commands = list(app.get_system_commands(app.screen))
        titles = [c.title for c in commands]
        assert "Save file" in titles


# ---------------------------------------------------------------------------
# Group 9: Footer order config
# ---------------------------------------------------------------------------


def test_load_footer_orders_empty_when_no_file(tmp_path):
    kb = tmp_path / "keybindings.toml"
    result = load_footer_orders(kb)
    assert result.for_area("editor") is None


def test_load_footer_orders_reads_list(tmp_path):
    kb = tmp_path / "keybindings.toml"
    kb.write_text('[footer.editor]\norder = ["save", "find", "replace"]\n')
    result = load_footer_orders(kb)
    assert result.for_area("editor") == ["save", "find", "replace"]


def test_load_footer_orders_backward_compat_no_section(tmp_path):
    kb = tmp_path / "keybindings.toml"
    kb.write_text('[bindings]\nsave = "ctrl+s"\n')
    result = load_footer_orders(kb)
    assert result.for_area("editor") is None


def test_save_keybindings_file_includes_footer_orders(tmp_path):
    kb = tmp_path / "keybindings.toml"
    orders = FooterOrders(areas={"editor": ["save", "find"]})
    save_keybindings_file({}, {}, kb, footer_orders=orders)
    loaded = load_footer_orders(kb)
    assert loaded.for_area("editor") == ["save", "find"]


def test_save_keybindings_file_round_trip_all_sections(tmp_path):
    kb = tmp_path / "keybindings.toml"
    display = {"save": ShortcutDisplayEntry(palette=False)}
    orders = FooterOrders(areas={"editor": ["save", "find", "replace"]})
    save_keybindings_file({"save": "ctrl+s"}, display, kb, footer_orders=orders)
    assert load_keybindings(kb)["save"] == "ctrl+s"
    assert load_shortcut_display(kb)["save"].palette is False
    assert load_footer_orders(kb).for_area("editor") == ["save", "find", "replace"]


@pytest.mark.asyncio
async def test_set_footer_order_saves_and_applies(
    workspace, tmp_path, restore_bindings
):
    from textual_code.widgets.ordered_footer import OrderedFooter

    settings_path = tmp_path / "settings.toml"
    app = TextualCode(
        workspace_path=workspace,
        with_open_file=None,
        user_config_path=settings_path,
        skip_sidebar=True,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        # Use app-level bindings (new_editor, toggle_sidebar) which are always active
        app.set_footer_order(["new_editor"], area="editor")
        await pilot.pause()
        # Verify saved to disk
        kb_path = get_keybindings_path(settings_path)
        loaded = load_footer_orders(kb_path)
        assert loaded.for_area("editor") == ["new_editor"]
        # Verify footer respects order
        footer = app.query_one(OrderedFooter)
        footer_actions = {
            b.action
            for (_, b, _, _) in app.screen.active_bindings.values()
            if footer._should_show_in_footer(b)
        }
        assert "new_editor" in footer_actions
        # toggle_sidebar not in order should be hidden
        assert "toggle_sidebar" not in footer_actions


@pytest.mark.asyncio
async def test_get_footer_priority_with_order(workspace, tmp_path, restore_bindings):
    settings_path = tmp_path / "settings.toml"
    app = TextualCode(
        workspace_path=workspace,
        with_open_file=None,
        user_config_path=settings_path,
        skip_sidebar=True,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        app.set_footer_order(["find", "save"], area="editor")
        await pilot.pause()
        assert app.get_footer_priority("find") == 0
        assert app.get_footer_priority("save") == 1


@pytest.mark.asyncio
async def test_get_footer_priority_falls_back_to_action_order(workspace):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        # No footer_order set — falls back to ACTION_ORDER
        priority = app.get_footer_priority("save")
        assert priority == 0
        priority = app.get_footer_priority("nonexistent")
        assert priority > 0
