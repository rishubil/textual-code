"""Tests for PathSearchModal — fzf-like path search with streaming support."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_app, wait_for_condition


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
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.wait_for_scheduled_animations()
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
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.wait_for_scheduled_animations()
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
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.wait_for_scheduled_animations()
        # Type "alpha" to search
        await pilot.press("a", "l", "p", "h", "a")
        await pilot.wait_for_scheduled_animations()
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
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            ),
            callback=lambda result: dismissed_with.append(result),
        )
        await pilot.wait_for_scheduled_animations()
        await pilot.press("escape")
        await pilot.wait_for_scheduled_animations()
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
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
                path_filter=lambda p: p.suffix != ".txt",
            )
        )
        await pilot.wait_for_scheduled_animations()
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
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_paths,
                cache_key="paths",
            )
        )
        await pilot.wait_for_scheduled_animations()
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
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.wait_for_scheduled_animations()
        ol = app.screen.query_one("#path-search-results", OptionList)
        names = [str(ol.get_option_at_index(i).prompt) for i in range(ol.option_count)]
        assert names == sorted(names)


# ── Cycle 2: App integration ─────────────────────────────────────────────────


async def test_action_opens_path_search_modal(
    workspace: Path, sample_files: list[Path]
):
    """action_open_file opens PathSearchModal."""
    from textual_code.modals import PathSearchModal

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.action_open_file()
        await pilot.wait_for_scheduled_animations()
        assert isinstance(app.screen, PathSearchModal)


async def test_file_search_opens_selected_file(
    workspace: Path, sample_files: list[Path]
):
    """Selecting a file in PathSearchModal opens it in the editor."""
    from textual.widgets import OptionList

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.action_open_file()
        await pilot.wait_for_scheduled_animations()
        # Type to search for "alpha"
        await pilot.press("a", "l", "p", "h", "a")
        # Wait for background fuzzy matching worker to complete
        ol = app.screen.query_one("#path-search-results", OptionList)
        await wait_for_condition(
            pilot, lambda: ol.option_count >= 1, msg="No search results found"
        )
        # Select the highlighted option
        await pilot.press("enter")
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Extra pause for file open async processing
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
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
            )
        )
        await pilot.wait_for_scheduled_animations()
        await pilot.press("a", "l", "p", "h", "a")
        # Wait for background scan + fuzzy matching worker to complete
        ol = app.screen.query_one("#path-search-results", OptionList)
        await wait_for_condition(
            pilot,
            lambda: ol.option_count >= 1,
            msg="No search results when cache is None",
        )


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
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.wait_for_scheduled_animations()
        modal = app.screen
        assert isinstance(modal, PathSearchModal)
        # Type to get results
        await pilot.press("a", "l", "p", "h", "a")
        # Wait for background fuzzy matching worker to complete
        ol = modal.query_one("#path-search-results", OptionList)
        await wait_for_condition(
            pilot, lambda: ol.option_count >= 1, msg="No search results found"
        )
        current_count = ol.option_count
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
        await pilot.wait_for_scheduled_animations()
        # First open — triggers scan
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        # Wait for background scan to populate cache
        await wait_for_condition(
            pilot,
            lambda: (workspace, "files") in PathSearchModal._cache,
            msg="Cache not populated after first open",
        )
        # Dismiss
        await pilot.press("escape")
        await pilot.wait_for_scheduled_animations()
        # Second open — should hit cache
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.wait_for_scheduled_animations()
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
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        # Wait for modal to mount
        await pilot.wait_for_scheduled_animations()
        # Wait for background scan worker to complete
        ol = app.screen.query_one("#path-search-results", OptionList)
        await wait_for_condition(
            pilot, lambda: ol.option_count > 0, msg="Scan did not populate results"
        )
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
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.wait_for_scheduled_animations()
        modal = app.screen
        assert isinstance(modal, PathSearchModal)
        ol = modal.query_one("#path-search-results", OptionList)
        # Discovery mode — should have items
        assert ol.option_count >= 2
        # Press down to highlight first item
        await pilot.press("down")
        await pilot.wait_for_scheduled_animations()
        assert ol.highlighted is not None
        initial_highlight = ol.highlighted
        # Press down again
        await pilot.press("down")
        await pilot.wait_for_scheduled_animations()
        assert ol.highlighted == initial_highlight + 1
        # Press up
        await pilot.press("up")
        await pilot.wait_for_scheduled_animations()
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
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.wait_for_scheduled_animations()
        modal = app.screen
        assert isinstance(modal, PathSearchModal)
        ol = modal.query_one("#path-search-results", OptionList)
        # Discovery should cap at _MAX_DISCOVERY
        assert ol.option_count == _MAX_DISCOVERY
        # Cursor navigation should work without lag
        await pilot.press("down")
        await pilot.wait_for_scheduled_animations()
        assert ol.highlighted is not None
        first = ol.highlighted
        # Navigate several items down
        for _ in range(5):
            await pilot.press("down")
        await pilot.wait_for_scheduled_animations()
        assert ol.highlighted == first + 5
        # Input should keep focus during navigation
        inp = modal.query_one("#path-search-input", Input)
        assert inp.has_focus


# ── Cycle 7: Gitignore toggle ─────────────────────────────────────────────────


async def test_gitignore_toggle_visible(workspace: Path, sample_files: list[Path]):
    """Checkbox visible when show_gitignore_toggle=True."""
    from textual.widgets import Checkbox

    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    _populate_cache(workspace, "files:gitignore=True", sample_files)
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files:gitignore=True",
                show_gitignore_toggle=True,
                unfiltered_scan_func=_read_workspace_files,
                unfiltered_cache_key="files:gitignore=False",
            )
        )
        await pilot.wait_for_scheduled_animations()
        modal = app.screen
        assert isinstance(modal, PathSearchModal)
        cb = modal.query_one("#path-search-gitignore", Checkbox)
        assert cb.value is True  # default ON


async def test_gitignore_toggle_hidden_by_default(
    workspace: Path, sample_files: list[Path]
):
    """No checkbox when show_gitignore_toggle is not set."""
    from textual.css.query import NoMatches
    from textual.widgets import Checkbox

    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    _populate_cache(workspace, "files", sample_files)
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.wait_for_scheduled_animations()
        modal = app.screen
        assert isinstance(modal, PathSearchModal)
        with pytest.raises(NoMatches):
            modal.query_one("#path-search-gitignore", Checkbox)


async def test_gitignore_toggle_triggers_rescan(workspace: Path):
    """Unchecking gitignore toggle should switch to unfiltered scan func."""
    from textual.widgets import Checkbox, OptionList

    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    # Filtered (gitignore ON): only 2 files
    filtered_files = sorted([Path("alpha.py"), Path("beta.py")])
    _populate_cache(workspace, "filtered", filtered_files)

    # Unfiltered (gitignore OFF): 4 files (includes gitignored ones)
    unfiltered_files = sorted(
        [
            Path("alpha.py"),
            Path("beta.py"),
            Path("build/out.js"),
            Path("node_modules/pkg.js"),
        ]
    )
    _populate_cache(workspace, "unfiltered", unfiltered_files)

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="filtered",
                show_gitignore_toggle=True,
                unfiltered_scan_func=_read_workspace_files,
                unfiltered_cache_key="unfiltered",
            )
        )
        await pilot.wait_for_scheduled_animations()
        modal = app.screen
        assert isinstance(modal, PathSearchModal)
        ol = modal.query_one("#path-search-results", OptionList)
        # Initially showing filtered results
        assert ol.option_count == 2

        # Uncheck gitignore toggle
        cb = modal.query_one("#path-search-gitignore", Checkbox)
        cb.value = False
        await pilot.wait_for_scheduled_animations()
        # Should now show unfiltered results
        ol = modal.query_one("#path-search-results", OptionList)
        assert ol.option_count == 4


async def test_action_open_file_has_gitignore_toggle(
    workspace: Path, sample_files: list[Path]
):
    """action_open_file opens PathSearchModal with gitignore toggle."""
    from textual.widgets import Checkbox

    from textual_code.modals import PathSearchModal

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.action_open_file()
        await pilot.wait_for_scheduled_animations()
        modal = app.screen
        assert isinstance(modal, PathSearchModal)
        cb = modal.query_one("#path-search-gitignore", Checkbox)
        assert cb.value is True


# ── Cycle 8: rapidfuzz large-list acceleration ──────────────────────────────


def test_adjust_score_for_path_filename_bonus():
    """Filename match gets a higher score than directory-only match."""
    from textual_code.modals import _adjust_score_for_path

    # Query "app" appears in filename "app.py"
    score_filename = _adjust_score_for_path(80.0, "src/app.py", "app")
    # Query "app" does NOT appear in filename "config.py"
    score_no_filename = _adjust_score_for_path(80.0, "src/application/config.py", "app")
    assert score_filename > score_no_filename


def test_adjust_score_for_path_short_path_bonus():
    """Shorter paths get higher scores than deeper paths."""
    from textual_code.modals import _adjust_score_for_path

    score_short = _adjust_score_for_path(80.0, "app.py", "x")
    score_deep = _adjust_score_for_path(80.0, "a/b/c/d/e/app.py", "x")
    assert score_short > score_deep


def test_adjust_score_for_path_depth_bonus():
    """Root-level files get a depth bonus over deeply nested files."""
    from textual_code.modals import _adjust_score_for_path

    score_root = _adjust_score_for_path(80.0, "file.py", "x")
    score_depth1 = _adjust_score_for_path(80.0, "src/file.py", "x")
    score_depth3 = _adjust_score_for_path(80.0, "a/b/c/file.py", "x")
    assert score_root > score_depth1
    assert score_depth1 > score_depth3


def test_adjust_score_for_path_backslash_separators():
    """Backslash separators produce the same scores as forward slashes."""
    from textual_code.modals import _adjust_score_for_path

    score_fwd = _adjust_score_for_path(80.0, "src/app.py", "app")
    score_bck = _adjust_score_for_path(80.0, "src\\app.py", "app")
    assert score_fwd == score_bck

    score_deep_fwd = _adjust_score_for_path(80.0, "a/b/c/file.py", "x")
    score_deep_bck = _adjust_score_for_path(80.0, "a\\b\\c\\file.py", "x")
    assert score_deep_fwd == score_deep_bck


async def test_rapidfuzz_used_for_large_file_list(workspace: Path):
    """With >5000 cached files, search should still return results quickly."""
    from textual.widgets import OptionList

    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    # Create 6000 synthetic paths (above _RAPIDFUZZ_THRESHOLD)
    large_files = sorted(Path(f"dir{i // 100}/file_{i:05d}.py") for i in range(6000))
    _populate_cache(workspace, "files", large_files)

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.wait_for_scheduled_animations()
        # Type to search
        await pilot.press("f", "i", "l", "e", "_", "0", "0", "5")
        # Wait for background fuzzy matching worker to complete
        ol = app.screen.query_one("#path-search-results", OptionList)
        await wait_for_condition(
            pilot,
            lambda: ol.option_count >= 1,
            msg="rapidfuzz path should return results",
        )
        # Top result should contain the query
        option = ol.get_option_at_index(0)
        assert "file_005" in str(option.prompt).lower()


async def test_rapidfuzz_prefers_filename_match(workspace: Path):
    """Filename matches should rank higher than directory-only matches."""
    from textual.widgets import OptionList

    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    # Build a large file list where one file has "target" in filename
    # and many others have it only in directory names
    paths: list[Path] = [Path("target.py")]
    for i in range(6000):
        paths.append(Path(f"target_dir/subdir{i // 100}/file_{i:05d}.py"))
    _populate_cache(workspace, "files", sorted(paths))

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.wait_for_scheduled_animations()
        await pilot.press("t", "a", "r", "g", "e", "t")
        # Wait for background fuzzy matching worker to complete
        ol = app.screen.query_one("#path-search-results", OptionList)
        await wait_for_condition(
            pilot, lambda: ol.option_count >= 1, msg="No search results for 'target'"
        )
        # "target.py" should be the top result (filename match)
        top_text = str(ol.get_option_at_index(0).prompt).lower()
        assert "target.py" in top_text, (
            f"Expected 'target.py' as top result, got: {top_text}"
        )


# ── Navigation: page_down / page_up ─────────────────────────────────────────


async def test_page_down_up_navigation(workspace: Path, sample_files: list[Path]):
    """page_down / page_up change highlighted index in the option list."""
    from textual.widgets import OptionList

    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    _populate_cache(workspace, "files", sample_files)
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            )
        )
        await pilot.wait_for_scheduled_animations()
        ol = app.screen.query_one("#path-search-results", OptionList)
        if ol.option_count > 0:
            await pilot.press("down")
            await pilot.wait_for_scheduled_animations()
            await pilot.press("pagedown")
            await pilot.wait_for_scheduled_animations()
            # pagedown should move or stay at end
            assert ol.highlighted is not None
            await pilot.press("pageup")
            await pilot.wait_for_scheduled_animations()
            assert ol.highlighted is not None


# ── Input submission: Enter selects first result ─────────────────────────────


async def test_input_submission_selects_first(
    workspace: Path, sample_files: list[Path]
):
    """Pressing Enter without navigation selects the first result."""
    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    _populate_cache(workspace, "files", sample_files)
    results = []
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            ),
            callback=results.append,
        )
        await pilot.wait_for_scheduled_animations()
        # Press Enter immediately to select first discovery item
        await pilot.press("enter")
        await pilot.wait_for_scheduled_animations()
        assert len(results) == 1
        assert results[0] is not None  # a Path was selected, not dismissed


# ── Gitignore toggle noop without unfiltered func ────────────────────────────


async def test_gitignore_toggle_noop_without_unfiltered_func(
    workspace: Path, sample_files: list[Path]
):
    """Toggling gitignore off with no unfiltered_scan_func is a no-op."""
    from textual.widgets import Checkbox

    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    _populate_cache(workspace, "files", sample_files)
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
                show_gitignore_toggle=True,
                unfiltered_scan_func=None,
            )
        )
        await pilot.wait_for_scheduled_animations()
        modal = app.screen
        assert isinstance(modal, PathSearchModal)
        cb = modal.query_one("#path-search-gitignore", Checkbox)
        original_func = modal._scan_func
        cb.value = False
        await pilot.wait_for_scheduled_animations()
        # scan_func unchanged because unfiltered_scan_func was None
        assert modal._scan_func is original_func


# ── Click background dismisses modal ─────────────────────────────────────────


async def test_click_background_dismisses(workspace: Path, sample_files: list[Path]):
    """Clicking the background overlay dismisses the modal with None."""
    from textual_code.commands import _read_workspace_files
    from textual_code.modals import PathSearchModal

    _populate_cache(workspace, "files", sample_files)
    results = []
    app = make_app(workspace, light=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.wait_for_scheduled_animations()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cache_key="files",
            ),
            callback=results.append,
        )
        await pilot.wait_for_scheduled_animations()
        # Click bottom area (background overlay, below the modal container)
        await pilot.click(offset=(60, 38))
        await pilot.wait_for_scheduled_animations()
        assert len(results) == 1
        assert results[0] is None
