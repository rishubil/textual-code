"""
Command palette shortcut display tests.

Verifies that SystemCommand descriptions include keyboard shortcut hints
for commands that have associated key bindings.
"""

from pathlib import Path

import pytest

from tests.conftest import make_app


def _get_commands(app) -> dict[str, str]:
    """Return {title: help} mapping for all SystemCommands."""
    return {cmd.title: cmd.help for cmd in app.get_system_commands(app.screen)}


@pytest.fixture
async def commands(tmp_path: Path) -> dict[str, str]:
    """Collect all system commands from a running app."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        return _get_commands(app)


async def test_save_file_shows_ctrl_s(tmp_path: Path):
    """'Save file' command description contains Ctrl+S shortcut."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = _get_commands(app)
    assert "Ctrl+S" in cmds["Save file"]


async def test_save_all_shows_ctrl_shift_s(tmp_path: Path):
    """'Save all files' command description contains Ctrl+Shift+S."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = _get_commands(app)
    assert "Ctrl+Shift+S" in cmds["Save all files"]


async def test_new_file_shows_ctrl_n(tmp_path: Path):
    """'New file' command description contains Ctrl+N."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = _get_commands(app)
    assert "Ctrl+N" in cmds["New file"]


async def test_close_file_shows_ctrl_w(tmp_path: Path):
    """'Close file' command description contains Ctrl+W."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = _get_commands(app)
    assert "Ctrl+W" in cmds["Close file"]


async def test_close_all_files_shows_ctrl_shift_w(tmp_path: Path):
    """'Close all files' command description contains Ctrl+Shift+W."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = _get_commands(app)
    assert "Ctrl+Shift+W" in cmds["Close all files"]


async def test_toggle_sidebar_shows_ctrl_b(tmp_path: Path):
    """'Toggle sidebar' command description contains Ctrl+B."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = _get_commands(app)
    assert "Ctrl+B" in cmds["Toggle sidebar"]


async def test_goto_line_shows_ctrl_g(tmp_path: Path):
    """'Goto line' command description contains Ctrl+G."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = _get_commands(app)
    assert "Ctrl+G" in cmds["Goto line"]


async def test_find_shows_ctrl_f(tmp_path: Path):
    """'Find' command description contains Ctrl+F."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = _get_commands(app)
    assert "Ctrl+F" in cmds["Find"]


async def test_replace_shows_ctrl_h(tmp_path: Path):
    """'Replace' command description contains Ctrl+H."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = _get_commands(app)
    assert "Ctrl+H" in cmds["Replace"]


async def test_select_all_occurrences_shows_ctrl_shift_l(tmp_path: Path):
    """'Select all occurrences' command description contains Ctrl+Shift+L."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = _get_commands(app)
    assert "Ctrl+Shift+L" in cmds["Select all occurrences"]


async def test_close_split_shows_ctrl_shift_backslash(tmp_path: Path):
    """'Close split' command description contains Ctrl+Shift+\\."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = _get_commands(app)
    assert "Ctrl+Shift+\\" in cmds["Close split"]


async def test_focus_next_split_command_exists(tmp_path: Path):
    """'Focus next split' command is registered in system commands."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = _get_commands(app)
    assert "Focus next split" in cmds


async def test_focus_prev_split_command_exists(tmp_path: Path):
    """'Focus previous split' command is registered in system commands."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = _get_commands(app)
    assert "Focus previous split" in cmds


# ── Verify already-existing shortcuts still work ──────────────────────────────


async def test_add_cursor_below_still_shows_shortcut(tmp_path: Path):
    """'Add cursor below' description still contains Ctrl+Alt+Down."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = _get_commands(app)
    assert "Ctrl+Alt+Down" in cmds["Add cursor below"]


async def test_add_next_occurrence_still_shows_shortcut(tmp_path: Path):
    """'Add next occurrence' description still contains Ctrl+D."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = _get_commands(app)
    assert "Ctrl+D" in cmds["Add next occurrence"]


async def test_find_in_workspace_still_shows_shortcut(tmp_path: Path):
    """'Find in Workspace' description still contains Ctrl+Shift+F."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = _get_commands(app)
    assert "Ctrl+Shift+F" in cmds["Find in Workspace"]


# ── Verify Textual built-in commands are excluded ─────────────────────────────

_TEXTUAL_BUILTIN_TITLES = {"Keys", "Screenshot", "Maximize", "Minimize", "Theme"}


async def test_no_textual_builtin_commands(tmp_path: Path):
    """Textual's default built-in commands must not appear in the palette."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = _get_commands(app)
    found = _TEXTUAL_BUILTIN_TITLES & set(cmds)
    assert not found, f"Built-in commands should be removed: {found}"


async def test_project_quit_command_exists(tmp_path: Path):
    """The project's own 'Quit' command must still appear in the palette."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = _get_commands(app)
    assert "Quit" in cmds
