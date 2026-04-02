"""Tests for workspace replace feature.

Covers:
- replace_workspace() pure function (unit tests)
- WorkspaceSearchPane replace UI integration tests
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from textual_code.search import (
    WorkspaceReplaceResult,
    WorkspaceSearchResult,
    _replace_at_positions,
    apply_selected_replace,
    apply_workspace_replace,
    preview_selected_replace,
    preview_workspace_replace,
    replace_workspace,
)

# ---------------------------------------------------------------------------
# Unit tests: replace_workspace()
# ---------------------------------------------------------------------------


def test_replace_simple(tmp_path: Path) -> None:
    f = tmp_path / "hello.txt"
    f.write_text("hello world\n")
    result = replace_workspace(tmp_path, "hello", "hi")
    assert result.files_modified == 1
    assert result.replacements_count == 1
    assert f.read_text() == "hi world\n"


def test_replace_no_match(tmp_path: Path) -> None:
    f = tmp_path / "hello.txt"
    f.write_text("hello world\n")
    result = replace_workspace(tmp_path, "xyz", "abc")
    assert result.files_modified == 0
    assert result.replacements_count == 0
    assert f.read_text() == "hello world\n"


def test_replace_multiple_occurrences_in_one_file(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("foo bar foo\nfoo baz\n")
    result = replace_workspace(tmp_path, "foo", "qux")
    assert result.replacements_count == 3
    assert result.files_modified == 1
    assert f.read_text() == "qux bar qux\nqux baz\n"


def test_replace_multiple_files(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("needle here\n")
    (tmp_path / "b.txt").write_text("another needle\n")
    (tmp_path / "c.txt").write_text("no match\n")
    result = replace_workspace(tmp_path, "needle", "pin")
    assert result.files_modified == 2
    assert result.replacements_count == 2


def test_replace_empty_query_returns_zero(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("hello\n")
    result = replace_workspace(tmp_path, "", "replacement")
    assert result.files_modified == 0
    assert result.replacements_count == 0
    assert f.read_text() == "hello\n"


def test_replace_regex(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("foo123\nbar456\n")
    result = replace_workspace(tmp_path, r"\d+", "X", use_regex=True)
    assert result.replacements_count == 2
    assert f.read_text() == "fooX\nbarX\n"


def test_replace_invalid_regex_returns_zero(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("hello\n")
    result = replace_workspace(tmp_path, "[invalid(", "x", use_regex=True)
    assert result.files_modified == 0
    assert result.replacements_count == 0
    assert f.read_text() == "hello\n"


def test_replace_binary_file_skipped(tmp_path: Path) -> None:
    f = tmp_path / "binary.bin"
    f.write_bytes(b"\x00\x01binary data")
    result = replace_workspace(tmp_path, "binary", "text")
    assert result.files_modified == 0


def test_replace_hidden_file_included_by_default(tmp_path: Path) -> None:
    """Hidden files are replaced when show_hidden_files=True (default)."""
    f = tmp_path / ".hidden"
    f.write_text("needle\n")
    result = replace_workspace(tmp_path, "needle", "pin")
    assert result.files_modified == 1
    assert f.read_text() == "pin\n"


def test_replace_hidden_file_skipped_when_disabled(tmp_path: Path) -> None:
    """Hidden files are skipped when show_hidden_files=False."""
    f = tmp_path / ".hidden"
    f.write_text("needle\n")
    result = replace_workspace(tmp_path, "needle", "pin", show_hidden_files=False)
    assert result.files_modified == 0
    assert f.read_text() == "needle\n"


def test_replace_hidden_directory_skipped(tmp_path: Path) -> None:
    hidden = tmp_path / ".git"
    hidden.mkdir()
    f = hidden / "config"
    f.write_text("needle\n")
    result = replace_workspace(tmp_path, "needle", "pin")
    assert result.files_modified == 0
    assert f.read_text() == "needle\n"


def test_replace_result_dataclass_fields() -> None:
    r = WorkspaceReplaceResult(files_modified=3, replacements_count=7)
    assert r.files_modified == 3
    assert r.replacements_count == 7


def test_replace_empty_workspace(tmp_path: Path) -> None:
    result = replace_workspace(tmp_path, "anything", "something")
    assert result.files_modified == 0
    assert result.replacements_count == 0


def test_replace_preserves_other_content(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("line1\nhello\nline3\n")
    replace_workspace(tmp_path, "hello", "bye")
    assert f.read_text() == "line1\nbye\nline3\n"


# ---------------------------------------------------------------------------
# Unit tests: preview_workspace_replace()
# ---------------------------------------------------------------------------


def test_preview_single_file_diff(tmp_path: Path) -> None:
    f = tmp_path / "hello.txt"
    f.write_text("hello world\n")
    resp = preview_workspace_replace(tmp_path, "hello", "hi")
    assert len(resp.previews) == 1
    p = resp.previews[0]
    assert p.rel_path == "hello.txt"
    assert p.replacement_count == 1
    assert len(p.original_hash) == 64  # SHA-256 hex
    assert any("-" in line for line in p.diff_lines)
    assert any("+" in line for line in p.diff_lines)
    assert not resp.is_truncated


def test_preview_multiple_files(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("needle here\n")
    (tmp_path / "b.txt").write_text("another needle\n")
    (tmp_path / "c.txt").write_text("no match\n")
    resp = preview_workspace_replace(tmp_path, "needle", "pin")
    assert len(resp.previews) == 2
    rel_paths = {p.rel_path for p in resp.previews}
    assert "a.txt" in rel_paths
    assert "b.txt" in rel_paths


def test_preview_no_matches_yields_nothing(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n")
    resp = preview_workspace_replace(tmp_path, "xyz", "abc")
    assert len(resp.previews) == 0
    assert not resp.is_truncated


def test_preview_regex_mode(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("foo123\nbar456\n")
    resp = preview_workspace_replace(tmp_path, r"\d+", "X", use_regex=True)
    assert len(resp.previews) == 1
    assert resp.previews[0].replacement_count == 2


def test_preview_binary_file_skipped(tmp_path: Path) -> None:
    (tmp_path / "binary.bin").write_bytes(b"\x00\x01binary data")
    resp = preview_workspace_replace(tmp_path, "binary", "text")
    assert len(resp.previews) == 0


def test_preview_diff_context_lines(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"line1\nline2\nold\nline4\nline5\n")
    resp = preview_workspace_replace(tmp_path, "old", "new")
    assert len(resp.previews) == 1
    diff_text = "".join(resp.previews[0].diff_lines)
    assert "@@" in diff_text
    assert "-old" in diff_text
    assert "+new" in diff_text


def test_preview_same_query_and_replacement(tmp_path: Path) -> None:
    """When query equals replacement, no files should appear in preview."""
    (tmp_path / "a.txt").write_text("foo bar foo\n")
    resp = preview_workspace_replace(tmp_path, "foo", "foo")
    assert len(resp.previews) == 0


def test_preview_truncated_when_exceeding_max_files(tmp_path: Path) -> None:
    for i in range(5):
        (tmp_path / f"file{i}.txt").write_text("needle\n")
    resp = preview_workspace_replace(tmp_path, "needle", "pin", max_files=3)
    assert len(resp.previews) == 3
    assert resp.is_truncated


def test_preview_empty_query_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n")
    resp = preview_workspace_replace(tmp_path, "", "x")
    assert len(resp.previews) == 0


def test_preview_case_insensitive(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("Hello HELLO hello\n")
    resp = preview_workspace_replace(tmp_path, "hello", "hi", case_sensitive=False)
    assert len(resp.previews) == 1
    assert resp.previews[0].replacement_count == 3


# ---------------------------------------------------------------------------
# Unit tests: apply_workspace_replace()
# ---------------------------------------------------------------------------


def test_apply_replaces_files(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello world\n")
    (tmp_path / "b.txt").write_text("hello again\n")
    resp = preview_workspace_replace(tmp_path, "hello", "hi")
    result = apply_workspace_replace(resp.previews, "hello", "hi")
    assert result.files_modified == 2
    assert result.replacements_count == 2
    assert (tmp_path / "a.txt").read_text() == "hi world\n"
    assert (tmp_path / "b.txt").read_text() == "hi again\n"


def test_apply_hash_mismatch_skips_file(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("hello world\n")
    resp = preview_workspace_replace(tmp_path, "hello", "hi")
    # Modify file after preview
    f.write_text("modified content\n")
    result = apply_workspace_replace(resp.previews, "hello", "hi")
    assert result.files_modified == 0
    assert result.files_skipped == 1
    assert "a.txt" in result.skipped_files
    assert f.read_text() == "modified content\n"


def test_apply_returns_counts(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("foo bar foo\n")
    (tmp_path / "b.txt").write_text("foo baz\n")
    resp = preview_workspace_replace(tmp_path, "foo", "qux")
    result = apply_workspace_replace(resp.previews, "foo", "qux")
    assert result.files_modified == 2
    assert result.replacements_count == 3
    assert result.files_skipped == 0
    assert result.skipped_files == []
    assert result.failed_files == []


def test_apply_io_error_reports_failed(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("hello world\n")
    resp = preview_workspace_replace(tmp_path, "hello", "hi")
    # Delete file to cause IO error on re-read
    f.unlink()
    result = apply_workspace_replace(resp.previews, "hello", "hi")
    assert result.files_modified == 0
    assert "a.txt" in result.failed_files


# ---------------------------------------------------------------------------
# Integration tests: WorkspaceSearchPane replace UI
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workspace_search_pane_has_replace_input(tmp_path: Path) -> None:
    from textual.widgets import Input

    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ws_pane = app.query_one(WorkspaceSearchPane)
        replace_input = ws_pane.query_one("#ws-replace", Input)
        assert replace_input is not None


@pytest.mark.asyncio
async def test_workspace_search_pane_has_replace_all_button(tmp_path: Path) -> None:
    from textual.widgets import Button

    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ws_pane = app.query_one(WorkspaceSearchPane)
        btn = ws_pane.query_one("#ws-replace-all", Button)
        assert btn is not None


@pytest.mark.asyncio
async def test_replace_all_modifies_files(tmp_path: Path) -> None:
    """Replace All confirms via modal, then modifies files."""
    f = tmp_path / "test.txt"
    f.write_text("hello world\n")

    from textual.widgets import Input

    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "hello"
        ws_pane.query_one("#ws-replace", Input).value = "hi"
        ws_pane._run_search()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        ws_pane._run_replace_all()
        # Wait for count worker + modal to appear
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        # Confirm in the modal
        await pilot.click("#apply-all")
        await pilot.wait_for_scheduled_animations()

    assert f.read_text() == "hi world\n"


@pytest.mark.asyncio
async def test_replace_all_updates_status_label(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("foo bar\nfoo baz\n")

    from textual.widgets import Input, Label

    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "foo"
        ws_pane.query_one("#ws-replace", Input).value = "bar"
        ws_pane._run_search()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        ws_pane._run_replace_all()
        # Wait for count worker + modal
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        # Confirm
        await pilot.click("#apply-all")
        await pilot.wait_for_scheduled_animations()

        status = ws_pane.query_one("#ws-replace-status", Label)
        status_text = str(status.content)
        # Should mention 2 replacements and 1 file
        assert "2" in status_text
        assert "1" in status_text


@pytest.mark.asyncio
async def test_replace_all_empty_query_does_nothing(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("hello\n")

    from textual.widgets import Input

    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = ""
        ws_pane.query_one("#ws-replace", Input).value = "replacement"
        ws_pane._run_replace_all()
        await pilot.wait_for_scheduled_animations()

    assert f.read_text() == "hello\n"


@pytest.mark.asyncio
async def test_replace_all_shows_confirmation_modal(tmp_path: Path) -> None:
    """Replace All triggers confirmation modal before replacing."""
    (tmp_path / "test.txt").write_text("hello world\n")

    from textual.widgets import Input

    from tests.conftest import make_app
    from textual_code.modals import ReplacePreviewScreen
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "hello"
        ws_pane.query_one("#ws-replace", Input).value = "hi"
        ws_pane._run_search()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        ws_pane._run_replace_all()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        # Modal should be on the screen stack
        assert isinstance(app.screen, ReplacePreviewScreen)


@pytest.mark.asyncio
async def test_replace_all_cancel_does_not_replace(tmp_path: Path) -> None:
    """Cancelling the modal leaves files unchanged."""
    f = tmp_path / "test.txt"
    f.write_text("hello world\n")

    from textual.widgets import Input

    from tests.conftest import make_app
    from textual_code.modals import ReplacePreviewScreen
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "hello"
        ws_pane.query_one("#ws-replace", Input).value = "hi"
        ws_pane._run_search()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        ws_pane._run_replace_all()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()

        assert isinstance(app.screen, ReplacePreviewScreen)

        # Cancel
        await pilot.click("#cancel")
        await pilot.wait_for_scheduled_animations()

        # Modal should be dismissed
        assert not isinstance(app.screen, ReplacePreviewScreen)

    # File should be unchanged
    assert f.read_text() == "hello world\n"


@pytest.mark.asyncio
async def test_replace_all_no_matches_shows_status_no_modal(tmp_path: Path) -> None:
    """When no matches selected, show status message without modal."""
    (tmp_path / "test.txt").write_text("hello world\n")

    from textual.widgets import Input, Label

    from tests.conftest import make_app
    from textual_code.modals import ReplacePreviewScreen
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.wait_for_scheduled_animations()
        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "nonexistent_xyz"
        ws_pane.query_one("#ws-replace", Input).value = "replacement"
        ws_pane._run_search()
        await pilot.wait_for_scheduled_animations()
        await pilot.wait_for_scheduled_animations()
        ws_pane._run_replace_all()
        await pilot.wait_for_scheduled_animations()

        # No modal should appear
        assert not isinstance(app.screen, ReplacePreviewScreen)

        # Status should show "No matches selected" (no results from search)
        status = ws_pane.query_one("#ws-replace-status", Label)
        assert "No matches selected" in str(status.content)


# ---------------------------------------------------------------------------
# Unit tests: _replace_at_positions()
# ---------------------------------------------------------------------------


def test_replace_at_positions_simple(tmp_path: Path) -> None:
    text = "hello world\nhello again\n"
    pattern = re.compile(re.escape("hello"))
    # Only replace the first occurrence (line 1, col 0)
    new_text, count, skipped = _replace_at_positions(text, pattern, "hi", {(1, 0)})
    assert count == 1
    assert skipped == 0
    assert new_text == "hi world\nhello again\n"


def test_replace_at_positions_partial_file(tmp_path: Path) -> None:
    text = "aaa bbb aaa\nccc aaa ddd\n"
    pattern = re.compile(re.escape("aaa"))
    # Replace only the match at line 1 col 8 and line 2 col 4
    new_text, count, skipped = _replace_at_positions(
        text, pattern, "XXX", {(1, 8), (2, 4)}
    )
    assert count == 2
    assert skipped == 0
    assert new_text == "aaa bbb XXX\nccc XXX ddd\n"


def test_replace_at_positions_regex_capture(tmp_path: Path) -> None:
    text = "foo bar baz\n"
    pattern = re.compile(r"(foo)")
    new_text, count, skipped = _replace_at_positions(
        text, pattern, r"\1_suffix", {(1, 0)}
    )
    assert count == 1
    assert new_text == "foo_suffix bar baz\n"


def test_replace_at_positions_multiple_matches_same_line() -> None:
    text = "ab ab ab\n"
    pattern = re.compile(re.escape("ab"))
    # Select only the 2nd occurrence (col 3)
    new_text, count, skipped = _replace_at_positions(text, pattern, "XY", {(1, 3)})
    assert count == 1
    assert skipped == 0
    assert new_text == "ab XY ab\n"


def test_replace_at_positions_skipped_count() -> None:
    text = "hello\n"
    pattern = re.compile(re.escape("hello"))
    # Position doesn't match any finditer result
    new_text, count, skipped = _replace_at_positions(
        text, pattern, "hi", {(1, 0), (5, 0)}
    )
    assert count == 1
    assert skipped == 1


# ---------------------------------------------------------------------------
# Unit tests: preview_selected_replace()
# ---------------------------------------------------------------------------


def test_preview_selected_replace_no_truncation(tmp_path: Path) -> None:
    # Create many files — use write_bytes to avoid Windows line-ending conversion
    for i in range(150):
        (tmp_path / f"file_{i:03d}.txt").write_bytes(b"hello world\n")

    results = [
        WorkspaceSearchResult(
            file_path=tmp_path / f"file_{i:03d}.txt",
            line_number=1,
            line_text="hello world",
            match_start=0,
            match_end=5,
            file_hash=hashlib.sha256(b"hello world\n").hexdigest(),
        )
        for i in range(150)
    ]
    response = preview_selected_replace(
        tmp_path, results, "hello", "hi", case_sensitive=True
    )
    # No truncation — all 150 files should be previewed
    assert len(response.previews) == 150
    assert response.is_truncated is False


def test_preview_selected_replace_generates_diff(tmp_path: Path) -> None:
    f = tmp_path / "test.txt"
    content = b"hello world\nhello again\n"
    f.write_bytes(content)
    file_hash = hashlib.sha256(content).hexdigest()

    results = [
        WorkspaceSearchResult(
            file_path=f,
            line_number=1,
            line_text="hello world",
            match_start=0,
            match_end=5,
            file_hash=file_hash,
        ),
    ]
    response = preview_selected_replace(
        tmp_path, results, "hello", "hi", case_sensitive=True
    )
    assert len(response.previews) == 1
    diff_text = "".join(response.previews[0].diff_lines)
    assert "-hello world" in diff_text
    assert "+hi world" in diff_text


def test_preview_selected_skips_modified_file(tmp_path: Path) -> None:
    f = tmp_path / "test.txt"
    f.write_text("hello world\n")
    old_hash = hashlib.sha256(b"old content\n").hexdigest()  # wrong hash

    results = [
        WorkspaceSearchResult(
            file_path=f,
            line_number=1,
            line_text="hello world",
            match_start=0,
            match_end=5,
            file_hash=old_hash,
        ),
    ]
    response = preview_selected_replace(
        tmp_path, results, "hello", "hi", case_sensitive=True
    )
    assert len(response.previews) == 0  # skipped due to hash mismatch


# ---------------------------------------------------------------------------
# Unit tests: apply_selected_replace()
# ---------------------------------------------------------------------------


def test_apply_selected_replace_hash_mismatch(tmp_path: Path) -> None:
    from textual_code.search import FileDiffPreview

    f = tmp_path / "test.txt"
    f.write_text("hello world\n")

    preview = FileDiffPreview(
        file_path=f,
        rel_path="test.txt",
        original_hash="wrong_hash",
        replacement_count=1,
        diff_lines=[],
    )
    results = [
        WorkspaceSearchResult(
            file_path=f,
            line_number=1,
            line_text="hello world",
            match_start=0,
            match_end=5,
        ),
    ]
    result = apply_selected_replace(
        [preview], results, "hello", "hi", case_sensitive=True
    )
    assert result.files_skipped == 1
    assert result.files_modified == 0
    # File should be unchanged
    assert f.read_text() == "hello world\n"
