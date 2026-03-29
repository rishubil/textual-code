"""Tests ported from VSCode's workspace search test suite.

Sources:
- searchModel.test.ts: result aggregation, search clearing, cancellation, regex replace
- searchResult.test.ts: match properties, file matching, replace, hierarchy
- searchViewlet.test.ts: result sorting, path ordering

Key coverage gaps filled:
- Multi-file result aggregation with multiple matches per file
- Result tree clearing when a new search starts
- Exclusive worker cancellation (previous search cancelled by new search)
- Regex capture group replacement in workspace-level replace
- Match text extraction from line_text using match_start/match_end
- Tree hierarchy: root → file nodes → match leaf nodes
- Replace removes patterns from disk files
- Result ordering by file path
- Nested directory Tree grouping

Behavioral differences from VSCode:
- Capture group syntax: VSCode uses $1, our replace uses \\1 (Python re.sub)
- Cancellation: VSCode uses CancellationToken, we use exclusive Textual workers
- Results structure: VSCode uses FileMatch/Match hierarchy, we use flat
  WorkspaceSearchResult list grouped by file in the Tree widget
- Sorting: VSCode uses custom comparers, we rely on ripgrep-rs native path sort
"""

from __future__ import annotations

from itertools import groupby
from pathlib import Path

import pytest

from textual_code.search import (
    replace_workspace,
    search_workspace,
)

# ── Unit: search_workspace result aggregation ────────────────────────────
# Adapted from searchModel.test.ts "Search Model: Search adds to results"


def test_search_adds_to_results_multiple_files(tmp_path: Path) -> None:
    """Search returns results from multiple files (VSCode line 290).

    Verifies that searching across multiple files returns the correct
    number of file groups and match counts per file.
    """
    (tmp_path / "file1.txt").write_text("preview 1 matched\npreview 1 also matched\n")
    (tmp_path / "file2.txt").write_text("preview 2 matched\n")

    results = search_workspace(tmp_path, "matched").results

    # Group results by file to verify aggregation
    groups = {k: list(v) for k, v in groupby(results, key=lambda r: r.file_path)}
    assert len(groups) == 2, f"Expected 2 file groups, got {len(groups)}"

    file1_results = [r for r in results if r.file_path.name == "file1.txt"]
    file2_results = [r for r in results if r.file_path.name == "file2.txt"]

    assert len(file1_results) == 2, "file1.txt should have 2 matches"
    assert len(file2_results) == 1, "file2.txt should have 1 match"


def test_search_adds_to_results_match_positions(tmp_path: Path) -> None:
    """Match positions (start/end columns) are correctly reported (VSCode line 290).

    VSCode verifies range positions for each match. We verify match_start
    and match_end character offsets.
    """
    (tmp_path / "test.txt").write_text("hello world hello\n")

    results = search_workspace(tmp_path, "hello").results
    assert len(results) == 2

    # First "hello" at column 0-5
    assert results[0].match_start == 0
    assert results[0].match_end == 5
    assert results[0].line_text == "hello world hello"

    # Second "hello" at column 12-17
    assert results[1].match_start == 12
    assert results[1].match_end == 17


def test_search_adds_to_results_line_numbers(tmp_path: Path) -> None:
    """Line numbers are 1-based and correct for each match (VSCode line 290).

    VSCode uses Range(line, col) with 1-based lines. Our WorkspaceSearchResult
    also uses 1-based line_number.
    """
    content = "no match here\nfirst match\nno match\nsecond match\n"
    (tmp_path / "test.txt").write_text(content)

    results = search_workspace(tmp_path, "match").results

    # "match" appears on lines 1 ("no match here"), 2, 3, and 4
    # Actually: line 1: "no match here" has "match" at pos 3
    #           line 2: "first match" has "match"
    #           line 3: "no match" has "match"
    #           line 4: "second match" has "match"
    assert len(results) == 4
    assert [r.line_number for r in results] == [1, 2, 3, 4]


