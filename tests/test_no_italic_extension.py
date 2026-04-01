"""Tests that file/directory names in the Explorer have no italic styling.

Textual's upstream DirectoryTree applies italic to file extensions via
highlight_regex(r"\\.+$") with the directory-tree--extension component class.
FilteredDirectoryTree.render_label() must strip this for ALL nodes.
"""

from pathlib import Path

import pytest
from rich.style import Style

from tests.conftest import make_app


def _label_has_italic(text, console):
    """Check if any character in a Rich Text has italic in its resolved style.

    Returns (bool, str) where the string describes which offset/char has italic,
    useful for debugging test failures.
    """
    plain = text.plain
    for i in range(len(plain)):
        style = text.get_style_at_offset(console, i)
        if style.italic:
            return True, f"offset {i} char {plain[i]!r}"
    return False, ""


def _find_root_file_node(tree, filename):
    """Find a tree node by filename among root's direct children."""
    for child in tree.root.children:
        if child.data is not None and child.data.path.name == filename:
            return child
    return None


def _assert_no_italic(tree, app, names):
    """Assert that none of the named nodes have italic in their rendered label."""
    for name in names:
        node = _find_root_file_node(tree, name)
        assert node is not None, f"node not found for {name}"
        label = tree.render_label(node, Style(), Style())
        has_italic, detail = _label_has_italic(label, app.console)
        assert not has_italic, f"{name} has italic at {detail}"


class TestNoItalicExtension:
    """Verify that render_label does NOT apply italic to any filename."""

    @pytest.mark.asyncio
    async def test_a01_regular_files_no_italic(self, tmp_path: Path):
        """Regular files with various extension patterns must not have italic."""
        ws = tmp_path / "ws"
        ws.mkdir()
        filenames = [
            "file.txt",
            "script.py",
            "aaaa.bbb",
            "data.backup",
            "config.local.json",
            "archive.tar.gz",
            "my file.txt",
            "backup.001",
            "CAPS.TXT",
            "file.c",
            "document.markdown",
            "file..txt",
            "file-v2.0.tar.gz",
            "\ud30c\uc77c.txt",
        ]
        for fn in filenames:
            (ws / fn).write_text("content\n")
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            assert app.sidebar is not None
            _assert_no_italic(app.sidebar.explorer.directory_tree, app, filenames)

    @pytest.mark.asyncio
    async def test_a02_dotfiles_no_italic(self, tmp_path: Path):
        """Dotfiles must not have italic (regression test for existing fix)."""
        ws = tmp_path / "ws"
        ws.mkdir()
        filenames = [".gitignore", ".env", ".eslintrc.json", "...hidden"]
        for fn in filenames:
            (ws / fn).write_text("content\n")
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            assert app.sidebar is not None
            _assert_no_italic(app.sidebar.explorer.directory_tree, app, filenames)

    @pytest.mark.asyncio
    async def test_a03_no_extension_no_italic(self, tmp_path: Path):
        """Files without extensions must not have italic."""
        ws = tmp_path / "ws"
        ws.mkdir()
        filenames = ["Makefile", "README", "LICENSE", "Dockerfile"]
        for fn in filenames:
            (ws / fn).write_text("content\n")
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            assert app.sidebar is not None
            _assert_no_italic(app.sidebar.explorer.directory_tree, app, filenames)

    @pytest.mark.asyncio
    async def test_a04_directories_with_dots_no_italic(self, tmp_path: Path):
        """Directory names containing dots must not have italic."""
        ws = tmp_path / "ws"
        ws.mkdir()
        dirnames = ["my.config.d", "node.js.d"]
        for dn in dirnames:
            (ws / dn).mkdir()
            (ws / dn / "dummy.txt").write_text("x\n")
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            assert app.sidebar is not None
            _assert_no_italic(app.sidebar.explorer.directory_tree, app, dirnames)

    @pytest.mark.asyncio
    async def test_a05_gitignored_no_italic_with_dim(self, tmp_path: Path):
        """Gitignored files must have no italic even when dimmed."""
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".gitignore").write_text("*.log\n")
        (ws / "debug.log").write_text("log content\n")
        (ws / "app.py").write_text("print('hi')\n")
        app = make_app(ws)
        async with app.run_test() as pilot:
            await pilot.wait_for_scheduled_animations()
            assert app.sidebar is not None
            _assert_no_italic(
                app.sidebar.explorer.directory_tree, app, ["debug.log", "app.py"]
            )
