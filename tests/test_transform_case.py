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
        await pilot.pause()
        ta = await _get_editor(app)
        ta.selection = Selection(start=(0, 0), end=(0, 5))
        ta.action_transform_uppercase()
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines[0] == "HELLO World"
        assert lines[1] == "foo BAR"


# ── Transform to lowercase ──────────────────────────────────────────────────


async def test_transform_lowercase(workspace: Path, mixed_case_file: Path):
    """Selecting 'BAR' and transforming to lowercase produces 'bar'."""
    app = make_app(workspace, light=True, open_file=mixed_case_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_editor(app)
        ta.selection = Selection(start=(1, 4), end=(1, 7))
        ta.action_transform_lowercase()
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines[0] == "Hello World"
        assert lines[1] == "foo bar"


# ── No-op cases ──────────────────────────────────────────────────────────────


async def test_transform_uppercase_no_selection_noop(
    workspace: Path, mixed_case_file: Path
):
    """Transforming with no selection (just a cursor) is a no-op."""
    app = make_app(workspace, light=True, open_file=mixed_case_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_editor(app)
        original = ta.text
        ta.cursor_location = (0, 3)
        ta.action_transform_uppercase()
        await pilot.pause()
        assert ta.text == original


async def test_transform_lowercase_no_selection_noop(
    workspace: Path, mixed_case_file: Path
):
    """Transforming with no selection (just a cursor) is a no-op."""
    app = make_app(workspace, light=True, open_file=mixed_case_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_editor(app)
        original = ta.text
        ta.cursor_location = (1, 0)
        ta.action_transform_lowercase()
        await pilot.pause()
        assert ta.text == original


# ── Multiline ────────────────────────────────────────────────────────────────


async def test_transform_uppercase_multiline(workspace: Path, mixed_case_file: Path):
    """Selecting across lines transforms all selected text to uppercase."""
    app = make_app(workspace, light=True, open_file=mixed_case_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_editor(app)
        # Select "World\nfoo"
        ta.selection = Selection(start=(0, 6), end=(1, 3))
        ta.action_transform_uppercase()
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines[0] == "Hello WORLD"
        assert lines[1] == "FOO BAR"


# ── Selection preserved ─────────────────────────────────────────────────────


async def test_transform_preserves_selection(workspace: Path, mixed_case_file: Path):
    """After transforming, the selection covers the same range."""
    app = make_app(workspace, light=True, open_file=mixed_case_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_editor(app)
        ta.selection = Selection(start=(0, 0), end=(0, 5))
        ta.action_transform_uppercase()
        await pilot.pause()
        assert ta.selection.start == (0, 0)
        assert ta.selection.end == (0, 5)


# ── Backward selection ───────────────────────────────────────────────────────


async def test_transform_backward_selection(workspace: Path, mixed_case_file: Path):
    """Backward (right-to-left) selection transforms correctly."""
    app = make_app(workspace, light=True, open_file=mixed_case_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        ta = await _get_editor(app)
        # Select "Hello" backwards (end before start)
        ta.selection = Selection(start=(0, 5), end=(0, 0))
        ta.action_transform_uppercase()
        await pilot.pause()
        lines = ta.text.split("\n")
        assert lines[0] == "HELLO World"


# ── Command palette ──────────────────────────────────────────────────────────


async def test_transform_command_palette(workspace: Path):
    """Transform commands are available in the system command palette."""
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        commands = list(app.get_system_commands(app.screen))
        titles = [cmd.title for cmd in commands]
        assert "Transform to uppercase" in titles
        assert "Transform to lowercase" in titles
