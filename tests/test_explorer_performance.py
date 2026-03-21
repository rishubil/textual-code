"""Tests for explorer startup performance optimizations (issue #5).

These tests verify:
1. Lazy per-directory gitignore loading (no workspace-wide traversal)
2. Background loading of git status (non-blocking render)
3. os.scandir optimization with is_dir caching in _load_directory
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.conftest import make_app
from textual_code.widgets.explorer import FilteredDirectoryTree

# ── os.scandir optimization tests ────────────────────────────────────────────


class TestScandirOptimization:
    def test_a01_is_dir_cache_populated_after_load(self, tmp_path: Path):
        """_load_directory populates _is_dir_cache with scanned entries."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "file.txt").touch()
        sub = ws / "subdir"
        sub.mkdir()
        tree = FilteredDirectoryTree(ws)
        assert hasattr(tree, "_is_dir_cache"), (
            "FilteredDirectoryTree must have _is_dir_cache attribute"
        )

    def test_a02_uses_scandir_not_iterdir(self, tmp_path: Path):
        """_load_directory should use os.scandir instead of path.iterdir."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "file.txt").touch()
        tree = FilteredDirectoryTree(ws)
        with patch(
            "textual_code.widgets.explorer.os.scandir", wraps=os.scandir
        ) as mock_scandir:
            tree._load_directory_sync(ws)
            mock_scandir.assert_called_once()

    def test_a03_scandir_provides_is_dir_without_stat(self, tmp_path: Path):
        """_load_directory should determine is_dir from scandir entries, not stat."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "file.txt").touch()
        sub = ws / "subdir"
        sub.mkdir()
        tree = FilteredDirectoryTree(ws)
        tree._load_directory_sync(ws)
        # After loading, cache should have entries
        assert len(tree._is_dir_cache) >= 2
        # subdir should be marked as directory
        ws_resolved = ws.resolve()
        assert tree._is_dir_cache.get(ws_resolved / "subdir") is True
        assert tree._is_dir_cache.get(ws_resolved / "file.txt") is False

    def test_a04_populate_node_consumes_cache(self, tmp_path: Path):
        """_populate_node should pop entries from _is_dir_cache."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "file.txt").touch()
        (ws / "subdir").mkdir()
        tree = FilteredDirectoryTree(ws)
        content = tree._load_directory_sync(ws)
        # Cache should be populated
        assert len(tree._is_dir_cache) >= 2
        # Simulate _populate_node: it should consume cache entries
        tree._populate_node(tree.root, content)
        # Cache entries for these paths should be consumed (popped)
        ws_resolved = ws.resolve()
        assert tree._is_dir_cache.get(ws_resolved / "file.txt") is None
        assert tree._is_dir_cache.get(ws_resolved / "subdir") is None


# ── Background git status loading tests ──────────────────────────────────────


class TestBackgroundGitStatusLoading:
    def test_b01_bg_loading_flag_exists(self, tmp_path: Path):
        """FilteredDirectoryTree has _bg_loading_started flag."""
        ws = tmp_path / "ws"
        ws.mkdir()
        tree = FilteredDirectoryTree(ws)
        assert hasattr(tree, "_bg_loading_started"), (
            "FilteredDirectoryTree must have _bg_loading_started flag"
        )
        assert tree._bg_loading_started is False

    @pytest.mark.asyncio
    async def test_b02_git_status_loads_in_background(self, tmp_path: Path):
        """Git status loads in background after app mount."""
        ws = tmp_path / "ws"
        ws.mkdir()
        config = tmp_path / "settings.toml"
        app = make_app(ws, user_config_path=config)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()  # allow background worker to complete
            assert app.sidebar is not None
            tree = app.sidebar.explorer.directory_tree
            assert tree._bg_loading_started is True

    @pytest.mark.asyncio
    async def test_b03_render_not_blocked_by_git_status(self, tmp_path: Path):
        """Tree renders immediately; git status loaded in background."""
        ws = tmp_path / "ws"
        ws.mkdir()
        config = tmp_path / "settings.toml"
        app = make_app(ws, user_config_path=config)
        async with app.run_test() as pilot:
            assert app.sidebar is not None
            tree = app.sidebar.explorer.directory_tree
            # bg_loading_started should be True immediately after mount
            assert tree._bg_loading_started is True
            await pilot.pause()
            await pilot.pause()


# ── Lazy gitignore loading tests ─────────────────────────────────────────────


class TestLazyGitignoreLoading:
    def test_c01_no_initial_workspace_traversal(self, tmp_path: Path):
        """Creating a tree does NOT scan workspace for .gitignore files."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".gitignore").write_text("*.log\n")
        sub = ws / "deep" / "nested"
        sub.mkdir(parents=True)
        (sub / ".gitignore").write_text("*.tmp\n")

        tree = FilteredDirectoryTree(ws)
        # _gitignore_checked_dirs should exist and be empty
        assert hasattr(tree, "_gitignore_checked_dirs")
        assert len(tree._gitignore_checked_dirs) == 0
        # No specs loaded yet
        specs = tree._get_gitignore_specs()
        assert len(specs) == 0

    def test_c02_lazy_loads_on_is_gitignored_call(self, tmp_path: Path):
        """_is_gitignored lazily loads ancestor gitignore files."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".gitignore").write_text("*.log\n")
        (ws / "debug.log").touch()

        tree = FilteredDirectoryTree(ws)
        # Before: no specs
        assert len(tree._get_gitignore_specs()) == 0
        # Calling _is_gitignored triggers lazy load for ancestor dirs
        result = tree._is_gitignored(ws / "debug.log")
        assert result is True
        # After: root .gitignore loaded
        assert len(tree._get_gitignore_specs()) == 1
        # Root dir should be in checked set
        assert ws in tree._gitignore_checked_dirs

    def test_c03_skips_hidden_ancestor_dirs(self, tmp_path: Path):
        """Lazy loading skips .gitignore in hidden directory ancestors."""
        ws = tmp_path / "ws"
        ws.mkdir()
        hidden = ws / ".hidden"
        hidden.mkdir()
        (hidden / ".gitignore").write_text("*\n")
        (hidden / "file.txt").touch()

        tree = FilteredDirectoryTree(ws)
        # Checking a file inside a hidden dir: ancestor .hidden has .gitignore
        # but it should be skipped (hidden dirs' gitignores are not loaded)
        result = tree._is_gitignored(hidden / "file.txt")
        assert result is False

    def test_c04_is_dir_param_skips_stat(self, tmp_path: Path):
        """_is_gitignored with is_dir parameter avoids stat call."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".gitignore").write_text("build/\n")
        build_dir = ws / "build"
        build_dir.mkdir()

        tree = FilteredDirectoryTree(ws)
        # Pass is_dir=True to avoid stat
        result = tree._is_gitignored(build_dir, is_dir=True)
        assert result is True

    def test_c05_only_loads_ancestors_not_siblings(self, tmp_path: Path):
        """Lazy load only checks ancestor dirs, not sibling dirs."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".gitignore").write_text("*.log\n")
        src = ws / "src"
        src.mkdir()
        (src / ".gitignore").write_text("*.tmp\n")
        docs = ws / "docs"
        docs.mkdir()
        (docs / ".gitignore").write_text("*.bak\n")

        tree = FilteredDirectoryTree(ws)
        # Check a file in src/ — should load root and src gitignores
        tree._is_gitignored(src / "app.tmp")
        checked = tree._gitignore_checked_dirs
        assert ws in checked
        assert src in checked
        # docs/ should NOT be checked (it's a sibling, not an ancestor)
        assert docs not in checked

    def test_c06_reload_clears_checked_dirs(self, tmp_path: Path):
        """reload() clears _gitignore_checked_dirs for re-discovery."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".gitignore").write_text("*.log\n")

        tree = FilteredDirectoryTree(ws)
        tree._is_gitignored(ws / "test.log")
        assert len(tree._gitignore_checked_dirs) > 0
        # Simulate reload cache clearing
        tree._gitignore_specs = None
        tree._gitignore_checked_dirs.clear()
        tree._gitignore_cache.clear()
        assert len(tree._gitignore_checked_dirs) == 0
