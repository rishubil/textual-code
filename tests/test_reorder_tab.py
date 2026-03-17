"""
Tests for tab reorder commands (move tab left/right within a tab group).

Covers:
- Move active tab one position right
- Move active tab one position left
- No-op at boundaries (leftmost tab left, rightmost tab right)
- No-op with single tab
- MarkdownPreviewPane tab reorder
- Command registration in get_system_commands
"""

from pathlib import Path

import pytest

from tests.conftest import make_app
from textual_code.widgets.draggable_tabs_content import DraggableTabbedContent

# ── Helpers ────────────────────────────────────────────────────────────────


def get_tab_order(tc: DraggableTabbedContent) -> list[str]:
    """Return the ordered list of pane IDs from the TabbedContent widget."""
    return tc.get_ordered_pane_ids()


# ── Fixtures ───────────────────────────────────────────────────────────────


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


@pytest.fixture
def py_file3(workspace: Path) -> Path:
    f = workspace / "third.py"
    f.write_text("y = 2\n")
    return f


@pytest.fixture
def md_file(workspace: Path) -> Path:
    f = workspace / "readme.md"
    f.write_text("# Hello\n\nWorld\n")
    return f


# ── Reorder right ───────────────────────────────────────────────────────


async def test_reorder_tab_right(
    workspace: Path, py_file: Path, py_file2: Path, py_file3: Path
):
    """Move active tab one position one position to the right."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Open two more files → tabs: [py_file, py_file2, py_file3]
        await app.main_view.action_open_code_editor(py_file2)
        await pilot.pause()
        await app.main_view.action_open_code_editor(py_file3)
        await pilot.pause()

        tc = app.main_view.tabbed_content
        order_before = get_tab_order(tc)
        assert len(order_before) == 3

        # Activate first tab
        tc.active = order_before[0]
        await pilot.pause()
        first_pane_id = order_before[0]

        # Move right
        app.main_view.action_reorder_tab_right()
        await pilot.pause()

        order_after = get_tab_order(tc)
        # First tab should now be at index 1
        assert order_after[1] == first_pane_id
        # Active tab unchanged
        assert tc.active == first_pane_id


# ── Reorder left ─────────────────────────────────────────────────────


async def test_reorder_tab_left(
    workspace: Path, py_file: Path, py_file2: Path, py_file3: Path
):
    """Move active tab one position one position to the left."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        await app.main_view.action_open_code_editor(py_file2)
        await pilot.pause()
        await app.main_view.action_open_code_editor(py_file3)
        await pilot.pause()

        tc = app.main_view.tabbed_content
        order_before = get_tab_order(tc)
        last_pane_id = order_before[2]

        # Activate last tab
        tc.active = last_pane_id
        await pilot.pause()

        # Move left
        app.main_view.action_reorder_tab_left()
        await pilot.pause()

        order_after = get_tab_order(tc)
        # Last tab should now be at index 1
        assert order_after[1] == last_pane_id
        assert tc.active == last_pane_id


# ── No-op at boundaries ──────────────────────────────────────────────────


async def test_reorder_tab_right_at_end(workspace: Path, py_file: Path, py_file2: Path):
    """Forward at the last position is a no-op."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        await app.main_view.action_open_code_editor(py_file2)
        await pilot.pause()

        tc = app.main_view.tabbed_content
        order_before = get_tab_order(tc)
        last_pane_id = order_before[-1]

        # Activate last tab
        tc.active = last_pane_id
        await pilot.pause()

        # Move right — should be no-op
        app.main_view.action_reorder_tab_right()
        await pilot.pause()

        assert get_tab_order(tc) == order_before


async def test_reorder_tab_left_at_start(
    workspace: Path, py_file: Path, py_file2: Path
):
    """Backward at the first position is a no-op."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        await app.main_view.action_open_code_editor(py_file2)
        await pilot.pause()

        tc = app.main_view.tabbed_content
        order_before = get_tab_order(tc)
        first_pane_id = order_before[0]

        # Activate first tab
        tc.active = first_pane_id
        await pilot.pause()

        # Move left — should be no-op
        app.main_view.action_reorder_tab_left()
        await pilot.pause()

        assert get_tab_order(tc) == order_before


# ── Single tab ────────────────────────────────────────────────────────────


async def test_reorder_tab_single_tab(workspace: Path, py_file: Path):
    """Reorder is a no-op when only one tab is open."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        tc = app.main_view.tabbed_content
        order_before = get_tab_order(tc)
        assert len(order_before) == 1

        app.main_view.action_reorder_tab_right()
        await pilot.pause()
        assert get_tab_order(tc) == order_before

        app.main_view.action_reorder_tab_left()
        await pilot.pause()
        assert get_tab_order(tc) == order_before


# ── MarkdownPreviewPane tab reorder ───────────────────────────────────────


async def test_reorder_markdown_preview_tab(
    workspace: Path, py_file: Path, md_file: Path
):
    """MarkdownPreviewPane tabs can also be reordered."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()

        # Open markdown file, then open its preview
        await app.main_view.action_open_code_editor(md_file)
        await pilot.pause()
        await app.main_view.action_open_markdown_preview_tab()
        await pilot.pause()

        tc = app.main_view.tabbed_content
        order_before = get_tab_order(tc)
        # Preview tab should be the last one (3 tabs: py_file, md_file, preview)
        assert len(order_before) == 3
        preview_pane_id = order_before[2]

        # Active tab is the preview tab
        assert tc.active == preview_pane_id

        # Move left
        app.main_view.action_reorder_tab_left()
        await pilot.pause()

        order_after = get_tab_order(tc)
        # Preview tab should now be at index 1
        assert order_after[1] == preview_pane_id


# ── Command registration ─────────────────────────────────────────────────


async def test_reorder_commands_registered(workspace: Path, py_file: Path):
    """Reorder tab commands are registered in get_system_commands."""
    app = make_app(workspace, open_file=py_file, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        cmds = {cmd.title for cmd in app.get_system_commands(app.screen)}

        assert "Reorder tab right" in cmds
        assert "Reorder tab left" in cmds
