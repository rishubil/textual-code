"""Tests for sidebar horizontal scrolling (#70).

Explorer should constrain the tree height so the horizontal scrollbar
remains visible.  Search results (ListView) should allow horizontal
scrolling so that long result lines remain accessible.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Input, ListView

from tests.conftest import make_app
from textual_code.widgets.explorer import FilteredDirectoryTree
from textual_code.widgets.workspace_search import WorkspaceSearchPane

LONG_FILENAME = "a_very_long_filename_that_exceeds_sidebar_width_easily.py"


def _populate_wide_workspace(ws: Path, *, num_files: int = 50) -> None:
    """Create a workspace with one long-named file and many short-named files."""
    (ws / LONG_FILENAME).write_text("print('hello')\n")
    for i in range(num_files):
        (ws / f"file_{i:03d}.py").write_text("")


# ---------------------------------------------------------------------------
# Explorer: horizontal scrollbar must not be occluded by the footer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_explorer_horizontal_scrollbar_above_footer(workspace: Path) -> None:
    """Horizontal scrollbar region must not extend into the footer row."""
    _populate_wide_workspace(workspace)

    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        for _ in range(10):
            await pilot.pause()

        tree = app.query_one(FilteredDirectoryTree)

        assert tree.show_horizontal_scrollbar is True, (
            "Horizontal scrollbar should be enabled"
        )

        hsb = tree._horizontal_scrollbar
        assert hsb is not None and hsb.display, (
            "Horizontal scrollbar should be displayed"
        )

        # The scrollbar must not extend to the very last row of the screen,
        # where the Footer is rendered and would occlude it.
        screen_height = app.screen.size.height
        scrollbar_bottom = hsb.region.y + hsb.region.height
        assert scrollbar_bottom < screen_height, (
            f"Horizontal scrollbar bottom ({scrollbar_bottom}) must be above "
            f"the screen bottom ({screen_height}) to avoid footer occlusion"
        )


# ---------------------------------------------------------------------------
# Explorer: tree height must be constrained so scrollbar fits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_explorer_tree_has_constrained_height(workspace: Path) -> None:
    """Tree height must be constrained so the horizontal scrollbar fits."""
    _populate_wide_workspace(workspace)

    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        for _ in range(10):
            await pilot.pause()

        tree = app.query_one(FilteredDirectoryTree)

        assert tree.size.height < tree.virtual_size.height, (
            f"Tree height ({tree.size.height}) should be less than "
            f"virtual height ({tree.virtual_size.height}) — "
            f"unconstrained height hides the horizontal scrollbar"
        )
        assert tree.virtual_size.width > tree.size.width, (
            f"Tree virtual width ({tree.virtual_size.width}) should exceed "
            f"widget width ({tree.size.width}) for long filenames"
        )
        assert tree.show_horizontal_scrollbar is True, (
            "Horizontal scrollbar should be visible when content overflows"
        )


# ---------------------------------------------------------------------------
# Search: horizontal scrolling should be enabled on results ListView
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_results_horizontal_scroll(workspace: Path) -> None:
    """Search results with long text should be horizontally scrollable."""
    long_line = "x" * 200
    (workspace / "wide.py").write_text(f"{long_line}\n")
    app = make_app(workspace)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.main_view.action_find_in_files()
        await pilot.pause()

        pane = app.query_one(WorkspaceSearchPane)
        pane.query_one("#ws-query", Input).value = "xxx"
        pane._run_search()
        # Give threaded search worker time to finish
        await pilot.pause(0.5)

        results_list = app.query_one("#ws-results", ListView)

        assert results_list.styles.overflow_x == "auto", (
            f"Search results overflow_x is '{results_list.styles.overflow_x}', "
            f"expected 'auto'"
        )
        assert results_list.virtual_size.width > results_list.size.width, (
            f"Results virtual width ({results_list.virtual_size.width}) should "
            f"exceed widget width ({results_list.size.width}) for long lines"
        )
