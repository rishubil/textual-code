"""
Command palette shortcut display tests.

Verifies that SystemCommand descriptions include keyboard shortcut hints
for commands that have associated key bindings.
"""

from pathlib import Path

import pytest
from textual.app import App
from textual.binding import Binding

from tests.conftest import make_app


def _get_commands(app) -> dict[str, str]:
    """Return {title: help} mapping for all SystemCommands."""
    return {cmd.title: cmd.help for cmd in app.get_system_commands(app.screen)}


@pytest.fixture
async def commands(tmp_path: Path) -> dict[str, str]:
    """Collect all system commands from a running app."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        return _get_commands(app)


async def test_save_file_shows_ctrl_s(tmp_path: Path):
    """'Save' command description contains Ctrl+S shortcut."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    assert "Ctrl+S" in cmds["Save"]


async def test_save_all_shows_ctrl_shift_s(tmp_path: Path):
    """'Save All' command description contains Ctrl+Shift+S."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    assert "Ctrl+Shift+S" in cmds["Save All"]


async def test_new_file_shows_ctrl_n(tmp_path: Path):
    """'New Untitled File' command description contains Ctrl+N."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    assert "Ctrl+N" in cmds["New Untitled File"]


async def test_close_file_shows_ctrl_w(tmp_path: Path):
    """'Close Editor' command description contains Ctrl+W."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    assert "Ctrl+W" in cmds["Close Editor"]


async def test_close_all_files_shows_ctrl_shift_w(tmp_path: Path):
    """'Close All Editors' command description contains Ctrl+Shift+W."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    assert "Ctrl+Shift+W" in cmds["Close All Editors"]


async def test_toggle_sidebar_shows_ctrl_b(tmp_path: Path):
    """'Toggle Sidebar' command description contains Ctrl+B."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    assert "Ctrl+B" in cmds["Toggle Sidebar"]


async def test_goto_line_shows_ctrl_g(tmp_path: Path):
    """'Go to Line/Column...' command description contains Ctrl+G."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    assert "Ctrl+G" in cmds["Go to Line/Column..."]


async def test_find_shows_ctrl_f(tmp_path: Path):
    """'Find' command description contains Ctrl+F."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    assert "Ctrl+F" in cmds["Find"]


async def test_replace_shows_ctrl_h(tmp_path: Path):
    """'Replace' command description contains Ctrl+H."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    assert "Ctrl+H" in cmds["Replace"]


async def test_select_all_occurrences_shows_ctrl_shift_l(tmp_path: Path):
    """'Select All Occurrences of Find Match' description contains Ctrl+Shift+L."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    assert "Ctrl+Shift+L" in cmds["Select All Occurrences of Find Match"]


async def test_close_split_shows_ctrl_shift_backslash(tmp_path: Path):
    """'Close Editor Group' description contains Ctrl+Shift+\\."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    assert "Ctrl+Shift+\\" in cmds["Close Editor Group"]


async def test_focus_next_split_command_exists(tmp_path: Path):
    """'Focus Next Group' command is registered in system commands."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    assert "Focus Next Group" in cmds


async def test_focus_prev_split_command_exists(tmp_path: Path):
    """'Focus Previous Group' command is registered in system commands."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    assert "Focus Previous Group" in cmds


# ── Verify already-existing shortcuts still work ──────────────────────────────


async def test_add_cursor_below_still_shows_shortcut(tmp_path: Path):
    """'Add Cursor Below' description still contains Ctrl+Alt+Down."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    assert "Ctrl+Alt+Down" in cmds["Add Cursor Below"]


async def test_add_next_occurrence_still_shows_shortcut(tmp_path: Path):
    """'Add Selection to Next Find Match' description still contains Ctrl+D."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    assert "Ctrl+D" in cmds["Add Selection to Next Find Match"]


async def test_find_in_workspace_still_shows_shortcut(tmp_path: Path):
    """'Find in Files' description still contains Ctrl+Shift+F."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    assert "Ctrl+Shift+F" in cmds["Find in Files"]


# ── Verify Textual built-in commands are excluded ─────────────────────────────

_TEXTUAL_BUILTIN_TITLES = {"Keys", "Screenshot", "Maximize", "Minimize", "Theme"}


async def test_no_textual_builtin_commands(tmp_path: Path):
    """Textual's default built-in commands must not appear in the palette."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    found = _TEXTUAL_BUILTIN_TITLES & set(cmds)
    assert not found, f"Built-in commands should be removed: {found}"


async def test_project_quit_command_exists(tmp_path: Path):
    """The project's own 'Quit' command must still appear in the palette."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    assert "Quit" in cmds


async def test_quit_shows_ctrl_q(tmp_path: Path):
    """'Quit' command description contains Ctrl+Q shortcut."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    assert "Ctrl+Q" in cmds["Quit"]


async def test_open_file_shows_ctrl_o(tmp_path: Path):
    """'Open File...' command description contains Ctrl+O shortcut."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        cmds = _get_commands(app)
    assert "Ctrl+O" in cmds["Open File..."]


async def test_open_file_ctrl_o_opens_modal(tmp_path: Path):
    """Pressing Ctrl+O opens the PathSearchModal."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+o")
        await pilot.wait_for_scheduled_animations()
        assert app.screen.__class__.__name__ == "PathSearchModal"


# ── Guard: Textual base App.BINDINGS must be reflected in COMMAND_REGISTRY ────


def test_textual_base_bindings_reflected_in_registry():
    """Every non-system Textual App.BINDINGS action must have a matching
    default_key in COMMAND_REGISTRY to prevent shortcut hints from going
    missing in the command palette."""
    from textual_code.command_registry import COMMAND_REGISTRY

    registry_by_action = {e.action: e for e in COMMAND_REGISTRY}

    for raw_binding in App.BINDINGS:
        if not isinstance(raw_binding, Binding):
            continue
        # Skip system bindings (e.g. ctrl+c help_quit) — not user-facing
        if raw_binding.system:
            continue
        if raw_binding.action not in registry_by_action:
            continue  # Not a project command — skip
        entry = registry_by_action[raw_binding.action]
        assert entry.default_key, (
            f"Textual App.BINDINGS has '{raw_binding.key} → {raw_binding.action}' "
            f"but COMMAND_REGISTRY entry '{raw_binding.action}' has no default_key. "
            f"Add default_key='{raw_binding.key}' to prevent missing shortcut hints."
        )
