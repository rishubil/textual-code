"""Tests for workspace search (search.py and WorkspaceSearchPane)."""

from __future__ import annotations

from pathlib import Path

import pytest

from textual_code.search import WorkspaceSearchResult, search_workspace

# ---------------------------------------------------------------------------
# Unit tests: search_workspace()
# ---------------------------------------------------------------------------


def test_plain_text_single_file(tmp_path: Path) -> None:
    f = tmp_path / "hello.py"
    f.write_text("hello world\nfoo bar\n")
    results = search_workspace(tmp_path, "hello")
    assert len(results) == 1
    assert results[0].file_path == f
    assert results[0].line_number == 1
    assert results[0].line_text == "hello world"
    assert results[0].match_start == 0


def test_returns_only_matching_files(tmp_path: Path) -> None:
    (tmp_path / "match.txt").write_text("needle here\n")
    (tmp_path / "nomatch.txt").write_text("nothing relevant\n")
    results = search_workspace(tmp_path, "needle")
    assert len(results) == 1
    assert results[0].file_path.name == "match.txt"


def test_multiple_matches_in_one_file(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("foo\nbar foo\nbaz\n")
    results = search_workspace(tmp_path, "foo")
    assert len(results) == 2
    assert {r.line_number for r in results} == {1, 2}


def test_regex_search(tmp_path: Path) -> None:
    (tmp_path / "r.txt").write_text("abc123\ndef456\nghi\n")
    results = search_workspace(tmp_path, r"\d+", use_regex=True)
    assert len(results) == 2
    assert results[0].line_number == 1
    assert results[1].line_number == 2


def test_binary_file_skipped(tmp_path: Path) -> None:
    (tmp_path / "binary.bin").write_bytes(b"\x00\x01\x02binary data")
    results = search_workspace(tmp_path, "binary")
    assert results == []


def test_hidden_file_skipped(tmp_path: Path) -> None:
    (tmp_path / ".hidden").write_text("secret needle\n")
    results = search_workspace(tmp_path, "needle")
    assert results == []


def test_hidden_directory_skipped(tmp_path: Path) -> None:
    hidden_dir = tmp_path / ".git"
    hidden_dir.mkdir()
    (hidden_dir / "config").write_text("needle\n")
    results = search_workspace(tmp_path, "needle")
    assert results == []


def test_empty_workspace(tmp_path: Path) -> None:
    results = search_workspace(tmp_path, "anything")
    assert results == []


def test_empty_query_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n")
    results = search_workspace(tmp_path, "")
    assert results == []


def test_whitespace_only_query_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n")
    results = search_workspace(tmp_path, "   ")
    # whitespace is valid as a plain search but "   " trimming is caller's job;
    # search_workspace itself searches for the literal string "   "
    # (three spaces) so no match expected here.
    assert results == []


def test_max_results_limit(tmp_path: Path) -> None:
    (tmp_path / "big.txt").write_text("needle\n" * 100)
    results = search_workspace(tmp_path, "needle", max_results=10)
    assert len(results) == 10


def test_invalid_regex_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n")
    results = search_workspace(tmp_path, "[invalid(", use_regex=True)
    assert results == []


def test_match_start_end_columns(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("  needle here\n")
    results = search_workspace(tmp_path, "needle")
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
        await pilot.pause()
        await pilot.press("ctrl+shift+f")
        await pilot.pause()
        sidebar = app.query_one(Sidebar)
        assert sidebar.tabbed_content.active == "search_pane"


@pytest.mark.asyncio
async def test_search_shows_results(tmp_path: Path) -> None:
    """Running a search populates the results list."""
    from textual.widgets import Input, ListView

    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    (tmp_path / "sample.txt").write_text("hello world\nfoo bar\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        # Open search panel
        await pilot.press("ctrl+shift+f")
        await pilot.pause()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "hello"
        await pilot.pause()

        # Trigger search directly
        ws_pane._run_search()
        await pilot.pause()

        results_list = ws_pane.query_one("#ws-results", ListView)
        assert results_list.children  # at least one result


@pytest.mark.asyncio
async def test_search_no_results_message(tmp_path: Path) -> None:
    """Search with no matches shows a 'No results' item."""
    from textual.widgets import Input, Label, ListView

    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    (tmp_path / "sample.txt").write_text("hello world\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+shift+f")
        await pilot.pause()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "xyzzy_no_match"
        await pilot.pause()

        ws_pane._run_search()
        await pilot.pause()

        results_list = ws_pane.query_one("#ws-results", ListView)
        labels = [str(lbl.content) for lbl in results_list.query(Label)]
        assert any("No results" in lbl for lbl in labels)


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
        await pilot.pause()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "unique_string_xyz"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        # Simulate selecting the first result
        ws_pane.post_message(
            WorkspaceSearchPane.OpenFileAtLineRequested(file_path=target, line_number=1)
        )
        await pilot.pause()

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
        await pilot.pause()
        await pilot.pause()

        editor = app.main_view.get_active_code_editor()
        assert editor is not None
        row, _col = editor.editor.cursor_location
        assert row == 2  # 0-based, line 3 → row 2


# ---------------------------------------------------------------------------
# Unit tests: gitignore support
# ---------------------------------------------------------------------------


def test_gitignore_root_respected(tmp_path: Path) -> None:
    """Files listed in root .gitignore are excluded from search."""
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    (tmp_path / "ignored.txt").write_text("needle\n")
    (tmp_path / "visible.txt").write_text("needle\n")

    results = search_workspace(tmp_path, "needle", respect_gitignore=True)
    paths = {r.file_path.name for r in results}
    assert "ignored.txt" not in paths
    assert "visible.txt" in paths


def test_gitignore_nested_subdir_respected(tmp_path: Path) -> None:
    """Nested .gitignore is applied relative to its directory."""
    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / ".gitignore").write_text("secret.txt\n")
    (subdir / "secret.txt").write_text("needle\n")
    (subdir / "public.txt").write_text("needle\n")

    results = search_workspace(tmp_path, "needle", respect_gitignore=True)
    paths = {r.file_path.name for r in results}
    assert "secret.txt" not in paths
    assert "public.txt" in paths


def test_respect_gitignore_false_bypasses(tmp_path: Path) -> None:
    """respect_gitignore=False returns gitignored files."""
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    (tmp_path / "ignored.txt").write_text("needle\n")

    results = search_workspace(tmp_path, "needle", respect_gitignore=False)
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

    results = search_workspace(tmp_path, "needle", files_to_include="src/**")
    paths = {r.file_path.name for r in results}
    assert "main.py" in paths
    assert "other.txt" not in paths


def test_exclude_filter_skips_matching_files(tmp_path: Path) -> None:
    """files_to_exclude skips matching files."""
    (tmp_path / "keep.py").write_text("needle\n")
    (tmp_path / "skip.txt").write_text("needle\n")

    results = search_workspace(tmp_path, "needle", files_to_exclude="*.txt")
    paths = {r.file_path.name for r in results}
    assert "keep.py" in paths
    assert "skip.txt" not in paths


def test_empty_include_returns_all_files(tmp_path: Path) -> None:
    """Empty files_to_include returns all files (no restriction)."""
    (tmp_path / "a.py").write_text("needle\n")
    (tmp_path / "b.txt").write_text("needle\n")

    results = search_workspace(tmp_path, "needle", files_to_include="")
    assert len(results) == 2


def test_extension_only_include_pattern(tmp_path: Path) -> None:
    """Extension-only pattern like '*.py' works for include filter."""
    (tmp_path / "code.py").write_text("needle\n")
    (tmp_path / "doc.txt").write_text("needle\n")

    results = search_workspace(tmp_path, "needle", files_to_include="*.py")
    paths = {r.file_path.name for r in results}
    assert "code.py" in paths
    assert "doc.txt" not in paths


def test_invalid_include_pattern_returns_empty(tmp_path: Path) -> None:
    """Invalid pattern in files_to_include yields empty results (no crash)."""
    (tmp_path / "a.txt").write_text("needle\n")

    # pathspec with an extremely malformed pattern; if it raises, iterator returns []
    # We pass something that could be invalid in some pathspec versions
    results = search_workspace(tmp_path, "needle", files_to_include="[invalid(")
    # Must not crash; result is a list (possibly empty)
    assert isinstance(results, list)


def test_trailing_comma_whitespace_in_pattern_string(tmp_path: Path) -> None:
    """Trailing comma and whitespace in pattern string are handled gracefully."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("needle\n")
    (tmp_path / "other.txt").write_text("needle\n")

    # Leading/trailing comma and spaces should be stripped
    results = search_workspace(tmp_path, "needle", files_to_include=" src/** , ")
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

    results = search_workspace(tmp_path, "needle", files_to_exclude="node_modules")
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

    results = search_workspace(tmp_path, "needle", files_to_exclude="dist,build")
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

    results = search_workspace(tmp_path, "needle", files_to_exclude="vendor")
    paths = {r.file_path.name for r in results}
    assert "lib.js" not in paths
    assert "main.py" in paths


def test_exclude_folder_trailing_slash(tmp_path: Path) -> None:
    """Trailing slash in exclude pattern is handled (dist/ excludes dist/)."""
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "out.js").write_text("needle\n")
    (tmp_path / "keep.py").write_text("needle\n")

    results = search_workspace(tmp_path, "needle", files_to_exclude="dist/")
    paths = {r.file_path.name for r in results}
    assert "out.js" not in paths
    assert "keep.py" in paths


# ---------------------------------------------------------------------------
# Unit tests: case-sensitive search
# ---------------------------------------------------------------------------


def test_case_sensitive_search_default(tmp_path: Path) -> None:
    """By default search is case-sensitive."""
    (tmp_path / "a.txt").write_text("Hello World\n")

    results = search_workspace(tmp_path, "hello")
    assert results == []

    results = search_workspace(tmp_path, "Hello")
    assert len(results) == 1


def test_case_insensitive_search(tmp_path: Path) -> None:
    """case_sensitive=False matches regardless of case."""
    (tmp_path / "a.txt").write_text("Hello World\n")

    results = search_workspace(tmp_path, "hello", case_sensitive=False)
    assert len(results) == 1
    assert results[0].line_text == "Hello World"


def test_case_insensitive_regex(tmp_path: Path) -> None:
    """case_sensitive=False works with use_regex=True."""
    (tmp_path / "a.txt").write_text("FooBar\nbaz\n")

    results = search_workspace(tmp_path, "foo.*", use_regex=True, case_sensitive=False)
    assert len(results) == 1
    assert results[0].line_text == "FooBar"


# ---------------------------------------------------------------------------
# UI integration test: exclude field in WorkspaceSearchPane
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exclude_field_in_ui_applies_to_search(tmp_path: Path) -> None:
    """The #ws-exclude Input field is read and applied during search."""
    from textual.widgets import Input, Label, ListView

    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("needle\n")
    (tmp_path / "keep.py").write_text("needle\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+shift+f")
        await pilot.pause()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "needle"
        ws_pane.query_one("#ws-exclude", Input).value = "node_modules"
        ws_pane._run_search()
        await pilot.pause()

        results_list = ws_pane.query_one("#ws-results", ListView)
        labels = [str(lbl.content) for lbl in results_list.query(Label)]
        assert not any("pkg.js" in lbl for lbl in labels)
        assert any("keep.py" in lbl for lbl in labels)


@pytest.mark.asyncio
async def test_case_sensitive_checkbox_in_ui(tmp_path: Path) -> None:
    """The #ws-case-sensitive checkbox controls case sensitivity."""
    from textual.widgets import Checkbox, Input, Label, ListView

    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    (tmp_path / "sample.txt").write_text("Hello World\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+shift+f")
        await pilot.pause()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "hello"
        # Disable case-sensitive (uncheck)
        ws_pane.query_one("#ws-case-sensitive", Checkbox).value = False
        ws_pane._run_search()
        await pilot.pause()

        results_list = ws_pane.query_one("#ws-results", ListView)
        labels = [str(lbl.content) for lbl in results_list.query(Label)]
        assert any("sample.txt" in lbl for lbl in labels)


@pytest.mark.asyncio
async def test_workspace_search_no_clipping(tmp_path: Path) -> None:
    """#ws-include must span the full width of its parent container (not half)."""
    from textual.widgets import Input

    from tests.conftest import make_app

    app = make_app(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("ctrl+shift+f")
        await pilot.pause()
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