def test_search_adds_to_results_preserves_line_text(tmp_path: Path) -> None:
    """Line text is preserved for each match result (VSCode line 310).

    VSCode checks match.text() against the preview string.
    We verify WorkspaceSearchResult.line_text matches the original line.
    """
    (tmp_path / "a.txt").write_text("alpha needle beta\n")
    (tmp_path / "b.txt").write_text("gamma needle delta\n")

    results = search_workspace(tmp_path, "needle").results
    assert len(results) == 2

    texts = {r.line_text for r in results}
    assert "alpha needle beta" in texts
    assert "gamma needle delta" in texts


# ── Unit: search results cleared ─────────────────────────────────────────
# Adapted from searchModel.test.ts "Search results are cleared during search"


def test_second_search_returns_independent_results(tmp_path: Path) -> None:
    """A second search returns fresh results, not accumulated (VSCode line 555).

    VSCode tests that searchResult.isEmpty() is true when a new search starts.
    At the unit level, each search_workspace() call returns independent results.
    """
    (tmp_path / "a.txt").write_text("hello world\n")
    (tmp_path / "b.txt").write_text("goodbye world\n")

    # First search: matches "hello" in a.txt
    results1 = search_workspace(tmp_path, "hello").results
    assert len(results1) == 1
    assert results1[0].file_path.name == "a.txt"

    # Second search: matches "goodbye" in b.txt (not "hello")
    results2 = search_workspace(tmp_path, "goodbye").results
    assert len(results2) == 1
    assert results2[0].file_path.name == "b.txt"

    # Results are independent — results2 does not contain results1
    assert all(r.file_path.name != "a.txt" for r in results2)


# ── Unit: regex replace with capture groups ──────────────────────────────
# Adapted from searchModel.test.ts "getReplaceString returns proper replace
# string for regExpressions"


def test_replace_plain_string(tmp_path: Path) -> None:
    """Plain (non-regex) replace substitutes literal text (VSCode line 601).

    VSCode: pattern='re', replaceString='hello' → match.replaceString == 'hello'
    """
    f = tmp_path / "test.txt"
    f.write_text("rested well\n")

    result = replace_workspace(tmp_path, "re", "hello")
    assert result.replacements_count == 1
    assert f.read_text() == "hellosted well\n"


def test_replace_regex_literal(tmp_path: Path) -> None:
    """Regex replace with no capture groups uses literal replacement (VSCode line 605).

    VSCode: pattern='re' (isRegExp=true), replaceString='hello'
    """
    f = tmp_path / "test.txt"
    f.write_text("preview 1 rested\n")

    result = replace_workspace(tmp_path, "re", "hello", use_regex=True)
    # "re" in "preview" and "rested" → both replaced
    assert result.replacements_count == 2
    assert f.read_text() == "phelloview 1 hellosted\n"


def test_replace_regex_non_capturing_group(tmp_path: Path) -> None:
    """Regex with non-capturing group (?:...) replaces correctly (VSCode line 609).

    VSCode: pattern='re(?:vi)', replaceString='hello'
    """
    f = tmp_path / "test.txt"
    f.write_text("preview 1\n")

    result = replace_workspace(tmp_path, r"re(?:vi)", "hello", use_regex=True)
    assert result.replacements_count == 1
    assert f.read_text() == "phelloew 1\n"


def test_replace_regex_capturing_group_unused(tmp_path: Path) -> None:
    """Regex with capture group, replacement ignores it (VSCode line 613).

    VSCode: pattern='r(e)(?:vi)', replaceString='hello'
    Our system: same behavior — capture group is ignored in replacement.
    """
    f = tmp_path / "test.txt"
    f.write_text("preview 1\n")

    result = replace_workspace(tmp_path, r"r(e)(?:vi)", "hello", use_regex=True)
    assert result.replacements_count == 1
    assert f.read_text() == "phelloew 1\n"


