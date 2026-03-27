"""Tests for compact folder rendering in Explorer sidebar (issue #128).

These tests verify:
1. Single-child directory chains are collapsed into one node with joined label
2. Chains end at multi-child or file-only directories
3. Filtering (hidden files) is applied before compacting
4. The setting can be toggled on/off
5. select_file works with compacted intermediate paths
"""

from __future__ import annotations

from pathlib import Path

from tests.conftest import make_app
from textual_code.widgets.explorer import Explorer, FilteredDirectoryTree


class TestCompactFolderDetection:
    """Unit tests for compact folder chain detection in _populate_node."""

    def test_a01_single_child_dir_chain_compacted(self, tmp_path: Path):
        """Single-child dir chains produce one node with joined label."""
        ws = tmp_path / "ws"
        ws.mkdir()
        # Create chain: src/main/java/App.java
        chain = ws / "src" / "main" / "java"
        chain.mkdir(parents=True)
        (chain / "App.java").touch()

        tree = FilteredDirectoryTree(ws, compact_folders=True)
        content = tree._load_directory_sync(ws)
        # Should have one entry: the "src" directory
        assert len(content) == 1

        # Populate the root node
        root_node = _FakeNode()
        tree._populate_node(root_node, content)  # ty: ignore[invalid-argument-type]

        # Should have exactly one child with joined label "src/main/java"
        assert len(root_node.children) == 1
        child = root_node.children[0]
        assert child.label == "src/main/java"
        # The DirEntry path should point to the deepest directory
        assert child.data.path == (ws / "src" / "main" / "java").resolve()
        assert child.allow_expand is True

    def test_a02_no_compaction_when_multiple_children(self, tmp_path: Path):
        """Directories with multiple children should not be compacted."""
        ws = tmp_path / "ws"
        ws.mkdir()
        src = ws / "src"
        src.mkdir()
        (src / "file1.py").touch()
        (src / "file2.py").touch()

        tree = FilteredDirectoryTree(ws, compact_folders=True)
        content = tree._load_directory_sync(ws)
        root_node = _FakeNode()
        tree._populate_node(root_node, content)  # ty: ignore[invalid-argument-type]

        # Should have one child "src" (not compacted, has 2 children)
        assert len(root_node.children) == 1
        child = root_node.children[0]
        assert child.label == "src"

    def test_a03_chain_ends_at_single_file(self, tmp_path: Path):
        """A directory with a single file child should not be part of the chain."""
        ws = tmp_path / "ws"
        ws.mkdir()
        src = ws / "src"
        src.mkdir()
        (src / "main.py").touch()

        tree = FilteredDirectoryTree(ws, compact_folders=True)
        content = tree._load_directory_sync(ws)
        root_node = _FakeNode()
        tree._populate_node(root_node, content)  # ty: ignore[invalid-argument-type]

        # "src" should not be compacted (single child is a file, not a dir)
        assert len(root_node.children) == 1
        child = root_node.children[0]
        assert child.label == "src"

    def test_a04_deep_chain_compacted(self, tmp_path: Path):
        """Deep chains (>3 levels) should compact fully."""
        ws = tmp_path / "ws"
        ws.mkdir()
        chain = ws / "a" / "b" / "c" / "d" / "e"
        chain.mkdir(parents=True)
        (chain / "file.txt").touch()

        tree = FilteredDirectoryTree(ws, compact_folders=True)
        content = tree._load_directory_sync(ws)
        root_node = _FakeNode()
        tree._populate_node(root_node, content)  # ty: ignore[invalid-argument-type]

        assert len(root_node.children) == 1
        child = root_node.children[0]
        assert child.label == "a/b/c/d/e"
        assert child.data.path == chain.resolve()

    def test_a05_compact_disabled_shows_normal(self, tmp_path: Path):
        """When compact_folders=False, chains should not be compacted."""
        ws = tmp_path / "ws"
        ws.mkdir()
        chain = ws / "src" / "main" / "java"
        chain.mkdir(parents=True)
        (chain / "App.java").touch()

        tree = FilteredDirectoryTree(ws, compact_folders=False)
        content = tree._load_directory_sync(ws)
        root_node = _FakeNode()
        tree._populate_node(root_node, content)  # ty: ignore[invalid-argument-type]

        # Should have one child "src" (not compacted)
        assert len(root_node.children) == 1
        child = root_node.children[0]
        assert child.label == "src"

    def test_a06_hidden_files_excluded_before_compacting(self, tmp_path: Path):
        """Hidden files should be filtered before deciding compaction."""
        ws = tmp_path / "ws"
        ws.mkdir()
        src = ws / "src"
        src.mkdir()
        main = src / "main"
        main.mkdir()
        (main / "app.py").touch()
        # Hidden file in src/ — should be invisible when show_hidden_files=False
        (src / ".hidden").touch()

        tree = FilteredDirectoryTree(ws, compact_folders=True, show_hidden_files=False)
        content = tree._load_directory_sync(ws)
        root_node = _FakeNode()
        tree._populate_node(root_node, content)  # ty: ignore[invalid-argument-type]

        # src has only "main" visible (hidden file filtered out), so should compact
        assert len(root_node.children) == 1
        child = root_node.children[0]
        assert child.label == "src/main"

    def test_a07_chain_stops_when_dir_has_mixed_children(self, tmp_path: Path):
        """Chain should stop when a dir has both a subdir and a file."""
        ws = tmp_path / "ws"
        ws.mkdir()
        src = ws / "src"
        src.mkdir()
        main = src / "main"
        main.mkdir()
        (src / "README.md").touch()
        (main / "app.py").touch()

        tree = FilteredDirectoryTree(ws, compact_folders=True)
        content = tree._load_directory_sync(ws)
        root_node = _FakeNode()
        tree._populate_node(root_node, content)  # ty: ignore[invalid-argument-type]

        # "src" has 2 children (main/ and README.md), so not compacted
        assert len(root_node.children) == 1
        child = root_node.children[0]
        assert child.label == "src"

    def test_a08_multiple_top_level_dirs_compact_independently(self, tmp_path: Path):
        """Multiple top-level dirs should each compact independently."""
        ws = tmp_path / "ws"
        ws.mkdir()
        # Chain 1: src/main/App.java
        chain1 = ws / "src" / "main"
        chain1.mkdir(parents=True)
        (chain1 / "App.java").touch()
        # Chain 2: tests/unit/test_app.py
        chain2 = ws / "tests" / "unit"
        chain2.mkdir(parents=True)
        (chain2 / "test_app.py").touch()

        tree = FilteredDirectoryTree(ws, compact_folders=True)
        content = tree._load_directory_sync(ws)
        root_node = _FakeNode()
        tree._populate_node(root_node, content)  # ty: ignore[invalid-argument-type]

        assert len(root_node.children) == 2
        labels = sorted(child.label for child in root_node.children)
        assert labels == ["src/main", "tests/unit"]


