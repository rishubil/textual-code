"""Tests for PathSearchModal — fzf-like path search with streaming support."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_app


@pytest.fixture(autouse=True)
def clear_path_search_cache():
    """Clear PathSearchModal class-level cache before/after each test."""
    from textual_code.modals import PathSearchModal

    PathSearchModal._cache.clear()
    PathSearchModal._cache_dirty.clear()
    yield
    PathSearchModal._cache.clear()
    PathSearchModal._cache_dirty.clear()


def _populate_cache(workspace: Path, cache_key: str, files: list[Path]) -> None:
    """Pre-populate PathSearchModal class-level cache for testing."""
    from textual_code.modals import PathSearchModal

    PathSearchModal._cache[(workspace, cache_key)] = tuple(sorted(files))


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def sample_files(workspace: Path) -> list[Path]:
    """Create sample files and return their relative paths (sorted)."""
    files = ["alpha.py", "beta.txt", "gamma/delta.py", "gamma/epsilon.txt"]
    for f in files:
        p = workspace / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {f}\n")
    return sorted(Path(f) for f in files)


# ── Cycle 1: Basic modal behavior ────────────────────────────────────────────


async def test_path_search_modal_mounts(workspace: Path, sample_files: list[Path]):
    """PathSearchModal mounts with Input and OptionList widgets."""
    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    _populate_cache(workspace, "files", sample_files)
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, PathSearchModal)
        assert modal.query_one("#path-search-input") is not None
        assert modal.query_one("#path-search-results") is not None


async def test_path_search_modal_shows_cached_paths(
    workspace: Path, sample_files: list[Path]
):
    """When cache is populated, files are shown immediately."""
    from textual.widgets import OptionList

    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    _populate_cache(workspace, "files", sample_files)
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.pause()
        ol = app.screen.query_one("#path-search-results", OptionList)
        assert ol.option_count == len(sample_files)


async def test_path_search_modal_fuzzy_search(
    workspace: Path, sample_files: list[Path]
):
    """Typing a query filters results via fuzzy matching."""
    from textual.widgets import OptionList

    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    _populate_cache(workspace, "files", sample_files)
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.pause()
        # Type "alpha" to search
        await pilot.press("a", "l", "p", "h", "a")
        await pilot.pause()
        ol = app.screen.query_one("#path-search-results", OptionList)
        assert ol.option_count >= 1
        # The top result should contain "alpha"
        option = ol.get_option_at_index(0)
        assert "alpha" in str(option.prompt).lower()


async def test_path_search_modal_escape_dismisses(
    workspace: Path, sample_files: list[Path]
):
    """Pressing Escape dismisses the modal with None."""
    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    _populate_cache(workspace, "files", sample_files)
    dismissed_with: list[Path | None] = []

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            ),
            callback=lambda result: dismissed_with.append(result),
        )
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert len(dismissed_with) == 1
        assert dismissed_with[0] is None


async def test_path_search_modal_applies_filter(
    workspace: Path, sample_files: list[Path]
):
    """path_filter excludes matching paths from results."""
    from textual.widgets import OptionList

    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    # Filter out .txt files
    _populate_cache(workspace, "files", sample_files)
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
                path_filter=lambda p: p.suffix != ".txt",
            )
        )
        await pilot.pause()
        ol = app.screen.query_one("#path-search-results", OptionList)
        # Only .py files should remain
        py_files = [f for f in sample_files if f.suffix == ".py"]
        assert ol.option_count == len(py_files)


async def test_path_search_modal_displays_relative_paths(
    workspace: Path, sample_files: list[Path]
):
    """Paths are displayed relative to workspace, not absolute."""
    from textual.widgets import OptionList

    from textual_code.commands import _read_workspace_paths
    from textual_code.modals import PathSearchModal

    # _read_workspace_paths returns absolute paths
    abs_paths = sorted(workspace / f for f in sample_files)
    _populate_cache(workspace, "paths", abs_paths)
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_paths,
                cache_key="paths",
            )
        )
        await pilot.pause()
        ol = app.screen.query_one("#path-search-results", OptionList)
        # All displayed paths should be relative (no leading /)
        for i in range(ol.option_count):
            displayed = str(ol.get_option_at_index(i).prompt)
            assert not displayed.startswith("/"), (
                f"Path should be relative: {displayed}"
            )


async def test_path_search_modal_sorted_discovery(
    workspace: Path,
):
    """Discovery results are sorted alphabetically."""
    from textual.widgets import OptionList

    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    # Create files in non-alphabetical order
    for name in ["zebra.py", "apple.py", "mango.py"]:
        (workspace / name).write_text(f"# {name}\n")

    cached = sorted([Path("apple.py"), Path("mango.py"), Path("zebra.py")])
    _populate_cache(workspace, "files", cached)

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.pause()
        ol = app.screen.query_one("#path-search-results", OptionList)
        names = [str(ol.get_option_at_index(i).prompt) for i in range(ol.option_count)]
        assert names == sorted(names)


# ── Cycle 2: App integration ─────────────────────────────────────────────────


async def test_action_opens_path_search_modal(
    workspace: Path, sample_files: list[Path]
):
    """action_open_file_with_command_palette opens PathSearchModal."""
    from textual_code.modals import PathSearchModal

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_open_file_with_command_palette()
        await pilot.pause()
        assert isinstance(app.screen, PathSearchModal)


async def test_file_search_opens_selected_file(
    workspace: Path, sample_files: list[Path]
):
    """Selecting a file in PathSearchModal opens it in the editor."""
    from textual.widgets import OptionList

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_open_file_with_command_palette()
        await pilot.pause()
        # Type to search for "alpha"
        await pilot.press("a", "l", "p", "h", "a")
        # Wait for background fuzzy matching worker to complete
        await pilot.pause(0.5)
        ol = app.screen.query_one("#path-search-results", OptionList)
        assert ol.option_count >= 1, "No search results found"
        # Select the highlighted option
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()  # Extra pause for file open async processing
        # Check that the file was opened
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.path is not None
        assert editor.path.name == "alpha.py"


async def test_path_search_modal_search_without_cache(
    workspace: Path, sample_files: list[Path]
):
    """Search should work when cached_paths is None (no pre-populated cache)."""
    from textual.widgets import OptionList

    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
            )
        )
        await pilot.pause()
        await pilot.press("a", "l", "p", "h", "a")
        await pilot.pause(1.0)
        ol = app.screen.query_one("#path-search-results", OptionList)
        assert ol.option_count >= 1, "No search results when cache is None"


# ── Cycle 3: Generation counter race condition fix ────────────────────────────


async def test_stale_search_results_discarded(
    workspace: Path, sample_files: list[Path]
):
    """Stale search results (wrong generation) must be discarded."""
    from textual.widgets import OptionList

    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    _populate_cache(workspace, "files", sample_files)
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, PathSearchModal)
        # Type to get results
        await pilot.press("a", "l", "p", "h", "a")
        await pilot.pause()
        ol = modal.query_one("#path-search-results", OptionList)
        current_count = ol.option_count
        assert current_count >= 1
        # Simulate a stale _apply_results call with wrong generation
        stale_gen = modal._search_generation - 1
        modal._apply_results("alpha", stale_gen, [])
        # Results should NOT have been overwritten by stale call
        assert ol.option_count == current_count, (
            "Stale results overwrote current display"
        )


# ── Cycle 4: Widget-internal cache ────────────────────────────────────────────


async def test_cache_hit_on_second_open(workspace: Path, sample_files: list[Path]):
    """Second open of PathSearchModal should hit class-level cache."""
    from textual.widgets import OptionList

    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    # Ensure clean cache
    PathSearchModal._cache.clear()

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        # First open — triggers scan
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.pause(1.0)
        # Dismiss
        await pilot.press("escape")
        await pilot.pause()
        # Verify cache was populated
        assert (workspace, "files") in PathSearchModal._cache
        # Second open — should hit cache
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.pause()
        ol = app.screen.query_one("#path-search-results", OptionList)
        # Should have results immediately from cache
        assert ol.option_count >= 1, "Cache miss on second open"


async def test_invalidate_cache_marks_dirty(workspace: Path, sample_files: list[Path]):
    """invalidate_cache should mark workspace as dirty."""
    from textual_code.modals import PathSearchModal

    PathSearchModal._cache.clear()
    PathSearchModal._cache_dirty.clear()
    # Pre-populate cache
    PathSearchModal._cache[(workspace, "files")] = tuple(sample_files)
    # Invalidate
    PathSearchModal.invalidate_cache(workspace)
    # Should be marked dirty (per-key granularity)
    assert (workspace, "files") in PathSearchModal._cache_dirty
    # Cache entry should still exist (lazy invalidation)
    assert (workspace, "files") in PathSearchModal._cache


async def test_dirty_cache_rescan_no_duplicates(
    workspace: Path, sample_files: list[Path]
):
    """Re-scan after dirty cache must not duplicate entries."""
    from textual.widgets import OptionList

    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    # Pre-populate cache and mark dirty
    _populate_cache(workspace, "files", sample_files)
    PathSearchModal.invalidate_cache(workspace)

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        # Wait for scan to complete
        await pilot.pause(1.0)
        ol = app.screen.query_one("#path-search-results", OptionList)
        # Count should equal unique files, not doubled
        displayed = [
            str(ol.get_option_at_index(i).prompt) for i in range(ol.option_count)
        ]
        assert len(displayed) == len(set(displayed)), (
            f"Duplicate entries found: {displayed}"
        )


# ── Cycle 5: Keyboard navigation ─────────────────────────────────────────────


async def test_keyboard_navigation_down_up(workspace: Path, sample_files: list[Path]):
    """Down/Up keys should navigate results while Input keeps focus."""
    from textual.widgets import Input, OptionList

    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    _populate_cache(workspace, "files", sample_files)
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, PathSearchModal)
        ol = modal.query_one("#path-search-results", OptionList)
        # Discovery mode — should have items
        assert ol.option_count >= 2
        # Press down to highlight first item
        await pilot.press("down")
        await pilot.pause()
        assert ol.highlighted is not None
        initial_highlight = ol.highlighted
        # Press down again
        await pilot.press("down")
        await pilot.pause()
        assert ol.highlighted == initial_highlight + 1
        # Press up
        await pilot.press("up")
        await pilot.pause()
        assert ol.highlighted == initial_highlight
        # Input should still have focus
        inp = modal.query_one("#path-search-input", Input)
        assert inp.has_focus


# ── Cycle 6: Performance regression ──────────────────────────────────────────


async def test_large_cache_discovery_and_navigation(workspace: Path):
    """With many cached files, discovery should show _MAX_DISCOVERY items and
    cursor navigation should work correctly."""
    from textual.widgets import Input, OptionList

    from textual_code.commands import _read_workspace_files
    from textual_code.modals import _MAX_DISCOVERY, PathSearchModal

    # Create 200 files in cache (well above _MAX_DISCOVERY=50)
    large_files = sorted(Path(f"dir{i // 50}/file_{i:04d}.py") for i in range(200))
    _populate_cache(workspace, "files", large_files)

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, PathSearchModal)
        ol = modal.query_one("#path-search-results", OptionList)
        # Discovery should cap at _MAX_DISCOVERY
        assert ol.option_count == _MAX_DISCOVERY
        # Cursor navigation should work without lag
        await pilot.press("down")
        await pilot.pause()
        assert ol.highlighted is not None
        first = ol.highlighted
        # Navigate several items down
        for _ in range(5):
            await pilot.press("down")
        await pilot.pause()
        assert ol.highlighted == first + 5
        # Input should keep focus during navigation
        inp = modal.query_one("#path-search-input", Input)
        assert inp.has_focus
