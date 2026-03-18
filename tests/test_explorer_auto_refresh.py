"""
Explorer auto-refresh: workspace file/folder change detection + git status polling.

Group A — _collect_expanded_dir_mtimes()
Group B — _get_git_ref_mtimes()
Group C — _poll_workspace_change() directory changes
Group D — _poll_workspace_change() git changes
Group E — Integration (full app)
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.conftest import init_git_repo, make_app, requires_git
from textual_code.widgets.explorer import FilteredDirectoryTree

# ── Group A: _collect_expanded_dir_mtimes() ──────────────────────────────────


class TestCollectExpandedDirMtimes:
    async def test_a01_returns_workspace_root_mtime(self, tmp_path: Path):
        """T-01: Result always includes the workspace root directory mtime."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "file.py").write_text("x = 1\n")
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.sidebar.explorer.directory_tree
            mtimes = tree._collect_expanded_dir_mtimes()
            assert ws in mtimes
            assert mtimes[ws] == pytest.approx(ws.stat().st_mtime)

    async def test_a02_includes_expanded_excludes_collapsed(self, tmp_path: Path):
        """T-02: Only expanded directories are included in the snapshot."""
        ws = tmp_path / "ws"
        ws.mkdir()
        sub_a = ws / "aaa"
        sub_a.mkdir()
        (sub_a / "file.py").write_text("x\n")
        sub_b = ws / "bbb"
        sub_b.mkdir()
        (sub_b / "file.py").write_text("y\n")
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.sidebar.explorer.directory_tree
            # Initially only root children are visible, dirs are collapsed
            mtimes_before = tree._collect_expanded_dir_mtimes()
            assert sub_a not in mtimes_before
            assert sub_b not in mtimes_before

            # Expand sub_a by finding its node and expanding it
            for child in tree.root.children:
                if child.data is not None and child.data.path == sub_a:
                    child.expand()
                    break
            await pilot.pause()

            mtimes_after = tree._collect_expanded_dir_mtimes()
            assert sub_a in mtimes_after
            assert sub_b not in mtimes_after  # still collapsed


# ── Group B: _get_git_ref_mtimes() ──────────────────────────────────────────


class TestGetGitRefMtimes:
    @requires_git
    async def test_b01_returns_mtimes_with_git(self, tmp_path: Path):
        """T-03: Returns (index_mtime, head_mtime) when .git directory exists."""
        ws = tmp_path / "ws"
        ws.mkdir()
        init_git_repo(ws)
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.sidebar.explorer.directory_tree
            index_mtime, head_mtime = tree._get_git_ref_mtimes()
            assert index_mtime is not None
            assert head_mtime is not None
            assert index_mtime == (ws / ".git" / "index").stat().st_mtime
            assert head_mtime == (ws / ".git" / "HEAD").stat().st_mtime

    async def test_b02_returns_none_without_git(self, tmp_path: Path):
        """T-04: Returns (None, None) when no .git directory exists."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "file.py").write_text("x\n")
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.sidebar.explorer.directory_tree
            assert tree._get_git_ref_mtimes() == (None, None)

    async def test_b03_returns_none_when_git_is_file(self, tmp_path: Path):
        """T-05: Returns (None, None) when .git is a file (submodule)."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".git").write_text("gitdir: ../other/.git\n")
        (ws / "file.py").write_text("x\n")
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.sidebar.explorer.directory_tree
            assert tree._get_git_ref_mtimes() == (None, None)


# ── Group C: _poll_workspace_change() directory changes ──────────────────────


