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
    ShortcutDisplayEntry,
    get_keybindings_path,
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
    kb.write_text(
        "[display.save]\nfooter = true\npalette = false\nfooter_priority = 1\n"
    )
    result = load_shortcut_display(kb)
    assert "save" in result
    assert result["save"].footer is True
    assert result["save"].palette is False
    assert result["save"].footer_priority == 1


def test_load_shortcut_display_partial_entry(tmp_path):
    kb = tmp_path / "keybindings.toml"
    kb.write_text("[display.find]\nfooter = false\n")
    result = load_shortcut_display(kb)
    assert result["find"].footer is False
    assert result["find"].palette is None
    assert result["find"].footer_priority is None


def test_load_shortcut_display_ignores_malformed(tmp_path):
    kb = tmp_path / "keybindings.toml"
    kb.write_text('[display.save]\nfooter = "not_a_bool"\n')
    result = load_shortcut_display(kb)
    assert result == {} or result.get("save", ShortcutDisplayEntry()).footer is None


def test_load_shortcut_display_backward_compat_no_display(tmp_path):
    kb = tmp_path / "keybindings.toml"
    kb.write_text('[bindings]\nsave = "ctrl+alt+s"\n')
    result = load_shortcut_display(kb)
    assert result == {}


def test_save_keybindings_file_writes_both_sections(tmp_path):
    kb = tmp_path / "keybindings.toml"
    display = {
        "save": ShortcutDisplayEntry(footer=True, palette=False, footer_priority=1)
    }
    save_keybindings_file({"save": "ctrl+s"}, display, kb)
    assert kb.exists()
    text = kb.read_text()
    assert "[bindings]" in text
    assert "ctrl+s" in text
    assert "[display.save]" in text
    assert "footer = true" in text
    assert "palette = false" in text
    assert "footer_priority = 1" in text


def test_save_keybindings_file_round_trip(tmp_path):
    kb = tmp_path / "keybindings.toml"
    display = {
        "save": ShortcutDisplayEntry(footer=True, palette=True, footer_priority=1),
        "find": ShortcutDisplayEntry(footer=False, palette=True, footer_priority=2),
    }
    save_keybindings_file({"save": "ctrl+s"}, display, kb)
    loaded_bindings = load_keybindings(kb)
    loaded_display = load_shortcut_display(kb)
    assert loaded_bindings["save"] == "ctrl+s"
    assert loaded_display["save"].footer is True
    assert loaded_display["save"].footer_priority == 1
    assert loaded_display["find"].footer is False
    assert loaded_display["find"].footer_priority == 2


def test_save_keybindings_preserves_display_section(tmp_path):
    """save_keybindings should preserve existing [display] sections."""
    kb = tmp_path / "keybindings.toml"
    display = {
        "save": ShortcutDisplayEntry(footer=True, palette=False, footer_priority=1)
    }
    save_keybindings_file({"save": "ctrl+s"}, display, kb)
    # Now save only keybindings — display should be preserved
    save_keybindings({"save": "ctrl+alt+s"}, kb)
    loaded_display = load_shortcut_display(kb)
    assert loaded_display["save"].footer is True


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
        footer_visible=True,
        palette_visible=False,
        footer_priority=1,
    )
    assert not result.is_cancelled
    assert result.action_name == "save"
    assert result.new_key == "ctrl+alt+s"
    assert result.footer_visible is True
    assert result.palette_visible is False
    assert result.footer_priority == 1


def test_shortcut_settings_result_cancelled():
    from textual_code.modals import ShortcutSettingsResult

    result = ShortcutSettingsResult(is_cancelled=True)
    assert result.is_cancelled
    assert result.new_key is None


@pytest.mark.asyncio
async def test_shortcut_settings_screen_renders(workspace):
    from textual.widgets import Button, Checkbox, Input

    from textual_code.modals import ShortcutSettingsScreen

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            ShortcutSettingsScreen(
                action_name="save",
                description="Save",
                current_key="ctrl+s",
                footer_visible=True,
                palette_visible=True,
                footer_priority=1,
            )
        )
        await pilot.pause()
        assert isinstance(app.screen, ShortcutSettingsScreen)
        # Verify checkboxes exist
        footer_cb = app.screen.query_one("#footer_visible", Checkbox)
        palette_cb = app.screen.query_one("#palette_visible", Checkbox)
        assert footer_cb.value is True
        assert palette_cb.value is True
        # Verify priority input
        priority_input = app.screen.query_one("#footer_priority", Input)
        assert priority_input.value == "1"
        # Verify buttons exist
        app.screen.query_one("#save", Button)
        app.screen.query_one("#cancel", Button)


