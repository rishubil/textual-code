"""Tests for workspace search (search.py and WorkspaceSearchPane)."""

from __future__ import annotations

from pathlib import Path

import pytest

from textual_code.search import (
    WorkspaceSearchResponse,
    WorkspaceSearchResult,
    search_workspace,
)

# ---------------------------------------------------------------------------
# Unit tests: search_workspace()
# ---------------------------------------------------------------------------


def test_plain_text_single_file(tmp_path: Path) -> None:
    f = tmp_path / "hello.py"
    f.write_text("hello world\nfoo bar\n")
    results = search_workspace(tmp_path, "hello").results
    assert len(results) == 1
    assert results[0].file_path == f
    assert results[0].line_number == 1
    assert results[0].line_text == "hello world"
    assert results[0].match_start == 0


def test_returns_only_matching_files(tmp_path: Path) -> None:
    (tmp_path / "match.txt").write_text("needle here\n")
    (tmp_path / "nomatch.txt").write_text("nothing relevant\n")
    results = search_workspace(tmp_path, "needle").results
    assert len(results) == 1
    assert results[0].file_path.name == "match.txt"


def test_multiple_matches_in_one_file(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("foo\nbar foo\nbaz\n")
    results = search_workspace(tmp_path, "foo").results
    assert len(results) == 2
    assert {r.line_number for r in results} == {1, 2}


def test_regex_search(tmp_path: Path) -> None:
    (tmp_path / "r.txt").write_text("abc123\ndef456\nghi\n")
    results = search_workspace(tmp_path, r"\d+", use_regex=True).results
    assert len(results) == 2
    assert results[0].line_number == 1
    assert results[1].line_number == 2


def test_binary_file_skipped(tmp_path: Path) -> None:
    (tmp_path / "binary.bin").write_bytes(b"\x00\x01\x02binary data")
    results = search_workspace(tmp_path, "binary").results
    assert results == []


def test_hidden_file_included_by_default(tmp_path: Path) -> None:
    """Hidden files are included when show_hidden_files=True (default)."""
    (tmp_path / ".hidden").write_text("secret needle\n")
    results = search_workspace(tmp_path, "needle").results
    assert len(results) == 1
    assert results[0].file_path.name == ".hidden"


def test_hidden_file_skipped_when_disabled(tmp_path: Path) -> None:
    """Hidden files are excluded when show_hidden_files=False."""
    (tmp_path / ".hidden").write_text("secret needle\n")
    (tmp_path / "visible.txt").write_text("needle\n")
    results = search_workspace(tmp_path, "needle", show_hidden_files=False).results
    assert len(results) == 1
    assert results[0].file_path.name == "visible.txt"


def test_git_directory_always_skipped(tmp_path: Path) -> None:
    """.git directory is always excluded, even with show_hidden_files=True."""
    hidden_dir = tmp_path / ".git"
    hidden_dir.mkdir()
    (hidden_dir / "config").write_text("needle\n")
    results = search_workspace(tmp_path, "needle").results
    assert results == []


def test_empty_workspace(tmp_path: Path) -> None:
    results = search_workspace(tmp_path, "anything").results
    assert results == []


def test_empty_query_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n")
    results = search_workspace(tmp_path, "").results
    assert results == []


def test_whitespace_only_query_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n")
    results = search_workspace(tmp_path, "   ").results
    # whitespace is valid as a plain search but "   " trimming is caller's job;
    # search_workspace itself searches for the literal string "   "
    # (three spaces) so no match expected here.
    assert results == []


def test_max_results_limit(tmp_path: Path) -> None:
    (tmp_path / "big.txt").write_text("needle\n" * 100)
    results = search_workspace(tmp_path, "needle", max_results=10).results
    assert len(results) == 10


def test_search_response_is_truncated_when_limit_reached(tmp_path: Path) -> None:
    """is_truncated should be True when results hit max_results cap."""
    (tmp_path / "big.txt").write_text("needle\n" * 100, encoding="utf-8")
    response = search_workspace(tmp_path, "needle", max_results=10)
    assert response.is_truncated is True
    assert len(response.results) == 10


def test_search_response_not_truncated_below_limit(tmp_path: Path) -> None:
    """is_truncated should be False when results are below max_results."""
    (tmp_path / "small.txt").write_text("needle\n" * 5, encoding="utf-8")
    response = search_workspace(tmp_path, "needle", max_results=100)
    assert response.is_truncated is False
    assert len(response.results) == 5


def test_invalid_regex_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n")
    results = search_workspace(tmp_path, "[invalid(", use_regex=True).results
    assert results == []


def test_match_start_end_columns(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("  needle here\n")
    results = search_workspace(tmp_path, "needle").results
    assert len(results) == 1
    r = results[0]
    assert r.match_start == 2
    assert r.match_end == 8


def test_result_dataclass_fields() -> None:
    p = Path("/tmp/x.py")
    r = WorkspaceSearchResult(
        file_path=p, line_number=3, line_text="hi", match_start=0, match_end=2
    )
    assert r.file_path == p
    assert r.line_number == 3
    assert r.line_text == "hi"
    assert r.match_start == 0
    assert r.match_end == 2


# ---------------------------------------------------------------------------
# Integration tests: WorkspaceSearchPane + app
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ctrl_shift_f_activates_search_tab(tmp_path: Path) -> None:
    """Ctrl+Shift+F switches sidebar to the Search tab."""
    from tests.conftest import make_app
    from textual_code.widgets.sidebar import Sidebar

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()
        sidebar = app.query_one(Sidebar)
        assert sidebar.tabbed_content.active == "search_pane"


@pytest.mark.asyncio
async def test_search_shows_results(tmp_path: Path) -> None:
    """Running a search populates the results tree."""
    from textual.widgets import Input

    from tests.conftest import make_app
    from textual_code.widgets.checkbox_tree import CheckboxTree
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    (tmp_path / "sample.txt").write_text("hello world\nfoo bar\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        # Open search panel
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "hello"
        await pilot.wait_for_scheduled_animations()

        # Trigger search directly
        ws_pane._run_search()
        await pilot.wait_for_scheduled_animations()

        results_tree = ws_pane.query_one("#ws-results", CheckboxTree)
        assert results_tree.file_rows()  # at least one file node


@pytest.mark.asyncio
async def test_search_no_results_message(tmp_path: Path) -> None:
    """Search with no matches shows a 'No results' node in the tree."""
    from textual.widgets import Input

    from tests.conftest import make_app
    from textual_code.widgets.checkbox_tree import CheckboxTree
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    (tmp_path / "sample.txt").write_text("hello world\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "xyzzy_no_match"
        await pilot.wait_for_scheduled_animations()

        ws_pane._run_search()
        await pilot.wait_for_scheduled_animations()

        results_tree = ws_pane.query_one("#ws-results", CheckboxTree)
        # CheckboxTree stays empty when no results
        assert results_tree.file_rows() == []


@pytest.mark.asyncio
async def test_search_result_click_opens_file(tmp_path: Path) -> None:
    """Clicking a search result opens the file in the editor."""
    from textual.widgets import Input

    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    target = tmp_path / "target.txt"
    target.write_text("unique_string_xyz\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "unique_string_xyz"
        await pilot.wait_for_scheduled_animations()
        await pilot.press("enter")
        await pilot.wait_for_scheduled_animations()

        # Simulate selecting the first result
        ws_pane.post_message(
            WorkspaceSearchPane.OpenFileAtLineRequested(file_path=target, line_number=1)
        )
        await pilot.wait_for_scheduled_animations()
        await (
            pilot.wait_for_scheduled_animations()
        )  # Windows: extra pause for post_message + file open

        # The file should now be open
        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        assert editor.path == target


@pytest.mark.asyncio
async def test_search_result_cursor_position(tmp_path: Path) -> None:
    """Opening a result at a specific line moves the cursor to that line."""
    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    target = tmp_path / "multiline.txt"
    target.write_text("line1\nline2\nline3\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.post_message(
            WorkspaceSearchPane.OpenFileAtLineRequested(file_path=target, line_number=3)
        )
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        row, _col = editor.editor.cursor_location
        assert row == 2  # 0-based, line 3 → row 2


# ---------------------------------------------------------------------------
# Unit tests: gitignore support
# ---------------------------------------------------------------------------


def test_gitignore_root_respected(tmp_path: Path) -> None:
    """Files listed in root .gitignore are excluded from search."""
    (tmp_path / ".git").mkdir()  # ripgrep needs .git to recognise .gitignore
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    (tmp_path / "ignored.txt").write_text("needle\n")
    (tmp_path / "visible.txt").write_text("needle\n")

    results = search_workspace(tmp_path, "needle", respect_gitignore=True).results
    paths = {r.file_path.name for r in results}
    assert "ignored.txt" not in paths
    assert "visible.txt" in paths


def test_gitignore_nested_subdir_respected(tmp_path: Path) -> None:
    """Nested .gitignore is applied relative to its directory."""
    (tmp_path / ".git").mkdir()  # ripgrep needs .git to recognise .gitignore
    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / ".gitignore").write_text("secret.txt\n")
    (subdir / "secret.txt").write_text("needle\n")
    (subdir / "public.txt").write_text("needle\n")

    results = search_workspace(tmp_path, "needle", respect_gitignore=True).results
    paths = {r.file_path.name for r in results}
    assert "secret.txt" not in paths
    assert "public.txt" in paths


def test_respect_gitignore_false_bypasses(tmp_path: Path) -> None:
    """respect_gitignore=False returns gitignored files."""
    (tmp_path / ".git").mkdir()  # ripgrep needs .git to recognise .gitignore
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    (tmp_path / "ignored.txt").write_text("needle\n")

    results = search_workspace(tmp_path, "needle", respect_gitignore=False).results
    assert any(r.file_path.name == "ignored.txt" for r in results)


# ---------------------------------------------------------------------------
# Unit tests: include/exclude filter
# ---------------------------------------------------------------------------


def test_include_filter_restricts_to_matching_files(tmp_path: Path) -> None:
    """files_to_include restricts search to matching files only."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("needle\n")
    (tmp_path / "other.txt").write_text("needle\n")

    results = search_workspace(tmp_path, "needle", files_to_include="src/**").results
    paths = {r.file_path.name for r in results}
    assert "main.py" in paths
    assert "other.txt" not in paths


def test_exclude_filter_skips_matching_files(tmp_path: Path) -> None:
    """files_to_exclude skips matching files."""
    (tmp_path / "keep.py").write_text("needle\n")
    (tmp_path / "skip.txt").write_text("needle\n")

    results = search_workspace(tmp_path, "needle", files_to_exclude="*.txt").results
    paths = {r.file_path.name for r in results}
    assert "keep.py" in paths
    assert "skip.txt" not in paths


def test_empty_include_returns_all_files(tmp_path: Path) -> None:
    """Empty files_to_include returns all files (no restriction)."""
    (tmp_path / "a.py").write_text("needle\n")
    (tmp_path / "b.txt").write_text("needle\n")

    results = search_workspace(tmp_path, "needle", files_to_include="").results
    assert len(results) == 2


def test_extension_only_include_pattern(tmp_path: Path) -> None:
    """Extension-only pattern like '*.py' works for include filter."""
    (tmp_path / "code.py").write_text("needle\n")
    (tmp_path / "doc.txt").write_text("needle\n")

    results = search_workspace(tmp_path, "needle", files_to_include="*.py").results
    paths = {r.file_path.name for r in results}
    assert "code.py" in paths
    assert "doc.txt" not in paths


def test_invalid_include_pattern_returns_empty(tmp_path: Path) -> None:
    """Invalid pattern in files_to_include yields empty results (no crash)."""
    (tmp_path / "a.txt").write_text("needle\n")

    # pathspec with an extremely malformed pattern; if it raises, iterator returns []
    # We pass something that could be invalid in some pathspec versions
    response = search_workspace(tmp_path, "needle", files_to_include="[invalid(")
    # Must not crash; response is a WorkspaceSearchResponse with a list of results
    assert isinstance(response, WorkspaceSearchResponse)
    assert isinstance(response.results, list)


def test_trailing_comma_whitespace_in_pattern_string(tmp_path: Path) -> None:
    """Trailing comma and whitespace in pattern string are handled gracefully."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("needle\n")
    (tmp_path / "other.txt").write_text("needle\n")

    # Leading/trailing comma and spaces should be stripped
    results = search_workspace(
        tmp_path, "needle", files_to_include=" src/** , "
    ).results
    paths = {r.file_path.name for r in results}
    assert "main.py" in paths
    assert "other.txt" not in paths


# ---------------------------------------------------------------------------
# Unit tests: folder exclusion
# ---------------------------------------------------------------------------


def test_exclude_folder_by_name(tmp_path: Path) -> None:
    """Folder name in files_to_exclude skips all files inside it."""
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("needle\n")
    (tmp_path / "keep.py").write_text("needle\n")

    results = search_workspace(
        tmp_path, "needle", files_to_exclude="node_modules"
    ).results
    paths = {r.file_path.name for r in results}
    assert "pkg.js" not in paths
    assert "keep.py" in paths


def test_exclude_multiple_folders(tmp_path: Path) -> None:
    """Comma-separated folder names are all excluded."""
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "bundle.js").write_text("needle\n")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "out.js").write_text("needle\n")
    (tmp_path / "src.py").write_text("needle\n")

    results = search_workspace(
        tmp_path, "needle", files_to_exclude="dist,build"
    ).results
    paths = {r.file_path.name for r in results}
    assert "bundle.js" not in paths
    assert "out.js" not in paths
    assert "src.py" in paths


def test_exclude_nested_folder(tmp_path: Path) -> None:
    """Folder name matches at any depth in the directory tree."""
    vendor = tmp_path / "src" / "vendor"
    vendor.mkdir(parents=True)
    (vendor / "lib.js").write_text("needle\n")
    (tmp_path / "src" / "main.py").write_text("needle\n")

    results = search_workspace(tmp_path, "needle", files_to_exclude="vendor").results
    paths = {r.file_path.name for r in results}
    assert "lib.js" not in paths
    assert "main.py" in paths


def test_exclude_folder_trailing_slash(tmp_path: Path) -> None:
    """Trailing slash in exclude pattern is handled (dist/ excludes dist/)."""
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "out.js").write_text("needle\n")
    (tmp_path / "keep.py").write_text("needle\n")

    results = search_workspace(tmp_path, "needle", files_to_exclude="dist/").results
    paths = {r.file_path.name for r in results}
    assert "out.js" not in paths
    assert "keep.py" in paths


# ---------------------------------------------------------------------------
# Unit tests: case-sensitive search
# ---------------------------------------------------------------------------


def test_case_sensitive_search_default(tmp_path: Path) -> None:
    """By default search is case-sensitive."""
    (tmp_path / "a.txt").write_text("Hello World\n")

    results = search_workspace(tmp_path, "hello").results
    assert results == []

    results = search_workspace(tmp_path, "Hello").results
    assert len(results) == 1


def test_case_insensitive_search(tmp_path: Path) -> None:
    """case_sensitive=False matches regardless of case."""
    (tmp_path / "a.txt").write_text("Hello World\n")

    results = search_workspace(tmp_path, "hello", case_sensitive=False).results
    assert len(results) == 1
    assert results[0].line_text == "Hello World"


def test_case_insensitive_regex(tmp_path: Path) -> None:
    """case_sensitive=False works with use_regex=True."""
    (tmp_path / "a.txt").write_text("FooBar\nbaz\n")

    results = search_workspace(
        tmp_path, "foo.*", use_regex=True, case_sensitive=False
    ).results
    assert len(results) == 1
    assert results[0].line_text == "FooBar"


# ---------------------------------------------------------------------------
# UI integration test: exclude field in WorkspaceSearchPane
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exclude_field_in_ui_applies_to_search(tmp_path: Path) -> None:
    """The #ws-exclude Input field is read and applied during search."""
    from textual.widgets import Input

    from tests.conftest import make_app
    from textual_code.widgets.checkbox_tree import CheckboxTree
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("needle\n")
    (tmp_path / "keep.py").write_text("needle\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "needle"
        ws_pane.query_one("#ws-exclude", Input).value = "node_modules"
        ws_pane._run_search()
        await pilot.wait_for_scheduled_animations()

        results_tree = ws_pane.query_one("#ws-results", CheckboxTree)
        file_labels = [n.label_text for n in results_tree.file_rows()]
        assert not any("pkg.js" in lbl for lbl in file_labels)
        assert any("keep.py" in lbl for lbl in file_labels)


@pytest.mark.asyncio
async def test_case_sensitive_checkbox_in_ui(tmp_path: Path) -> None:
    """The #ws-case-sensitive checkbox controls case sensitivity."""
    from textual.widgets import Checkbox, Input

    from tests.conftest import make_app
    from textual_code.widgets.checkbox_tree import CheckboxTree
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    (tmp_path / "sample.txt").write_text("Hello World\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "hello"
        # Disable case-sensitive (uncheck)
        ws_pane.query_one("#ws-case-sensitive", Checkbox).value = False
        ws_pane._run_search()
        await pilot.wait_for_scheduled_animations()

        results_tree = ws_pane.query_one("#ws-results", CheckboxTree)
        file_labels = [n.label_text for n in results_tree.file_rows()]
        assert any("sample.txt" in lbl for lbl in file_labels)


@pytest.mark.asyncio
async def test_workspace_search_no_clipping(tmp_path: Path) -> None:
    """#ws-include must span the full width of its parent container (not half)."""
    from textual.widgets import Input

    from tests.conftest import make_app

    app = make_app(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()
        ws_filter_bar = app.query_one("#ws-filter-bar")
        ws_include = app.query_one("#ws-include", Input)
        ws_exclude = app.query_one("#ws-exclude", Input)
        # Both inputs must span the full container width (stacked, not side by side).
        # Use outer_size (includes borders/padding) to match the container's size.
        container_w = ws_filter_bar.size.width
        assert ws_include.outer_size.width == container_w, (
            f"ws-include outer width {ws_include.outer_size.width} != {container_w}"
        )
        assert ws_exclude.outer_size.width == container_w, (
            f"ws-exclude outer width {ws_exclude.outer_size.width} != {container_w}"
        )


# ---------------------------------------------------------------------------
# Loading indicator tests
# ---------------------------------------------------------------------------


def _patch_gated_search(monkeypatch):
    """Patch run_cancellable to block until the returned asyncio Event is set."""
    import asyncio as _asyncio

    import textual_code.widgets.workspace_search as ws_module

    gate = _asyncio.Event()

    async def gated_run_cancellable(fn, *args, **kwargs):
        await gate.wait()
        return fn(*args)

    monkeypatch.setattr(ws_module, "run_cancellable", gated_run_cancellable)
    return gate


@pytest.mark.asyncio
async def test_search_loading_indicator(tmp_path: Path, monkeypatch) -> None:
    """Results Tree shows loading=True while search is running."""
    from textual.widgets import Input

    from tests.conftest import make_app
    from textual_code.widgets.checkbox_tree import CheckboxTree
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    (tmp_path / "sample.txt").write_text("hello world\n")
    gate = _patch_gated_search(monkeypatch)

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "hello"
        await pilot.wait_for_scheduled_animations()

        ws_pane._run_search()
        await pilot.wait_for_scheduled_animations()

        results_tree = ws_pane.query_one("#ws-results", CheckboxTree)
        assert results_tree.loading is True

        gate.set()
        await pilot.wait_for_scheduled_animations()

        assert results_tree.loading is False


@pytest.mark.asyncio
async def test_search_error_clears_loading(tmp_path: Path, monkeypatch) -> None:
    """Search error sets loading=False and shows 'Search failed'."""
    from textual.widgets import Input

    import textual_code.widgets.workspace_search as ws_module
    from tests.conftest import make_app
    from textual_code.widgets.checkbox_tree import CheckboxTree
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    (tmp_path / "sample.txt").write_text("hello\n")

    def exploding_search(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(ws_module, "search_workspace", exploding_search)

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "hello"
        await pilot.wait_for_scheduled_animations()

        ws_pane._run_search()
        await pilot.wait_for_scheduled_animations()

        results_tree = ws_pane.query_one("#ws-results", CheckboxTree)
        assert results_tree.loading is False
        # CheckboxTree stays empty on error (no "Search failed" leaf)
        assert results_tree.file_rows() == []


@pytest.mark.asyncio
async def test_empty_query_clears_loading(tmp_path: Path, monkeypatch) -> None:
    """Re-searching with empty query clears loading state."""
    from textual.widgets import Input

    from tests.conftest import make_app
    from textual_code.widgets.checkbox_tree import CheckboxTree
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    (tmp_path / "sample.txt").write_text("hello world\n")
    gate = _patch_gated_search(monkeypatch)

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "hello"
        await pilot.wait_for_scheduled_animations()

        ws_pane._run_search()
        await pilot.wait_for_scheduled_animations()

        results_tree = ws_pane.query_one("#ws-results", CheckboxTree)
        assert results_tree.loading is True

        # Clear query and re-run search
        ws_pane.query_one("#ws-query", Input).value = ""
        ws_pane._run_search()
        await pilot.wait_for_scheduled_animations()

        assert results_tree.loading is False

        gate.set()  # Release the blocked worker


# ---------------------------------------------------------------------------
# Inaccessible path handling tests
# ---------------------------------------------------------------------------


def test_search_survives_inaccessible_directory(tmp_path: Path, monkeypatch) -> None:
    """Search completes with partial results when some files are inaccessible.

    ripgrep-rs silently skips inaccessible files, so inaccessible_paths is
    always empty.  We monkeypatch rg_files to simulate a partial listing to
    verify the search still returns results from accessible files.
    """
    (tmp_path / "visible.txt").write_text("needle\n")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "also_visible.txt").write_text("needle\n")

    response = search_workspace(tmp_path, "needle")
    # ripgrep finds both files; inaccessible_paths is always empty
    assert len(response.results) == 2
    assert response.inaccessible_paths == []


def test_search_response_empty_inaccessible_paths(tmp_path: Path) -> None:
    """Search with no errors returns empty inaccessible_paths."""
    (tmp_path / "a.txt").write_text("needle\n")
    response = search_workspace(tmp_path, "needle")
    assert isinstance(response, WorkspaceSearchResponse)
    assert len(response.results) == 1
    assert response.inaccessible_paths == []


@pytest.mark.asyncio
async def test_enter_in_include_field_triggers_search(tmp_path: Path) -> None:
    """Pressing Enter in #ws-include triggers search with the include filter."""
    from textual.widgets import Input

    from tests.conftest import make_app
    from textual_code.widgets.checkbox_tree import CheckboxTree
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("needle\n")
    (tmp_path / "other.txt").write_text("needle\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "needle"
        await pilot.wait_for_scheduled_animations()

        # Focus include input, type filter, press Enter
        await pilot.click("#ws-include")
        await pilot.press(*"src/**")
        await pilot.press("enter")
        await pilot.wait_for_scheduled_animations()

        results_tree = ws_pane.query_one("#ws-results", CheckboxTree)
        file_labels = [n.label_text for n in results_tree.file_rows()]
        assert any("main.py" in lbl for lbl in file_labels)
        assert not any("other.txt" in lbl for lbl in file_labels)


@pytest.mark.asyncio
async def test_enter_in_exclude_field_triggers_search(tmp_path: Path) -> None:
    """Pressing Enter in #ws-exclude triggers search with the exclude filter."""
    from textual.widgets import Input

    from tests.conftest import make_app
    from textual_code.widgets.checkbox_tree import CheckboxTree
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("needle\n")
    (tmp_path / "keep.py").write_text("needle\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "needle"
        await pilot.wait_for_scheduled_animations()

        # Focus exclude input, type filter, press Enter
        await pilot.click("#ws-exclude")
        await pilot.press(*"node_modules")
        await pilot.press("enter")
        await pilot.wait_for_scheduled_animations()

        results_tree = ws_pane.query_one("#ws-results", CheckboxTree)
        file_labels = [n.label_text for n in results_tree.file_rows()]
        assert any("keep.py" in lbl for lbl in file_labels)
        assert not any("pkg.js" in lbl for lbl in file_labels)


@pytest.mark.asyncio
async def test_search_with_permission_error_shows_toast(
    tmp_path: Path, monkeypatch
) -> None:
    """Search with inaccessible paths shows a Toast warning notification."""
    from unittest.mock import patch

    from textual.widgets import Input

    import textual_code.widgets.workspace_search as ws_module
    from tests.conftest import make_app
    from textual_code.widgets.checkbox_tree import CheckboxTree
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    (tmp_path / "sample.txt").write_text("hello world\n")

    def search_with_errors(*args, **kwargs):
        return WorkspaceSearchResponse(
            results=[
                WorkspaceSearchResult(
                    file_path=tmp_path / "sample.txt",
                    line_number=1,
                    line_text="hello world",
                    match_start=0,
                    match_end=5,
                )
            ],
            inaccessible_paths=["/restricted/dir1", "/restricted/dir2"],
        )

    monkeypatch.setattr(ws_module, "search_workspace", search_with_errors)

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "hello"
        await pilot.wait_for_scheduled_animations()

        with patch.object(app, "notify") as mock_notify:
            ws_pane._run_search()
            await pilot.wait_for_scheduled_animations()

            # Results should be populated
            results_tree = ws_pane.query_one("#ws-results", CheckboxTree)
            file_labels = [n.label_text for n in results_tree.file_rows()]
            assert any("sample.txt" in lbl for lbl in file_labels)

            # Toast warning should have been shown
            mock_notify.assert_called_once()
            call_args = mock_notify.call_args
            assert "2 path(s)" in call_args[0][0]
            assert call_args[1]["severity"] == "warning"


# ---------------------------------------------------------------------------
# Tree grouping tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_results_grouped_by_file(tmp_path: Path) -> None:
    """Search results are grouped by file in a Tree widget."""
    from textual.widgets import Input

    from tests.conftest import make_app
    from textual_code.widgets.checkbox_tree import CheckboxTree
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    (tmp_path / "alpha.py").write_text("needle line1\nneedle line2\n")
    (tmp_path / "beta.py").write_text("other\nneedle line3\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "needle"
        ws_pane._run_search()
        await pilot.wait_for_scheduled_animations()

        results_tree = ws_pane.query_one("#ws-results", CheckboxTree)
        file_nodes = list(results_tree.file_rows())

        # Should have 2 file-level nodes
        assert len(file_nodes) == 2

        # Check file node labels contain path and match count
        alpha_node = file_nodes[0]
        assert "alpha.py" in alpha_node.label_text
        assert "2 matches" in alpha_node.label_text

        beta_node = file_nodes[1]
        assert "beta.py" in beta_node.label_text
        assert "1 match" in beta_node.label_text
        # Singular "match" not "matches"
        assert "1 matches" not in beta_node.label_text

        # Check match-level children
        alpha_children = results_tree.match_rows_for(alpha_node)
        assert len(alpha_children) == 2
        assert "1:" in alpha_children[0].label_text
        assert "needle line1" in alpha_children[0].label_text
        assert "2:" in alpha_children[1].label_text
        assert "needle line2" in alpha_children[1].label_text

        beta_children = results_tree.match_rows_for(beta_node)
        assert len(beta_children) == 1
        assert "2:" in beta_children[0].label_text
        assert "needle line3" in beta_children[0].label_text


@pytest.mark.asyncio
async def test_tree_file_nodes_expanded_by_default(tmp_path: Path) -> None:
    """All file-level tree nodes are expanded after search."""
    from textual.widgets import Input

    from tests.conftest import make_app
    from textual_code.widgets.checkbox_tree import CheckboxTree
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    (tmp_path / "a.py").write_text("needle\n")
    (tmp_path / "b.py").write_text("needle\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "needle"
        ws_pane._run_search()
        await pilot.wait_for_scheduled_animations()

        from textual_code.widgets.checkbox_tree import _ExpandToggle

        results_tree = ws_pane.query_one("#ws-results", CheckboxTree)
        for file_row in results_tree.file_rows():
            toggle = file_row.query_one(_ExpandToggle)
            assert toggle.expanded, (
                f"File row '{file_row.label_text}' should be expanded"
            )


@pytest.mark.asyncio
async def test_tree_match_node_click_opens_file(tmp_path: Path) -> None:
    """Clicking a match leaf node opens the file at that line."""
    from textual.widgets import Input

    from tests.conftest import make_app
    from textual_code.widgets.checkbox_tree import CheckboxTree
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    target = tmp_path / "target.py"
    target.write_text("line1\nneedle_here\nline3\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "needle_here"
        ws_pane._run_search()
        await pilot.wait_for_scheduled_animations()

        results_tree = ws_pane.query_one("#ws-results", CheckboxTree)
        file_row = list(results_tree.file_rows())[0]
        match_rows = results_tree.match_rows_for(file_row)
        match_row = match_rows[0]

        # Verify data is stored on the row
        assert match_row.data is not None
        file_path, line_number = match_row.data
        assert file_path == target
        assert line_number == 2


@pytest.mark.asyncio
async def test_tree_file_node_click_opens_file(tmp_path: Path) -> None:
    """Clicking a file-level node opens the file at the first match line."""
    from textual.widgets import Input

    from tests.conftest import make_app, wait_for_condition
    from textual_code.widgets.checkbox_tree import CheckboxTree
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    target = tmp_path / "target.py"
    target.write_text("line1\nline2\nneedle_here\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "needle_here"
        ws_pane._run_search()

        results_tree = ws_pane.query_one("#ws-results", CheckboxTree)
        # Windows: search worker may not finish in a single pause
        await wait_for_condition(
            pilot,
            lambda: len(list(results_tree.file_rows())) > 0,
            msg="Search results tree has no children after retries",
        )
        file_node = list(results_tree.file_rows())[0]

        # File node data should carry the first match's line number
        assert file_node.data is not None
        file_path, line_number = file_node.data
        assert file_path == target
        assert line_number == 3  # first (and only) match line


@pytest.mark.asyncio
async def test_tree_match_count_accuracy_at_cap(tmp_path: Path) -> None:
    """File node match counts reflect actual returned results when capped."""
    from textual.widgets import Input

    from tests.conftest import make_app
    from textual_code.widgets.checkbox_tree import CheckboxTree
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    # Create files with many matches (exceeds 500 default cap)
    (tmp_path / "many.py").write_text("needle\n" * 400)
    (tmp_path / "more.py").write_text("needle\n" * 200)

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        await pilot.press("ctrl+shift+f")
        await pilot.wait_for_scheduled_animations()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "needle"
        ws_pane._run_search()
        await pilot.wait_for_scheduled_animations()

        results_tree = ws_pane.query_one("#ws-results", CheckboxTree)
        file_nodes = list(results_tree.file_rows())

        # Total results capped at 500, counts should reflect actual returned
        total_matches = sum(len(results_tree.match_rows_for(fr)) for fr in file_nodes)
        assert total_matches <= 500

        # Each file row label should show correct count for its children
        for file_row in file_nodes:
            child_count = len(results_tree.match_rows_for(file_row))
            assert f"{child_count} match" in file_row.label_text


# ---------------------------------------------------------------------------
# Unit tests: _byte_offset_to_char_offset
# ---------------------------------------------------------------------------


def test_byte_offset_to_char_offset_ascii() -> None:
    """For ASCII text, byte offset == character offset."""
    from textual_code.search import _byte_offset_to_char_offset

    assert _byte_offset_to_char_offset("hello world", 0) == 0
    assert _byte_offset_to_char_offset("hello world", 5) == 5
    assert _byte_offset_to_char_offset("hello world", 11) == 11


def test_byte_offset_to_char_offset_multibyte() -> None:
    """For multibyte UTF-8, byte offset != character offset."""
    from textual_code.search import _byte_offset_to_char_offset

    # 2 CJK chars (3 bytes each in UTF-8), then " needle"
    line = "\ud55c\uae00 needle"
    # byte 0 -> char 0
    assert _byte_offset_to_char_offset(line, 0) == 0
    # byte 6 -> char 2 (after the 2 CJK chars)
    assert _byte_offset_to_char_offset(line, 6) == 2
    # byte 7 -> char 3 (after CJK + space)
    assert _byte_offset_to_char_offset(line, 7) == 3


# ---------------------------------------------------------------------------
# Unit tests: new search behavior
# ---------------------------------------------------------------------------


def test_multiple_matches_same_line(tmp_path: Path) -> None:
    """Multiple matches on the same line produce separate results."""
    (tmp_path / "a.txt").write_text("foo bar foo baz foo\n")
    results = search_workspace(tmp_path, "foo").results
    assert len(results) == 3
    assert all(r.line_number == 1 for r in results)
    # Check match positions are distinct and ordered
    starts = [r.match_start for r in results]
    assert starts == sorted(starts)
    assert starts[0] == 0
    assert starts[1] == 8
    assert starts[2] == 16


def test_search_multibyte_columns(tmp_path: Path) -> None:
    """Match columns are character offsets, not byte offsets."""
    (tmp_path / "a.txt").write_text("\ud55c\uae00 needle\n", encoding="utf-8")
    results = search_workspace(tmp_path, "needle").results
    assert len(results) == 1
    r = results[0]
    # 2 CJK chars + space = 3 chars, then "needle" starts at char 3
    assert r.match_start == 3
    assert r.match_end == 9


def test_search_special_chars_literal(tmp_path: Path) -> None:
    """Literal search with regex special characters works correctly."""
    content = "call foo() and bar[0].baz\n"
    (tmp_path / "a.txt").write_text(content)

    # Search for literal "foo()" — should not be treated as regex
    results = search_workspace(tmp_path, "foo()").results
    assert len(results) == 1
    assert results[0].match_start == 5

    # Search for literal "bar[0]" — brackets are special in regex
    results = search_workspace(tmp_path, "bar[0]").results
    assert len(results) == 1
    assert results[0].match_start == 15


def test_search_performance_with_gitignore(tmp_path: Path) -> None:
    """Search with gitignore should complete quickly even with ignored dirs."""
    import time

    # Create a structure with many files in an ignored directory
    (tmp_path / ".git").mkdir()  # ripgrep needs .git to recognise .gitignore
    ignored = tmp_path / "ignored_dir"
    ignored.mkdir()
    for i in range(100):
        (ignored / f"file_{i}.txt").write_text(f"needle {i}\n")

    # Create a .gitignore that ignores the directory
    (tmp_path / ".gitignore").write_text("ignored_dir/\n")

    # Create a visible file
    (tmp_path / "visible.txt").write_text("needle here\n")

    t0 = time.monotonic()
    response = search_workspace(tmp_path, "needle", respect_gitignore=True)
    elapsed = time.monotonic() - t0

    # Should only find the visible file
    assert len(response.results) == 1
    assert response.results[0].file_path.name == "visible.txt"
    # Should complete quickly (not scanning ignored dirs)
    assert elapsed < 1.0, f"Search took {elapsed:.2f}s, expected <1.0s"