class TestPollWorkspaceChangeDir:
    async def test_c01_new_file_triggers_reload(self, tmp_path: Path):
        """T-06: Creating a new file changes dir mtime → reload triggered."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "existing.py").write_text("x\n")
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.sidebar.explorer.directory_tree
            # Initialize polling state
            tree._dir_mtimes = tree._collect_expanded_dir_mtimes()
            tree._git_ref_mtimes = tree._get_git_ref_mtimes()

            # Create a new file (changes workspace root mtime)
            (ws / "new_file.py").write_text("y\n")

            with patch.object(
                FilteredDirectoryTree, "reload", wraps=tree.reload
            ) as mock_reload:
                tree._poll_workspace_change()
                mock_reload.assert_called_once()

    async def test_c02_deleted_file_triggers_reload(self, tmp_path: Path):
        """T-07: Deleting a file changes dir mtime → reload triggered."""
        ws = tmp_path / "ws"
        ws.mkdir()
        target = ws / "to_delete.py"
        target.write_text("x\n")
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.sidebar.explorer.directory_tree
            tree._dir_mtimes = tree._collect_expanded_dir_mtimes()
            tree._git_ref_mtimes = tree._get_git_ref_mtimes()

            # Delete the file
            target.unlink()

            with patch.object(
                FilteredDirectoryTree, "reload", wraps=tree.reload
            ) as mock_reload:
                tree._poll_workspace_change()
                mock_reload.assert_called_once()

    async def test_c03_no_changes_no_reload(self, tmp_path: Path):
        """T-08: No filesystem changes → no reload or refresh."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "file.py").write_text("x\n")
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.sidebar.explorer.directory_tree
            tree._dir_mtimes = tree._collect_expanded_dir_mtimes()
            tree._git_ref_mtimes = tree._get_git_ref_mtimes()

            with patch.object(
                FilteredDirectoryTree, "reload", wraps=tree.reload
            ) as mock_reload, patch.object(tree, "refresh") as mock_refresh:
                tree._poll_workspace_change()
                mock_reload.assert_not_called()
                mock_refresh.assert_not_called()

    async def test_c04_polling_paused_skips_check(self, tmp_path: Path):
        """T-09: When _ws_polling_paused is True, poll is a no-op."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "file.py").write_text("x\n")
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.sidebar.explorer.directory_tree
            tree._dir_mtimes = tree._collect_expanded_dir_mtimes()
            tree._git_ref_mtimes = tree._get_git_ref_mtimes()
            tree._ws_polling_paused = True

            # Create a new file — should be ignored
            (ws / "new.py").write_text("y\n")

            with patch.object(
                FilteredDirectoryTree, "reload", wraps=tree.reload
            ) as mock_reload:
                tree._poll_workspace_change()
                mock_reload.assert_not_called()

    async def test_c05_resume_after_reload(self, tmp_path: Path):
        """T-10: After reload completes, _ws_polling_paused is reset to False."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "file.py").write_text("x\n")
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.sidebar.explorer.directory_tree
            tree._dir_mtimes = tree._collect_expanded_dir_mtimes()
            tree._git_ref_mtimes = tree._get_git_ref_mtimes()

            # Create file and trigger poll → reload
            (ws / "new.py").write_text("y\n")
            tree._poll_workspace_change()

            assert tree._ws_polling_paused is True

            # Wait for async reload to complete
            await pilot.pause()
            await pilot.pause()

            assert tree._ws_polling_paused is False


# ── Group D: _poll_workspace_change() git changes ───────────────────────────


