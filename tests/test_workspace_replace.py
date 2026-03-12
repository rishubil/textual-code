"""Tests for workspace replace feature.

Covers:
- replace_workspace() pure function (unit tests)
- WorkspaceSearchPane replace UI integration tests
"""

from __future__ import annotations

from pathlib import Path

import pytest

from textual_code.search import WorkspaceReplaceResult, replace_workspace

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


def test_replace_hidden_file_skipped(tmp_path: Path) -> None:
    f = tmp_path / ".hidden"
    f.write_text("needle\n")
    result = replace_workspace(tmp_path, "needle", "pin")
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
# Integration tests: WorkspaceSearchPane replace UI
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workspace_search_pane_has_replace_input(tmp_path: Path) -> None:
    from textual.widgets import Input

    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
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
        await pilot.pause()
        ws_pane = app.query_one(WorkspaceSearchPane)
        btn = ws_pane.query_one("#ws-replace-all", Button)
        assert btn is not None


@pytest.mark.asyncio
async def test_replace_all_modifies_files(tmp_path: Path) -> None:
    f = tmp_path / "test.txt"
    f.write_text("hello world\n")

    from textual.widgets import Input

    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "hello"
        ws_pane.query_one("#ws-replace", Input).value = "hi"
        ws_pane._run_replace_all()
        await pilot.pause()

    assert f.read_text() == "hi world\n"


@pytest.mark.asyncio
async def test_replace_all_updates_status_label(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("foo bar\nfoo baz\n")

    from textual.widgets import Input, Label

    from tests.conftest import make_app
    from textual_code.widgets.workspace_search import WorkspaceSearchPane

    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = "foo"
        ws_pane.query_one("#ws-replace", Input).value = "bar"
        ws_pane._run_replace_all()
        await pilot.pause()

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
        await pilot.pause()
        ws_pane = app.query_one(WorkspaceSearchPane)
        ws_pane.query_one("#ws-query", Input).value = ""
        ws_pane.query_one("#ws-replace", Input).value = "replacement"
        ws_pane._run_replace_all()
        await pilot.pause()

    assert f.read_text() == "hello\n"