def test_replace_regex_capturing_group_backreference(tmp_path: Path) -> None:
    r"""Regex with capturing group and backreference in replacement (VSCode line 617).

    VSCode: pattern='r(e)(?:vi)', replaceString='hello$1' → 'helloe'
    Our system: Python uses \1 syntax instead of $1.
    Behavioral difference: VSCode uses $1 for capture groups,
    our replace_workspace uses Python's re.sub which expects \1.
    """
    f = tmp_path / "test.txt"
    f.write_text("preview 1\n")

    # Python re.sub uses \1 for backreference (not $1 like VSCode)
    result = replace_workspace(tmp_path, r"r(e)(?:vi)", r"hello\1", use_regex=True)
    assert result.replacements_count == 1
    assert f.read_text() == "phelloeew 1\n"


def test_replace_regex_multiple_capturing_groups(tmp_path: Path) -> None:
    r"""Multiple capturing groups with backreferences.

    Extension of VSCode test — verifies \1 and \2 work together.
    """
    f = tmp_path / "test.txt"
    f.write_text("2025-03-28\n")

    result = replace_workspace(
        tmp_path, r"(\d{4})-(\d{2})-(\d{2})", r"\2/\3/\1", use_regex=True
    )
    assert result.replacements_count == 1
    assert f.read_text() == "03/28/2025\n"


# ── Integration: Tree result clearing on new search ──────────────────────
# Adapted from searchModel.test.ts "Search results are cleared during search"


@pytest.mark.asyncio
async def test_search_tree_cleared_on_new_search(tmp_path: Path) -> None:
    """Starting a new search clears previous results from the Tree (VSCode line 555).

    VSCode verifies searchResult.isEmpty() is true when a new search begins,
    even before the new search completes. We verify the Tree widget is cleared.
    """
    from textual.widgets import Input, Tree

    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    (tmp_path / "a.txt").write_text("hello world\n")
    (tmp_path / "b.txt").write_text("hello again\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+shift+f")
        await pilot.pause()

        ws_pane = app.query_one(WorkspaceSearchPane)
        query_input = ws_pane.query_one("#ws-query", Input)
        results_tree = ws_pane.query_one("#ws-results", Tree)

        # First search: populate results
        query_input.value = "hello"
        await pilot.pause()
        ws_pane._run_search()
        await pilot.pause()

        # Verify results are populated
        assert len(results_tree.root.children) > 0, "First search should have results"

        # Second search with different query — tree should be cleared first
        query_input.value = "nonexistent_string_xyz"
        await pilot.pause()
        ws_pane._run_search()
        await pilot.pause()

        # After the second search completes, results should show "No results"
        node_labels = [str(n.label) for n in results_tree.root.children]
        assert any("No results" in lbl for lbl in node_labels), (
            f"Expected 'No results' after nonexistent search, got: {node_labels}"
        )


# ── Integration: exclusive worker cancellation ───────────────────────────
# Adapted from searchModel.test.ts "Previous search is cancelled when new
# search is called"