class TestPollWorkspaceChangeGit:
    @requires_git
    async def test_d01_git_index_change_refreshes(self, tmp_path: Path):
        """T-11: Git index mtime change → invalidates git cache + refresh."""
        ws = tmp_path / "ws"
        ws.mkdir()
        init_git_repo(ws)
        (ws / "file.py").write_text("x\n")
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.sidebar.explorer.directory_tree
            tree._dir_mtimes = tree._collect_expanded_dir_mtimes()
            tree._git_ref_mtimes = tree._get_git_ref_mtimes()
            # Pre-load git status cache
            tree._ensure_git_status_loaded()
            assert tree._git_result is not None

            # Simulate git index change (e.g., git add)
            git_env = {**os.environ, "HOME": str(ws)}
            subprocess.run(
                ["git", "add", "file.py"],
                cwd=ws,
                check=True,
                capture_output=True,
                env=git_env,
            )

            with patch.object(
                FilteredDirectoryTree, "reload", wraps=tree.reload
            ) as mock_reload, patch.object(tree, "refresh") as mock_refresh:
                tree._poll_workspace_change()
                # Should refresh (git-only), NOT full reload
                mock_reload.assert_not_called()
                mock_refresh.assert_called_once()
                # Git cache should be invalidated
                assert tree._git_result is None

    @requires_git
    async def test_d02_both_dir_and_git_change_reloads(self, tmp_path: Path):
        """T-12: Both dir + git change → full reload (not just refresh)."""
        ws = tmp_path / "ws"
        ws.mkdir()
        init_git_repo(ws)
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.sidebar.explorer.directory_tree
            tree._dir_mtimes = tree._collect_expanded_dir_mtimes()
            tree._git_ref_mtimes = tree._get_git_ref_mtimes()

            # Create new file (dir change) AND stage it (git change)
            (ws / "new.py").write_text("y\n")
            git_env = {**os.environ, "HOME": str(ws)}
            subprocess.run(
                ["git", "add", "new.py"],
                cwd=ws,
                check=True,
                capture_output=True,
                env=git_env,
            )

            with patch.object(
                FilteredDirectoryTree, "reload", wraps=tree.reload
            ) as mock_reload:
                tree._poll_workspace_change()
                # Dir change takes priority → full reload
                mock_reload.assert_called_once()

    @requires_git
    async def test_d03_git_only_preserves_expanded_state(self, tmp_path: Path):
        """T-13: Git-only refresh does not collapse expanded directories."""
        ws = tmp_path / "ws"
        ws.mkdir()
        init_git_repo(ws)
        sub = ws / "subdir"
        sub.mkdir()
        (sub / "inner.py").write_text("x\n")
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.sidebar.explorer.directory_tree

            # Expand the subdir
            for child in tree.root.children:
                if child.data is not None and child.data.path == sub:
                    child.expand()
                    break
            await pilot.pause()

            tree._dir_mtimes = tree._collect_expanded_dir_mtimes()
            tree._git_ref_mtimes = tree._get_git_ref_mtimes()

            # Simulate git-only change (stage existing file)
            git_env = {**os.environ, "HOME": str(ws)}
            subprocess.run(
                ["git", "add", "subdir/inner.py"],
                cwd=ws,
                check=True,
                capture_output=True,
                env=git_env,
            )

            tree._poll_workspace_change()
            await pilot.pause()

            # Verify subdir is still expanded
            for child in tree.root.children:
                if child.data is not None and child.data.path == sub:
                    assert child.is_expanded, (
                        "subdir should remain expanded after git-only refresh"
                    )
                    break


# ── Group E: Integration (full app) ─────────────────────────────────────────


class TestIntegration:
    async def test_e01_new_file_appears_after_poll(self, tmp_path: Path):
        """T-14: New file appears in tree after poll + pause."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "existing.py").write_text("x\n")
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.sidebar.explorer.directory_tree
            tree._dir_mtimes = tree._collect_expanded_dir_mtimes()
            tree._git_ref_mtimes = tree._get_git_ref_mtimes()

            # Verify new_file not in tree yet
            names_before = {
                c.data.path.name for c in tree.root.children if c.data is not None
            }
            assert "new_file.txt" not in names_before

            # Create a new file
            (ws / "new_file.txt").write_text("hello\n")

            # Trigger poll and wait for async reload
            tree._poll_workspace_change()
            await pilot.pause()
            await pilot.pause()

            # Verify new file now appears in tree
            names_after = {
                c.data.path.name for c in tree.root.children if c.data is not None
            }
            assert "new_file.txt" in names_after

    async def test_e02_expanded_dirs_preserved_after_reload(self, tmp_path: Path):
        """T-15: Expanded dirs remain expanded after dir-change auto-refresh."""
        ws = tmp_path / "ws"
        ws.mkdir()
        sub = ws / "mydir"
        sub.mkdir()
        (sub / "inner.py").write_text("x\n")
        (ws / "root.py").write_text("y\n")
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.sidebar.explorer.directory_tree

            # Expand the subdir
            for child in tree.root.children:
                if child.data is not None and child.data.path == sub:
                    child.expand()
                    break
            await pilot.pause()

            tree._dir_mtimes = tree._collect_expanded_dir_mtimes()
            tree._git_ref_mtimes = tree._get_git_ref_mtimes()

            # Create a new file in workspace root (triggers dir change)
            (ws / "added.py").write_text("z\n")

            # Trigger poll and wait for async reload
            tree._poll_workspace_change()
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()

            # Verify mydir is still expanded after reload
            found = False
            for child in tree.root.children:
                if child.data is not None and child.data.path == sub:
                    assert child.is_expanded, (
                        "mydir should remain expanded after auto-refresh"
                    )
                    found = True
                    break
            assert found, "mydir node not found in tree after reload"
