"""Tests for git diff gutter indicators (issue #41).

Tests the line-level diff computation between HEAD and current editor text,
the git HEAD content retrieval, and editor integration.
"""

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

from tests.conftest import (
    _GIT_TEST_ENV,
    git_add_commit,
    init_git_repo,
    make_app,
    requires_git,
)
from textual_code.widgets.code_editor import (
    LineChangeType,
    _compute_line_changes,
    _get_git_head_content,
)


def _assert_keys_in_range(result: dict[int, LineChangeType], new_lines: list[str]):
    """Assert all keys in result are valid indices into new_lines."""
    for k in result:
        assert 0 <= k < len(new_lines), f"key {k} out of range [0, {len(new_lines)})"


# ── _compute_line_changes unit tests ────────────────────────────────────────


class TestComputeLineChanges:
    def test_a01_no_changes(self):
        """Identical text produces empty dict."""
        old = ["a", "b", "c"]
        new = ["a", "b", "c"]
        result = _compute_line_changes(old, new)
        assert result == {}

    def test_a02_added_lines(self):
        """Inserted lines are marked ADDED."""
        old = ["a"]
        new = ["a", "b", "c"]
        result = _compute_line_changes(old, new)
        assert result[1] == LineChangeType.ADDED
        assert result[2] == LineChangeType.ADDED
        _assert_keys_in_range(result, new)

    def test_a03_modified_lines(self):
        """Replaced lines are marked MODIFIED."""
        old = ["a", "b", "c"]
        new = ["a", "x", "c"]
        result = _compute_line_changes(old, new)
        assert result[1] == LineChangeType.MODIFIED
        assert 0 not in result
        assert 2 not in result
        _assert_keys_in_range(result, new)

    def test_a04_deleted_lines_middle(self):
        """Deleted lines in the middle mark the next line as DELETED_ABOVE."""
        old = ["a", "b", "c", "d"]
        new = ["a", "d"]
        result = _compute_line_changes(old, new)
        # Lines "b" and "c" deleted — the line after deletion (index 1, "d") gets marker
        assert result[1] == LineChangeType.DELETED_ABOVE
        _assert_keys_in_range(result, new)

    def test_a05_deleted_lines_eof(self):
        """Deleted lines at EOF mark the last line as DELETED_BELOW."""
        old = ["a", "b", "c"]
        new = ["a"]
        result = _compute_line_changes(old, new)
        assert result[0] == LineChangeType.DELETED_BELOW
        _assert_keys_in_range(result, new)

    def test_a06_deleted_adjacent_to_modified(self):
        """When delete is adjacent to replace, SequenceMatcher merges into replace."""
        old = ["a", "b", "c", "d"]
        new = ["x", "d"]
        result = _compute_line_changes(old, new)
        # SequenceMatcher merges old[0:3] → new[0:1] as a single 'replace'.
        # Only line 0 is MODIFIED; deleted lines are absorbed into the replace.
        assert result[0] == LineChangeType.MODIFIED
        assert 1 not in result  # "d" is unchanged
        _assert_keys_in_range(result, new)

    def test_a06b_delete_separate_from_modify(self):
        """Separate delete and modify opcodes produce both indicators."""
        old = ["a", "b", "c", "d", "e"]
        new = ["a", "d", "e"]
        result = _compute_line_changes(old, new)
        # equal("a"), delete("b","c") at j1=1, equal("d","e")
        # Line 1 ("d") gets DELETED_ABOVE
        assert result[1] == LineChangeType.DELETED_ABOVE
        assert 0 not in result
        assert 2 not in result
        _assert_keys_in_range(result, new)

    def test_a07_mixed_changes(self):
        """Mixed add, modify, delete in one diff."""
        old = ["a", "b", "c", "d", "e"]
        new = ["a", "X", "new1", "new2", "e"]
        result = _compute_line_changes(old, new)
        # "b","c","d" replaced by "X","new1","new2"
        assert result[1] == LineChangeType.MODIFIED
        assert result[2] == LineChangeType.MODIFIED
        assert result[3] == LineChangeType.MODIFIED
        _assert_keys_in_range(result, new)

    def test_a08_empty_new_file(self):
        """All lines deleted (empty new file) returns empty dict."""
        old = ["a", "b", "c"]
        new = []
        result = _compute_line_changes(old, new)
        assert result == {}
        _assert_keys_in_range(result, new)

    def test_a09_large_file_skipped(self):
        """Files with more than 10000 lines return empty dict."""
        old = [f"line{i}" for i in range(10001)]
        new = [f"line{i}" for i in range(10001)]
        new[5000] = "changed"
        result = _compute_line_changes(old, new)
        assert result == {}

    def test_a10_deleted_at_beginning(self):
        """Deleted lines at the beginning mark line 0 as DELETED_ABOVE."""
        old = ["a", "b", "c"]
        new = ["c"]
        result = _compute_line_changes(old, new)
        assert result[0] == LineChangeType.DELETED_ABOVE
        _assert_keys_in_range(result, new)

    def test_a11_all_lines_added(self):
        """Empty old file with new content — all lines ADDED."""
        old = []
        new = ["a", "b", "c"]
        result = _compute_line_changes(old, new)
        for i in range(3):
            assert result[i] == LineChangeType.ADDED
        _assert_keys_in_range(result, new)