@pytest.mark.asyncio
async def test_previous_search_cancelled_by_new_search(
    tmp_path: Path, monkeypatch
) -> None:
    """New search cancels the previous search worker (VSCode line 575).

    VSCode verifies CancellationToken.isCancellationRequested after starting
    a second search. We verify that Textual's exclusive worker mechanism
    cancels the first search when a second is started.
    """
    import threading

    from textual.widgets import Input
    from textual.worker import WorkerState

    import textual_code.widgets.workspace_search as ws_module
    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    # Create files so search has something to find
    for i in range(10):
        (tmp_path / f"file{i}.txt").write_text(f"needle content {i}\n")

    # Track search invocation count and block first search
    call_count = 0
    gate = threading.Event()
    original_search = ws_module.search_workspace

    def tracked_search(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1 and not gate.wait(timeout=5):
            raise RuntimeError("Gate timed out")
        return original_search(*args, **kwargs)

    monkeypatch.setattr(ws_module, "search_workspace", tracked_search)

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+shift+f")
        await pilot.pause()

        ws_pane = app.query_one(WorkspaceSearchPane)
        query_input = ws_pane.query_one("#ws-query", Input)

        # Start first search (will block on gate)
        query_input.value = "needle"
        await pilot.pause()
        ws_pane._run_search()
        await pilot.pause()

        # Capture reference to the first worker
        first_workers = [
            w for w in app.workers if w.group == "search" and not w.is_finished
        ]
        assert len(first_workers) >= 1, "First search worker should be running"
        first_worker = first_workers[0]

        # Start second search — exclusive worker should cancel the first
        query_input.value = "content"
        await pilot.pause()
        ws_pane._run_search()
        await pilot.pause()

        # Release the gate so the first search can complete (or notice cancellation)
        gate.set()
        await pilot.pause()
        await pilot.pause()

        # The first worker should have been cancelled by the exclusive worker mechanism
        assert first_worker.state == WorkerState.CANCELLED, (
            f"First worker should be CANCELLED, got {first_worker.state}"
        )


# ── Integration: Tree result aggregation with grouping ───────────────────
# Extended from searchModel.test.ts "Search adds to results" — verifies
# the full pipeline from search_workspace → Tree grouping


@pytest.mark.asyncio
async def test_search_tree_groups_results_by_file(tmp_path: Path) -> None:
    """Tree groups results by file with match counts (VSCode line 290).

    Extends the unit test to verify the full integration: search → Tree widget.
    File nodes show path and match count; leaf nodes show line number and text.
    """
    from textual.widgets import Input, Tree

    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    # Create files with known content — multiple matches in file1
    (tmp_path / "file1.txt").write_text("alpha target\nbeta target\n")
    (tmp_path / "file2.txt").write_text("gamma target\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+shift+f")
        await pilot.pause()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "target"
        ws_pane._run_search()
        await pilot.pause()

        results_tree = ws_pane.query_one("#ws-results", Tree)
        file_nodes = list(results_tree.root.children)

        assert len(file_nodes) == 2, f"Expected 2 file groups, got {len(file_nodes)}"

        # Find nodes by filename (order depends on ripgrep path sorting)
        node_labels = {str(n.label): n for n in file_nodes}
        file1_label = next(lbl for lbl in node_labels if "file1.txt" in lbl)
        file2_label = next(lbl for lbl in node_labels if "file2.txt" in lbl)

        assert "2 matches" in file1_label
        assert "1 match" in file2_label
        assert "1 matches" not in file2_label  # singular form

        # Verify leaf children of file1 node
        file1_node = node_labels[file1_label]
        file1_children = list(file1_node.children)
        assert len(file1_children) == 2
        assert "1:" in str(file1_children[0].label)
        assert "alpha target" in str(file1_children[0].label)
        assert "2:" in str(file1_children[1].label)
        assert "beta target" in str(file1_children[1].label)


# ══════════════════════════════════════════════════════════════════════════
# Phase 3: searchResult.test.ts — match properties, hierarchy, replace
# ══════════════════════════════════════════════════════════════════════════

# ── Unit: match text extraction ──────────────────────────────────────────
# Adapted from searchResult.test.ts "Line Match" (line 73)


def test_line_match_text_extraction(tmp_path: Path) -> None:
    """Matched text can be extracted from line_text via match_start/match_end.

    VSCode: lineMatch.fullMatchText() returns 'foo' from '0 foo bar'.
    Our equivalent: line_text[match_start:match_end] gives the matched text.
    """
    (tmp_path / "test.txt").write_text("0 foo bar\n")

    results = search_workspace(tmp_path, "foo").results
    assert len(results) == 1

    r = results[0]
    assert r.line_text == "0 foo bar"
    # Extract matched text using offsets — equivalent to fullMatchText()
    assert r.line_text[r.match_start : r.match_end] == "foo"


def test_line_match_full_line_context(tmp_path: Path) -> None:
    """line_text provides full line context including non-matched text.

    VSCode: lineMatch.fullMatchText(true) returns the full preview line.
    Our equivalent: line_text always contains the full line.
    """
    (tmp_path / "test.txt").write_text("prefix needle suffix\n")

    results = search_workspace(tmp_path, "needle").results
    assert len(results) == 1

    r = results[0]
    assert r.line_text == "prefix needle suffix"
    assert r.line_text[r.match_start : r.match_end] == "needle"
    # Full context preserved — matches VSCode's fullMatchText(true)
    assert "prefix" in r.line_text
    assert "suffix" in r.line_text


# ── Unit: file match properties ──────────────────────────────────────────
# Adapted from searchResult.test.ts "File Match" (line 94)


def test_file_match_path_property(tmp_path: Path) -> None:
    """file_path points to the correct file.

    VSCode: fileMatch.resource.toString() == 'file:///folder/file.txt'
    Our equivalent: result.file_path resolves to the actual file on disk.
    """
    target = tmp_path / "folder" / "file.txt"
    target.parent.mkdir(parents=True)
    target.write_text("matched content\n")

    results = search_workspace(tmp_path, "matched").results
    assert len(results) == 1
    assert results[0].file_path == target
    assert results[0].file_path.name == "file.txt"


def test_file_match_name_from_path(tmp_path: Path) -> None:
    """File name can be derived from file_path.

    VSCode: fileMatch.name() returns 'file.txt' from 'folder/file.txt'.
    """
    (tmp_path / "deep" / "nested").mkdir(parents=True)
    (tmp_path / "deep" / "nested" / "target.py").write_text("found\n")

    results = search_workspace(tmp_path, "found").results
    assert len(results) == 1
    assert results[0].file_path.name == "target.py"


# ── Unit: multiple matches on the same line ──────────────────────────────
# Adapted from searchResult.test.ts "Adding a raw match will add a file
# match with line matches" (line 189) — multiple matches with same preview


def test_multiple_matches_same_line(tmp_path: Path) -> None:
    """Multiple same-line matches produce separate results.

    VSCode: Adding 3 TextSearchMatch instances to the same file creates
    3 MatchImpl objects. We verify that multiple occurrences on the same
    line produce separate WorkspaceSearchResult entries.
    """
    (tmp_path / "test.txt").write_text("foo bar foo baz foo\n")

    results = search_workspace(tmp_path, "foo").results
    assert len(results) == 3

    # All results are on the same line
    assert all(r.line_number == 1 for r in results)
    assert all(r.line_text == "foo bar foo baz foo" for r in results)

    # Each match has unique position
    starts = [r.match_start for r in results]
    assert starts == [0, 8, 16], f"Expected [0, 8, 16], got {starts}"
    assert all(r.match_end - r.match_start == 3 for r in results)


# ── Unit: replace removes pattern from file ──────────────────────────────
# Adapted from searchResult.test.ts "replace should remove the file match"
# (line 358)


def test_replace_removes_pattern_from_file(tmp_path: Path) -> None:
    """After replace, the pattern no longer exists in the file.

    VSCode: testObject.replace(fileMatch) → testObject.isEmpty() is true.
    Our equivalent: after replace_workspace, searching again finds nothing.
    """
    f = tmp_path / "test.txt"
    f.write_text("preview 1 matched\n")

    result = replace_workspace(tmp_path, "matched", "replaced")
    assert result.replacements_count == 1
    assert result.files_modified == 1

    # After replace, pattern is gone — equivalent to testObject.isEmpty()
    verify = search_workspace(tmp_path, "matched").results
    assert len(verify) == 0

    # Replacement text is present
    assert "replaced" in f.read_text()


# ── Unit: replaceAll removes all matches across files ────────────────────
# Adapted from searchResult.test.ts "replaceAll should remove all file
# matches" (line 391)


def test_replace_all_removes_all_patterns(tmp_path: Path) -> None:
    """After replace all, no files contain the pattern.

    VSCode: testObject.replaceAll(null) → testObject.isEmpty() is true.
    Our equivalent: replace_workspace processes all files, none left with match.
    """
    (tmp_path / "file1.txt").write_text("preview 1 target\n")
    (tmp_path / "file2.txt").write_text("preview 2 target\n")

    result = replace_workspace(tmp_path, "target", "done")
    assert result.replacements_count == 2
    assert result.files_modified == 2

    # After replace all, pattern is gone from ALL files
    verify = search_workspace(tmp_path, "target").results
    assert len(verify) == 0

    assert "done" in (tmp_path / "file1.txt").read_text()
    assert "done" in (tmp_path / "file2.txt").read_text()


def test_replace_preserves_unmatched_content(tmp_path: Path) -> None:
    """Replace only changes matched text; surrounding content is preserved.

    Verifies that replace_workspace does not corrupt non-matched portions
    of the file, especially important for multi-line files.
    """
    f = tmp_path / "test.txt"
    f.write_text("line one\nfoo target bar\nline three\n")

    replace_workspace(tmp_path, "target", "replaced")

    lines = f.read_text().splitlines()
    assert lines[0] == "line one"
    assert lines[1] == "foo replaced bar"
    assert lines[2] == "line three"


# ── Unit: results sorted by file path ────────────────────────────────────
# Adapted from searchViewlet.test.ts "Comparer" (line 97)


def test_search_results_sorted_by_file_path(tmp_path: Path) -> None:
    """Results are returned sorted by file path.

    VSCode: searchMatchComparer(fileMatch1, fileMatch2) orders by path.
    Our ripgrep-rs backend returns results sorted by path natively.
    """
    # Create files in reverse alphabetical order to test sorting
    (tmp_path / "zoo.txt").write_text("needle\n")
    (tmp_path / "alpha.txt").write_text("needle\n")
    (tmp_path / "mid.txt").write_text("needle\n")

    results = search_workspace(tmp_path, "needle").results
    assert len(results) == 3

    paths = [r.file_path.name for r in results]
    assert paths == sorted(paths), f"Results not sorted by path: {paths}"


def test_search_results_nested_paths_sorted(tmp_path: Path) -> None:
    """Nested path results maintain path sort order.

    VSCode: searchMatchComparer sorts /foo before /with/path before
    /with/path/foo. Ripgrep sorts by path components (directories before
    files at the same level), so with/path/ contents appear before with/path.txt.

    Behavioral difference: ripgrep uses component-wise sorting where
    directory entries sort before sibling files (with/path/foo.txt < with/path.txt).
    """
    (tmp_path / "with" / "path").mkdir(parents=True)
    (tmp_path / "foo.txt").write_text("needle\n")
    (tmp_path / "with" / "path.txt").write_text("needle\n")
    (tmp_path / "with" / "path" / "foo.txt").write_text("needle\n")

    results = search_workspace(tmp_path, "needle").results
    assert len(results) == 3

    rel_paths = [str(r.file_path.relative_to(tmp_path)) for r in results]

    # Ripgrep sorts by path components: directory contents come before
    # sibling files. So with/path/foo.txt sorts before with/path.txt.
    assert rel_paths[0] == "foo.txt"
    assert "with/path/foo.txt" in rel_paths[1]
    assert "with/path.txt" in rel_paths[2]


# ── Integration: Tree hierarchy ──────────────────────────────────────────
# Adapted from searchResult.test.ts "Match -> FileMatch -> SearchResult
# hierarchy exists" (line 176)


@pytest.mark.asyncio
async def test_tree_hierarchy_file_and_match_nodes(tmp_path: Path) -> None:
    """Tree has correct two-level hierarchy: file nodes → match leaf nodes.

    VSCode: lineMatch.parent() === fileMatch, fileMatch.parent() === folderMatch.
    Our Tree: root.children are file nodes, file_node.children are match leaves.
    """
    from textual.widgets import Input, Tree

    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    (tmp_path / "test.txt").write_text("alpha needle\nbeta needle\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+shift+f")
        await pilot.pause()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "needle"
        ws_pane._run_search()
        await pilot.pause()

        results_tree = ws_pane.query_one("#ws-results", Tree)

        # Level 1: file nodes are direct children of root
        file_nodes = list(results_tree.root.children)
        assert len(file_nodes) == 1
        assert "test.txt" in str(file_nodes[0].label)

        # Level 2: match leaves are children of the file node
        match_nodes = list(file_nodes[0].children)
        assert len(match_nodes) == 2
        assert not match_nodes[0].allow_expand  # match nodes are leaves
        assert not match_nodes[1].allow_expand


# ── Integration: Tree node data storage ──────────────────────────────────
# Verifies that tree nodes store correct data for file navigation


@pytest.mark.asyncio
async def test_tree_node_data_stores_file_and_line(tmp_path: Path) -> None:
    """Tree nodes store (file_path, line_number) tuples for navigation.

    File nodes store (file_path, first_match_line).
    Match leaf nodes store (file_path, match_line_number).
    This data is used by on_tree_node_selected to open files.
    """
    from textual.widgets import Input, Tree

    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    target = tmp_path / "data.txt"
    target.write_text("line one\nneedle here\nline three\nneedle again\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+shift+f")
        await pilot.pause()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "needle"
        ws_pane._run_search()
        await pilot.pause()

        results_tree = ws_pane.query_one("#ws-results", Tree)
        file_nodes = list(results_tree.root.children)
        assert len(file_nodes) == 1

        # File node data: (file_path, first_match_line_number)
        file_data = file_nodes[0].data
        assert file_data[0] == target
        assert file_data[1] == 2  # "needle here" is on line 2

        # Match leaf node data: (file_path, match_line_number)
        match_leaves = list(file_nodes[0].children)
        assert len(match_leaves) == 2
        assert match_leaves[0].data == (target, 2)
        assert match_leaves[1].data == (target, 4)


# ── Integration: nested directory Tree grouping ──────────────────────────
# Adapted from searchResult.test.ts "Creating a model with nested folders
# should create the correct structure" (line 497)


@pytest.mark.asyncio
async def test_nested_directory_tree_grouping(tmp_path: Path) -> None:
    """Nested directory results show relative paths in Tree file nodes.

    VSCode: Nested folder matches display hierarchically with folder grouping.
    Our Tree: File nodes show relative paths from workspace root, naturally
    grouping by directory through the path prefix.
    """
    from textual.widgets import Input, Tree

    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    # Create nested directory structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "deep").mkdir()
    (tmp_path / "src" / "app.py").write_text("needle in app\n")
    (tmp_path / "src" / "deep" / "util.py").write_text("needle in util\n")
    (tmp_path / "root.txt").write_text("needle at root\n")

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+shift+f")
        await pilot.pause()

        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "needle"
        ws_pane._run_search()
        await pilot.pause()

        results_tree = ws_pane.query_one("#ws-results", Tree)
        file_nodes = list(results_tree.root.children)
        assert len(file_nodes) == 3, f"Expected 3 file groups, got {len(file_nodes)}"

        # Collect labels for verification
        labels = [str(n.label) for n in file_nodes]

        # All three files should appear with relative paths
        assert any("root.txt" in lbl for lbl in labels)
        assert any("app.py" in lbl for lbl in labels)
        assert any("util.py" in lbl for lbl in labels)

        # Nested files should show directory prefix in their label
        deep_label = next(lbl for lbl in labels if "util.py" in lbl)
        assert "src/deep/util.py" in deep_label or "src\\deep\\util.py" in deep_label