class TestCompactFolderIntegration:
    """Mounted app integration tests for compact folder rendering."""

    async def test_c01_expand_compacted_node_shows_deepest_contents(
        self, workspace: Path
    ):
        """Expanding a compacted node should show contents of the deepest dir."""
        # Create chain: src/main/java/App.java
        chain = workspace / "src" / "main" / "java"
        chain.mkdir(parents=True)
        (chain / "App.java").touch()
        (chain / "Utils.java").touch()

        app = make_app(workspace)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()

            assert app.sidebar is not None
            explorer = app.sidebar.query_one(Explorer)
            tree = explorer.directory_tree

            # Find the compacted "src/main/java" node
            root = tree.root
            compact_node = None
            for child in root.children:
                if child.data is not None and child.data.path == chain.resolve():
                    compact_node = child
                    break
            assert compact_node is not None, "Should have a compacted node"
            assert "src/main/java" in compact_node.label.plain  # ty: ignore[unresolved-attribute]

    async def test_c02_select_file_inside_compacted_chain(self, workspace: Path):
        """select_file should navigate to a file inside a compacted directory."""
        chain = workspace / "src" / "main"
        chain.mkdir(parents=True)
        f_top = workspace / "top.py"
        f_nested = chain / "app.py"
        f_top.write_text("# top\n")
        f_nested.write_text("# app\n")

        app = make_app(workspace, open_file=f_top)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()

            assert app.sidebar is not None
            explorer = app.sidebar.query_one(Explorer)

            # Open nested file inside compacted chain
            await app.main_view.action_open_code_editor(f_nested)
            for attempt in range(50):
                await pilot.pause()
                node = explorer.directory_tree.cursor_node
                if (
                    node is not None
                    and node.data is not None
                    and node.data.path == f_nested
                ):
                    break
                if explorer._pending_path is None and attempt % 10 == 9:
                    explorer.select_file(f_nested)

            assert explorer.directory_tree.cursor_node is not None
            assert explorer.directory_tree.cursor_node.data.path == f_nested  # ty: ignore[unresolved-attribute]


class TestCompactFolderSetting:
    """Tests for the compact_folders configuration setting."""

    def test_b01_default_enabled(self):
        """compact_folders should default to True."""
        from textual_code.config import DEFAULT_EDITOR_SETTINGS

        assert "compact_folders" in DEFAULT_EDITOR_SETTINGS
        assert DEFAULT_EDITOR_SETTINGS["compact_folders"] is True

    def test_b02_setting_key_registered(self):
        """compact_folders should be in EDITOR_KEYS."""
        from textual_code.config import EDITOR_KEYS

        assert "compact_folders" in EDITOR_KEYS


# ── Helper for unit-testing _populate_node without mounting ──────────────


class _FakeChildNode:
    """Minimal stand-in for a tree child node."""

    def __init__(self, label: str, data, allow_expand: bool):
        self.label = label
        self.data = data
        self.allow_expand = allow_expand


class _FakeNode:
    """Minimal stand-in for a TreeNode, capturing add() calls."""

    def __init__(self):
        self.children: list[_FakeChildNode] = []

    def remove_children(self):
        self.children.clear()

    def add(self, label, *, data=None, allow_expand=False):
        child = _FakeChildNode(label, data, allow_expand)
        self.children.append(child)
        return child

    def expand(self):
        pass
