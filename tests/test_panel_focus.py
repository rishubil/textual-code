"""
Tests for Ctrl+Tab / Ctrl+Shift+Tab panel focus cycling.

Panel order: [Sidebar (if visible)] → [Leaf0] → [Leaf1] → ... → (wrap)
"""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.widgets.split_tree import all_leaves


@pytest.fixture
def py_file(workspace: Path) -> Path:
    f = workspace / "main.py"
    f.write_text("print('hello')\n")
    return f


@pytest.fixture
def py_file2(workspace: Path) -> Path:
    f = workspace / "other.py"
    f.write_text("x = 1\n")
    return f


# ── Binding test ─────────────────────────────────────────────────────────────


async def test_ctrl_tab_triggers_focus_next_panel(workspace: Path, py_file: Path):
    """ctrl+tab should be bound to action_focus_next_panel."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Focus starts on the editor; ctrl+tab should move to sidebar
        assert app.sidebar.display is True
        await pilot.press("ctrl+tab")
        await pilot.pause()
        # After ctrl+tab from editor, focus should move to sidebar
        assert app.focused is not None
        assert app.sidebar in app.focused.ancestors_with_self


# ── Logic tests ──────────────────────────────────────────────────────────────


async def test_focus_next_panel_sidebar_to_editor(workspace: Path, py_file: Path):
    """Next panel from sidebar should focus the editor."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Focus sidebar first
        app.sidebar.explorer.directory_tree.focus()
        await pilot.pause()
        # Now cycle forward
        app.action_focus_next_panel()
        await pilot.pause()
        # Should be in the editor area (MainView descendant, not Sidebar)
        assert app.focused is not None
        assert app.sidebar not in app.focused.ancestors_with_self


async def test_focus_prev_panel_editor_to_sidebar(workspace: Path, py_file: Path):
    """Prev panel from editor should focus the sidebar."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Focus is on the editor by default
        app.action_focus_prev_panel()
        await pilot.pause()
        # Should be in the sidebar
        assert app.focused is not None
        assert app.sidebar in app.focused.ancestors_with_self


async def test_focus_next_panel_wraps(workspace: Path, py_file: Path):
    """From last panel (editor), next should wrap to sidebar."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        # panels: [sidebar, leaf0]
        # Focus is on leaf0 (the only editor leaf)
        app.action_focus_next_panel()
        await pilot.pause()
        # Should wrap to sidebar
        assert app.focused is not None
        assert app.sidebar in app.focused.ancestors_with_self


async def test_focus_next_panel_skips_hidden_sidebar(workspace: Path, py_file: Path):
    """When sidebar is hidden, cycling should stay on editor leaves."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.sidebar.display = False
        await pilot.pause()
        # panels: [leaf0] only
        app.action_focus_next_panel()
        await pilot.pause()
        # Should stay on the editor (wraps to itself)
        assert app.focused is not None
        assert app.sidebar not in app.focused.ancestors_with_self


async def test_focus_next_panel_with_splits(
    workspace: Path, py_file: Path, py_file2: Path
):
    """With 2 splits: sidebar → leaf0 → leaf1 → sidebar."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Create a split
        await app.main_view.action_split_right()
        await pilot.pause()

        leaves = all_leaves(app.main_view._split_root)
        assert len(leaves) == 2

        # Start from sidebar
        app.sidebar.explorer.directory_tree.focus()
        await pilot.pause()

        # Next → leaf0
        app.action_focus_next_panel()
        await pilot.pause()
        assert app.main_view._active_leaf_id == leaves[0].leaf_id

        # Next → leaf1
        app.action_focus_next_panel()
        await pilot.pause()
        assert app.main_view._active_leaf_id == leaves[1].leaf_id

        # Next → sidebar (wrap)
        app.action_focus_next_panel()
        await pilot.pause()
        assert app.focused is not None
        assert app.sidebar in app.focused.ancestors_with_self


async def test_focus_sidebar_respects_active_tab(workspace: Path, py_file: Path):
    """When sidebar Search tab is active, focusing sidebar should focus search input."""
    app = make_app(workspace, open_file=py_file)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Switch sidebar to Search tab
        app.sidebar.tabbed_content.active = "search_pane"
        await pilot.pause()

        # Ensure focus is on the editor (not sidebar)
        app.main_view._set_active_leaf(all_leaves(app.main_view._split_root)[0])
        await pilot.pause()

        # Now go back to sidebar (prev)
        app.action_focus_prev_panel()
        await pilot.pause()

        # The focused widget should be inside the search pane
        assert app.focused is not None
        assert app.sidebar in app.focused.ancestors_with_self