@pytest.mark.asyncio
async def test_shortcut_settings_screen_save_returns_result(workspace):
    from textual.widgets import Button, Checkbox

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
                footer_visible=True,
                palette_visible=True,
                footer_priority=1,
            ),
            callback=results.append,
        )
        await pilot.pause()
        # Toggle footer off
        footer_cb = app.screen.query_one("#footer_visible", Checkbox)
        footer_cb.toggle()
        await pilot.pause()
        # Click save
        save_btn = app.screen.query_one("#save", Button)
        save_btn.press()
        await pilot.pause()
        assert len(results) == 1
        r = results[0]
        assert isinstance(r, ShortcutSettingsResult)
        assert not r.is_cancelled
        assert r.footer_visible is False
        assert r.palette_visible is True
        assert r.footer_priority == 1


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
                footer_visible=True,
                palette_visible=True,
                footer_priority=1,
            ),
            callback=results.append,
        )
        await pilot.pause()
        cancel_btn = app.screen.query_one("#cancel", Button)
        cancel_btn.press()
        await pilot.pause()
        assert len(results) == 1
        assert results[0].is_cancelled


@pytest.mark.asyncio
async def test_shortcut_settings_screen_validates_priority(workspace):
    from textual.widgets import Input

    from textual_code.modals import ShortcutSettingsScreen

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            ShortcutSettingsScreen(
                action_name="save",
                description="Save",
                current_key="ctrl+s",
                footer_visible=True,
                palette_visible=True,
                footer_priority=1,
            ),
        )
        await pilot.pause()
        priority_input = app.screen.query_one("#footer_priority", Input)
        # The input has restrict=r"[0-9]*", so non-digit characters
        # are rejected at the widget level. Verify the restrict is set.
        assert priority_input.restrict is not None
        assert priority_input.max_length == 3


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
# Group 8: Integration — set_shortcut_display
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_shortcut_display_saves_to_config(
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
            ShortcutDisplayEntry(footer=False, palette=True, footer_priority=5),
        )
        await pilot.pause()
        kb_path = get_keybindings_path(settings_path)
        loaded_display = load_shortcut_display(kb_path)
        assert loaded_display["save"].footer is False
        assert loaded_display["save"].footer_priority == 5


@pytest.mark.asyncio
async def test_get_footer_priority_returns_custom(
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
            ShortcutDisplayEntry(footer_priority=42),
        )
        await pilot.pause()
        assert app.get_footer_priority("save") == 42


@pytest.mark.asyncio
async def test_get_footer_priority_falls_back_to_action_order(workspace):
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        # "save" is index 0 in ACTION_ORDER
        priority = app.get_footer_priority("save")
        assert priority == 0
        # Unknown action falls back to len(ACTION_ORDER)
        priority = app.get_footer_priority("nonexistent")
        assert priority > 0


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
# Group 9: Integration — footer display config applied at runtime
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_footer_shows_binding_when_display_footer_true(
    workspace, tmp_path, restore_bindings
):
    """Setting footer=True for a hidden binding makes it appear in footer."""
    from textual_code.widgets.ordered_footer import OrderedFooter

    settings_path = tmp_path / "settings.toml"
    app = TextualCode(
        workspace_path=workspace,
        with_open_file=None,
        user_config_path=settings_path,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        # show_shortcuts is show=False by default, verify it's not in footer
        footer = app.query_one(OrderedFooter)
        footer_actions_before = {
            b.action
            for (_, b, _, _) in app.screen.active_bindings.values()
            if footer._should_show_in_footer(b)
        }
        assert "show_shortcuts" not in footer_actions_before
        # Now set footer=True for show_shortcuts
        app.set_shortcut_display(
            "show_shortcuts",
            ShortcutDisplayEntry(footer=True),
        )
        await pilot.pause()
        footer_actions_after = {
            b.action
            for (_, b, _, _) in app.screen.active_bindings.values()
            if footer._should_show_in_footer(b)
        }
        assert "show_shortcuts" in footer_actions_after


@pytest.mark.asyncio
async def test_footer_hides_binding_when_display_footer_false(
    workspace, tmp_path, restore_bindings
):
    """Setting footer=False for a visible binding removes it from footer."""
    from textual_code.widgets.ordered_footer import OrderedFooter

    settings_path = tmp_path / "settings.toml"
    app = TextualCode(
        workspace_path=workspace,
        with_open_file=None,
        user_config_path=settings_path,
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        footer = app.query_one(OrderedFooter)
        # "new_editor" has show=True by default
        footer_actions_before = {
            b.action
            for (_, b, _, _) in app.screen.active_bindings.values()
            if footer._should_show_in_footer(b)
        }
        assert "new_editor" in footer_actions_before
        # Now hide it
        app.set_shortcut_display(
            "new_editor",
            ShortcutDisplayEntry(footer=False),
        )
        await pilot.pause()
        footer_actions_after = {
            b.action
            for (_, b, _, _) in app.screen.active_bindings.values()
            if footer._should_show_in_footer(b)
        }
        assert "new_editor" not in footer_actions_after
