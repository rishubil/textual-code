"""Tests for PathSearchModal — fzf-like path search with streaming support."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_app


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

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cached_paths=sample_files,
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
    """When cached_paths is provided, files are shown immediately."""
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
                cached_paths=sample_files,
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

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cached_paths=sample_files,
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

    dismissed_with: list[Path | None] = []

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cached_paths=sample_files,
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
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cached_paths=sample_files,
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
    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_paths,
                cached_paths=abs_paths,
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

    app = make_app(workspace, light=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(
            PathSearchModal(
                workspace,
                scan_func=_read_workspace_files,
                cached_paths=cached,
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