# ── _get_git_head_content unit tests ────────────────────────────────────────


class TestGetGitHeadContent:
    @requires_git
    def test_b01_returns_committed_content(self, tmp_path: Path):
        """Returns the committed content of a tracked file."""
        init_git_repo(tmp_path)
        committed = tmp_path / "committed.py"
        result = _get_git_head_content(committed)
        assert result is not None
        assert "# committed" in result

    @requires_git
    def test_b02_returns_none_for_untracked(self, tmp_path: Path):
        """Returns None for an untracked file."""
        init_git_repo(tmp_path)
        untracked = tmp_path / "newfile.py"
        untracked.write_text("# new\n")
        result = _get_git_head_content(untracked)
        assert result is None

    def test_b03_returns_none_no_git(self, tmp_path: Path):
        """Returns None when not in a git repo."""
        no_git = tmp_path / "file.py"
        no_git.write_text("# no git\n")
        result = _get_git_head_content(no_git)
        assert result is None

    def test_b04_returns_none_no_git_binary(self, tmp_path: Path):
        """Returns None when git binary is not found."""
        f = tmp_path / "file.py"
        f.write_text("# test\n")
        with patch("textual_code.widgets.code_editor._git_bin", None):
            result = _get_git_head_content(f)
        assert result is None

    @requires_git
    def test_b05_returns_non_ascii_utf8_content(self, tmp_path: Path):
        """Returns correct content for files with non-ASCII UTF-8 characters."""
        init_git_repo(tmp_path)
        committed = tmp_path / "committed.py"
        # Use Unicode escapes to avoid tripping the English-only language check
        korean = "\ud55c\uad6d\uc5b4"  # "Korean" in Korean
        japanese = "\u3053\u3093\u306b\u3061\u306f"  # "hello" in Japanese
        emoji = "\U0001f30d"  # globe emoji
        non_ascii = f"# {korean}\nprint('{japanese} {emoji}')\n"
        committed.write_text(non_ascii, encoding="utf-8")
        git_env = {**os.environ, **_GIT_TEST_ENV, "HOME": str(tmp_path)}
        subprocess.run(
            ["git", "add", "."],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            env=git_env,
        )
        subprocess.run(
            ["git", "commit", "-m", "add non-ascii"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            env=git_env,
        )
        result = _get_git_head_content(committed)
        assert result is not None
        assert korean in result
        assert japanese in result
        assert emoji in result

    @requires_git
    def test_b06_subprocess_uses_utf8_encoding(self, tmp_path: Path):
        """subprocess.run calls must pass encoding='utf-8' and errors='replace'."""
        init_git_repo(tmp_path)
        committed = tmp_path / "committed.py"
        calls: list[dict] = []
        original_run = subprocess.run

        def spy_run(*args, **kwargs):
            calls.append(kwargs)
            return original_run(*args, **kwargs)

        with patch(
            "textual_code.widgets.code_editor_git.subprocess.run", side_effect=spy_run
        ):
            _get_git_head_content(committed)

        assert len(calls) >= 2, "Expected at least 2 subprocess.run calls"
        for i, call_kwargs in enumerate(calls):
            assert call_kwargs.get("encoding") == "utf-8", (
                f"subprocess.run call {i} missing encoding='utf-8': {call_kwargs}"
            )
            assert call_kwargs.get("errors") == "replace", (
                f"subprocess.run call {i} missing errors='replace': {call_kwargs}"
            )

    @requires_git
    def test_b07_returns_latin1_content(self, tmp_path: Path):
        """Returns correct content for files committed in Latin-1 encoding."""
        init_git_repo(tmp_path)
        committed = tmp_path / "committed.py"
        # Latin-1 characters: e-acute, a-grave, n-tilde, u-umlaut
        text = "# caf\u00e9 r\u00e9sum\u00e9\nprint('\u00e0\u00f1\u00fc')\n"
        committed.write_bytes(text.encode("latin-1"))
        git_add_commit(tmp_path, "latin1 file")
        result = _get_git_head_content(committed, encoding="latin-1")
        assert result is not None
        assert "caf\u00e9" in result
        assert "r\u00e9sum\u00e9" in result
        assert "\u00e0\u00f1\u00fc" in result

    @requires_git
    def test_b08_returns_euc_kr_content(self, tmp_path: Path):
        """Returns correct content for files committed in EUC-KR encoding."""
        init_git_repo(tmp_path)
        committed = tmp_path / "committed.py"
        korean = "\ud55c\uad6d\uc5b4"  # "Korean" in Korean
        text = f"# {korean}\n"
        committed.write_bytes(text.encode("euc_kr"))
        git_add_commit(tmp_path, "euc-kr file")
        result = _get_git_head_content(committed, encoding="euc_kr")
        assert result is not None
        assert korean in result

    @requires_git
    def test_b10_git_show_uses_file_encoding(self, tmp_path: Path):
        """git rev-parse uses UTF-8; git show uses the provided encoding."""
        init_git_repo(tmp_path)
        committed = tmp_path / "committed.py"
        calls: list[dict] = []
        original_run = subprocess.run

        def spy_run(*args, **kwargs):
            calls.append(kwargs)
            return original_run(*args, **kwargs)

        with patch(
            "textual_code.widgets.code_editor_git.subprocess.run", side_effect=spy_run
        ):
            _get_git_head_content(committed, encoding="latin-1")

        assert len(calls) >= 2, "Expected at least 2 subprocess.run calls"
        # First call (git rev-parse) stays UTF-8
        assert calls[0].get("encoding") == "utf-8"
        assert calls[0].get("errors") == "replace"
        # Second call (git show) uses the provided encoding
        assert calls[1].get("encoding") == "latin-1"
        assert calls[1].get("errors") == "replace"

    @requires_git
    async def test_b11_fetch_head_lines_passes_encoding(self, tmp_path: Path):
        """_fetch_head_lines passes self.encoding to _get_git_head_content."""
        from textual_code.widgets.code_editor import CodeEditor

        init_git_repo(tmp_path)
        committed = tmp_path / "committed.py"

        captured_kwargs: list[dict] = []
        original_fn = _get_git_head_content

        def spy_fn(*args, **kwargs):
            captured_kwargs.append(kwargs)
            return original_fn(*args, **kwargs)

        app = make_app(tmp_path, open_file=committed, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            editors = list(app.query(CodeEditor))
            assert editors, "Expected at least one CodeEditor"
            editor = editors[0]
            editor.encoding = "latin-1"

            with patch(
                "textual_code.widgets.code_editor._get_git_head_content",
                side_effect=spy_fn,
            ):
                editor._fetch_head_lines()

            assert len(captured_kwargs) >= 1
            assert captured_kwargs[0].get("encoding") == "latin-1"


# ── Editor integration tests ────────────────────────────────────────────────


class TestEditorGitGutterIntegration:
    @requires_git
    async def test_c01_editor_shows_indicators(self, tmp_path: Path):
        """Modified committed file shows git indicators in the editor."""
        from textual_code.widgets.code_editor import CodeEditor

        init_git_repo(tmp_path)
        committed = tmp_path / "committed.py"
        # Modify the committed file on disk
        committed.write_text("# modified content\nprint('hello')\n")

        app = make_app(tmp_path, open_file=committed, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            await pilot.wait_for_scheduled_animations()
            editors = list(app.query(CodeEditor))
            assert len(editors) > 0
            editor = editors[0]
            # Wait for the background git diff worker
            await pilot.wait_for_scheduled_animations()
            await pilot.wait_for_scheduled_animations()
            await pilot.wait_for_scheduled_animations()
            # Indicators should be set
            line_changes = editor.editor._line_changes
            assert len(line_changes) > 0
            # All keys must be valid line indices
            line_count = editor.editor.document.line_count
            for k in line_changes:
                assert 0 <= k < line_count, f"key {k} out of range [0, {line_count})"

    @requires_git
    async def test_c02_no_indicators_untracked(self, tmp_path: Path):
        """Untracked file has no git indicators."""
        init_git_repo(tmp_path)
        newfile = tmp_path / "newfile.py"
        newfile.write_text("# new file\n")

        app = make_app(tmp_path, open_file=newfile, light=True)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            await pilot.wait_for_scheduled_animations()
            await pilot.wait_for_scheduled_animations()
            from textual_code.widgets.code_editor import CodeEditor

            editors = list(app.query(CodeEditor))
            assert len(editors) > 0
            editor = editors[0]
            assert editor.editor._line_changes == {}
