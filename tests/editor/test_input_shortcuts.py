"""
Standard text editing shortcuts in Input widgets.

Issue #54: Input widgets (find bar, workspace search, modals) should support
the same basic editing shortcuts as the code editor where applicable.

Covered shortcuts:
- Ctrl+A: select all text (not move cursor to home)
- Ctrl+D: no action when Input is focused (not add_next_occurrence)
"""

from pathlib import Path

from textual.widgets import Input

from tests.conftest import make_app

# ── Ctrl+A selects all in find input ─────────────────────────────────────────


async def test_ctrl_a_selects_all_in_find_input(workspace: Path):
    """Ctrl+A in find input should select all text, not move cursor to home."""
    f = workspace / "test.txt"
    f.write_text("hello world\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+f")
        await pilot.wait_for_scheduled_animations()
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.wait_for_scheduled_animations()

        find_input = app.focused
        assert isinstance(find_input, Input), f"Expected Input, got {type(find_input)}"
        assert find_input.value == "hello"

        # Ctrl+A should select all, then typing replaces everything
        await pilot.press("ctrl+a")
        await pilot.press("x")
        await pilot.wait_for_scheduled_animations()
        assert find_input.value == "x", (
            f"Expected 'x' (Ctrl+A selected all, replaced), got '{find_input.value}'"
        )


# ── Ctrl+A selects all in workspace search input ────────────────────────────


async def test_ctrl_a_selects_all_in_workspace_search(workspace: Path):
    """Ctrl+A in workspace search input should select all text."""
    f = workspace / "test.txt"
    f.write_text("hello world\n")
    app = make_app(workspace, open_file=f)  # full app (sidebar needed)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Open workspace search via shortcut
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()

        ws_input = app.focused
        assert isinstance(ws_input, Input), f"Expected Input, got {type(ws_input)}"

        await pilot.press("h", "e", "l", "l", "o")
        await pilot.wait_for_scheduled_animations()
        assert ws_input.value == "hello"

        await pilot.press("ctrl+a")
        await pilot.press("x")
        await pilot.wait_for_scheduled_animations()
        assert ws_input.value == "x", (
            f"Expected 'x' (Ctrl+A selected all, then replaced), got '{ws_input.value}'"
        )


# ── Ctrl+D no action in find input ──────────────────────────────────────────


async def test_ctrl_d_no_action_in_find_input(workspace: Path):
    """Ctrl+D in find input should do nothing (not trigger add_next_occurrence)."""
    f = workspace / "test.txt"
    f.write_text("hello world\nhello again\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+f")
        await pilot.wait_for_scheduled_animations()
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.wait_for_scheduled_animations()

        find_input = app.focused
        assert isinstance(find_input, Input), f"Expected Input, got {type(find_input)}"
        assert find_input.value == "hello"

        # Ctrl+D should do nothing — text should remain unchanged
        await pilot.press("ctrl+d")
        await pilot.wait_for_scheduled_animations()
        assert find_input.value == "hello", (
            f"Expected 'hello' (no change), got '{find_input.value}'"
        )


# ── Regression: Ctrl+A still works in code editor ───────────────────────────


async def test_ctrl_a_still_works_in_editor(workspace: Path):
    """Ctrl+A in the code editor should still select all text."""
    f = workspace / "test.txt"
    f.write_text("line1\nline2\nline3\n")
    app = make_app(workspace, open_file=f, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        text_area = editor.editor

        # Ctrl+A should select all text in the editor
        await pilot.press("ctrl+a")
        await pilot.wait_for_scheduled_animations()
        assert text_area.selected_text == "line1\nline2\nline3\n"
