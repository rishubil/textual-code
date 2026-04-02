"""
Transform selected text case tests.

Tests for the uppercase/lowercase conversion feature (Issue #38).
Available via command palette only — no keybindings.
"""

from pathlib import Path

import pytest
from textual.widgets.text_area import Selection

from tests.conftest import make_app

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mixed_case_file(workspace: Path) -> Path:
    f = workspace / "mixed.txt"
    f.write_text("Hello World\nfoo BAR\n")
    return f


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_editor(app):
    """Return the MultiCursorTextArea from the active code editor."""
    return app.main_view.get_active_code_editor().editor


# ── Transform to uppercase ───────────────────────────────────────────────────


async def test_transform_uppercase(workspace: Path, mixed_case_file: Path):
    """Selecting 'Hello' and transforming to uppercase produces 'HELLO'."""
    app = make_app(workspace, light=True, open_file=mixed_case_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        ta.selection = Selection(start=(0, 0), end=(0, 5))
        ta.action_transform_uppercase()
        await pilot.wait_for_scheduled_animations()
        lines = ta.text.split("\n")
        assert lines[0] == "HELLO World"
        assert lines[1] == "foo BAR"


# ── Transform to lowercase ──────────────────────────────────────────────────


async def test_transform_lowercase(workspace: Path, mixed_case_file: Path):
    """Selecting 'BAR' and transforming to lowercase produces 'bar'."""
    app = make_app(workspace, light=True, open_file=mixed_case_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        ta.selection = Selection(start=(1, 4), end=(1, 7))
        ta.action_transform_lowercase()
        await pilot.wait_for_scheduled_animations()
        lines = ta.text.split("\n")
        assert lines[0] == "Hello World"
        assert lines[1] == "foo bar"


# ── Collapsed cursor auto-selects word ───────────────────────────────────────


async def test_transform_uppercase_collapsed_cursor_selects_word(
    workspace: Path, mixed_case_file: Path
):
    """Collapsed cursor auto-selects word under cursor (VSCode behavior)."""
    app = make_app(workspace, light=True, open_file=mixed_case_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        # Cursor inside "Hello" → auto-selects "Hello" → "HELLO"
        ta.cursor_location = (0, 3)
        ta.action_transform_uppercase()
        await pilot.wait_for_scheduled_animations()
        lines = ta.text.split("\n")
        assert lines[0] == "HELLO World"


async def test_transform_lowercase_collapsed_cursor_selects_word(
    workspace: Path, mixed_case_file: Path
):
    """Collapsed cursor auto-selects word under cursor (VSCode behavior)."""
    app = make_app(workspace, light=True, open_file=mixed_case_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        # Cursor inside "BAR" at (1, 5) → auto-selects "BAR" → "bar"
        ta.cursor_location = (1, 5)
        ta.action_transform_lowercase()
        await pilot.wait_for_scheduled_animations()
        lines = ta.text.split("\n")
        assert lines[1] == "foo bar"


async def test_transform_collapsed_cursor_on_whitespace_noop(
    workspace: Path, mixed_case_file: Path
):
    """Collapsed cursor on whitespace/non-word char is still a no-op."""
    app = make_app(workspace, light=True, open_file=mixed_case_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        original = ta.text
        # Cursor at the space between "Hello" and "World"
        ta.cursor_location = (0, 5)
        ta.action_transform_uppercase()
        await pilot.wait_for_scheduled_animations()
        assert ta.text == original


# ── Multiline ────────────────────────────────────────────────────────────────


async def test_transform_uppercase_multiline(workspace: Path, mixed_case_file: Path):
    """Selecting across lines transforms all selected text to uppercase."""
    app = make_app(workspace, light=True, open_file=mixed_case_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        # Select "World\nfoo"
        ta.selection = Selection(start=(0, 6), end=(1, 3))
        ta.action_transform_uppercase()
        await pilot.wait_for_scheduled_animations()
        lines = ta.text.split("\n")
        assert lines[0] == "Hello WORLD"
        assert lines[1] == "FOO BAR"


# ── Selection preserved ─────────────────────────────────────────────────────


async def test_transform_preserves_selection(workspace: Path, mixed_case_file: Path):
    """After transforming, the selection covers the same range."""
    app = make_app(workspace, light=True, open_file=mixed_case_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        ta.selection = Selection(start=(0, 0), end=(0, 5))
        ta.action_transform_uppercase()
        await pilot.wait_for_scheduled_animations()
        assert ta.selection.start == (0, 0)
        assert ta.selection.end == (0, 5)


# ── Backward selection ───────────────────────────────────────────────────────


async def test_transform_backward_selection(workspace: Path, mixed_case_file: Path):
    """Backward (right-to-left) selection transforms correctly."""
    app = make_app(workspace, light=True, open_file=mixed_case_file)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        # Select "Hello" backwards (end before start)
        ta.selection = Selection(start=(0, 5), end=(0, 0))
        ta.action_transform_uppercase()
        await pilot.wait_for_scheduled_animations()
        lines = ta.text.split("\n")
        assert lines[0] == "HELLO World"


# ── Command palette ──────────────────────────────────────────────────────────


async def test_transform_command_palette(workspace: Path):
    """All 7 transform commands are available in the system command palette."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        commands = list(app.get_system_commands(app.screen))
        titles = [cmd.title for cmd in commands]
        assert "Transform to Uppercase" in titles
        assert "Transform to Lowercase" in titles
        assert "Transform to Title Case" in titles
        assert "Transform to Snake Case" in titles
        assert "Transform to Camel Case" in titles
        assert "Transform to Kebab Case" in titles
        assert "Transform to Pascal Case" in titles


# ── Selection length adjustment ─────────────────────────────────────────────


async def test_snake_case_selection_grows(workspace: Path):
    """snake_case adds underscores, selection end column must increase."""
    f = workspace / "sel.txt"
    f.write_text("parseHTMLString\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        # "parseHTMLString" (15 chars) → "parse_html_string" (17 chars)
        ta.selection = Selection(start=(0, 0), end=(0, 15))
        ta.action_transform_snake_case()
        await pilot.wait_for_scheduled_animations()
        assert ta.document.get_line(0) == "parse_html_string"
        assert ta.selection == Selection((0, 0), (0, 17))


async def test_pascal_case_selection_shrinks(workspace: Path):
    """PascalCase removes separators, selection end column must decrease."""
    f = workspace / "sel.txt"
    f.write_text("hello world\n")
    app = make_app(workspace, light=True, open_file=f)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ta = await _get_editor(app)
        # "hello world" (11 chars) → "HelloWorld" (10 chars)
        ta.selection = Selection(start=(0, 0), end=(0, 11))
        ta.action_transform_pascal_case()
        await pilot.wait_for_scheduled_animations()
        assert ta.document.get_line(0) == "HelloWorld"
        assert ta.selection == Selection((0, 0), (0, 10))
